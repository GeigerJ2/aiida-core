###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################

from __future__ import annotations

import json
from collections.abc import Collection
from dataclasses import dataclass, field, fields
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from aiida.common.exceptions import NotExistent
from aiida.common.log import AIIDA_LOGGER
from aiida.tools.dumping.mapping import GroupNodeMapping
from aiida.tools.dumping.utils.types import DumpStoreKeys
from aiida.tools.dumping.utils.paths import DumpPaths
from aiida.tools.dumping.utils.time import DumpTimes
from aiida.tools.dumping.utils.types import StoreNameType

# TODO: Possibly dump hierarchy of dumped directory inside json file
# TODO: Currently, json file has only top-level "groups", "workflows", and "calculations"
# TODO: `add_entry` and `add_entries` shouldn't _require_ passing a store, but could be automatically evaluated from the
# type of the first node in the passed entry/entries
# NOTE: Could use DumpLogger also as container for orm.Nodes, that should be dumped
# NOTE: Should DumpLogger be not provided (None), or should it rather just be empty with no entries
# NOTE: Is on `save_log` again the whole history being written to disk? Ideally, this would be incremental
# NOTE: Shouldn't the logger have the `DumpTimes` attached to it??
# NOTE: Problem with general `node_mtime` is that `Group`s don't have an `mtime` attribute


logger = AIIDA_LOGGER.getChild("tools.dumping.logger")


@dataclass
class DumpLog:
    """Represents a single dump log entry."""

    path: Path
    symlinks: List[Path] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "path": str(self.path),
            "symlinks": [str(path) for path in self.symlinks] if self.symlinks else [],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DumpLog":
        symlinks = []
        if data.get("symlinks"):
            symlinks = [Path(path) for path in data["symlinks"]]

        return cls(
            path=Path(data["path"]),
            symlinks=symlinks,
        )

    def add_symlink(self, path: Path) -> None:
        """Add a symlink path to this log entry."""
        if path not in self.symlinks:
            self.symlinks.append(path)

    def remove_symlink(self, path: Path) -> bool:
        """Remove a symlink path from this log entry."""
        if path in self.symlinks:
            self.symlinks.remove(path)
            return True
        return False


@dataclass
class DumpLogStore:
    """A store for DumpLog entries, indexed by UUID."""

    entries: Dict[str, DumpLog] = field(default_factory=dict)

    def add_entry(self, uuid: str, entry: DumpLog) -> None:
        """Add a single entry to the container."""
        self.entries[uuid] = entry

    def add_entries(self, entries: Dict[str, DumpLog]) -> None:
        """Add a collection of entries to the container."""
        self.entries.update(entries)

    def del_entry(self, uuid: str) -> bool:
        """Remove a single entry by UUID."""
        if uuid in self.entries:
            del self.entries[uuid]
            return True
        return False

    def del_entries(self, uuids: Collection[str]) -> None:
        """Remove a collection of entries by UUID."""
        for uuid in uuids:
            if uuid in self.entries:
                del self.entries[uuid]

    def get_entry(self, uuid: str) -> Optional[DumpLog]:
        """Retrieve a single entry by UUID."""
        return self.entries.get(uuid)

    def __len__(self) -> int:
        """Return the number of entries in the container."""
        return len(self.entries)

    def __iter__(self):
        """Iterate over all entries."""
        return iter(self.entries.items())

    def to_dict(self) -> Dict:
        return {uuid: entry.to_dict() for uuid, entry in self.entries.items()}

    @classmethod
    def from_dict(cls, data: Dict) -> "DumpLogStore":
        store = cls()

        for uuid, entry_data in data.items():
            # Handle old format (backward compatibility)
            if isinstance(entry_data, dict) and "path" in entry_data:
                store.entries[uuid] = DumpLog.from_dict(entry_data)
            else:
                # Old format had just the path as a string
                store.entries[uuid] = DumpLog(path=Path(entry_data))

        return store

    def update_paths(self, old_str: str, new_str: str) -> None:
        """Update all paths in the store by replacing exact occurrences of old_str with new_str."""
        if not old_str.startswith("/"):
            old_str = f"/{old_str}"
        if not new_str.startswith("/"):
            new_str = f"/{new_str}"

        for uuid, entry in self.entries.items():
            # Check if old_str exists in the path
            path_str = str(entry.path)
            if old_str in path_str:
                # Create a new path with the replaced string
                new_path = Path(path_str.replace(old_str, new_str))
                entry.path = new_path

            # Also update symlinks
            for i, symlink_path in enumerate(entry.symlinks):
                symlink_str = str(symlink_path)
                if old_str in symlink_str:
                    entry.symlinks[i] = Path(symlink_str.replace(old_str, new_str))


@dataclass
class DumpLogStoreCollection:
    """Represents the entire log, with calculations and workflows (will be extended with Data)."""

    calculations: DumpLogStore
    workflows: DumpLogStore
    groups: DumpLogStore
    data: DumpLogStore


class DumpLogger:
    _instance = None
    _initialized = False  # To handle re-initialization

    @classmethod
    def reset_instance(cls):
        """Reset the singleton instance for testing purposes.

        Warning: This will completely clear the logger's state and should only be used in tests.
        """
        cls._instance = None
        cls._initialized = False

    def __new__(cls, dump_paths: DumpPaths, dump_times: DumpTimes, **kwargs):
        if cls._instance is None:
            cls._instance = super(DumpLogger, cls).__new__(cls)
        return cls._instance

    def __init__(
        self,
        dump_paths: DumpPaths,
        dump_times: DumpTimes,
        calculations: Optional[DumpLogStore] = None,
        workflows: Optional[DumpLogStore] = None,
        groups: Optional[DumpLogStore] = None,
        data: Optional[DumpLogStore] = None,
        last_dump_time: Optional[datetime] = None,
        group_node_mapping: Optional[GroupNodeMapping] = None,
    ) -> None:
        # Prevent re-initialization if already initialized
        if self._initialized:
            return

        self.dump_paths = dump_paths
        self.dump_times = dump_times
        self.calculations = calculations or DumpLogStore()
        self.workflows = workflows or DumpLogStore()
        self.groups = groups or DumpLogStore()
        self.data = data or DumpLogStore()
        self.last_dump_time = last_dump_time
        self._group_node_mapping = group_node_mapping
        self._initialized = True

    @classmethod
    def from_file(cls, dump_paths: DumpPaths) -> "DumpLogger":
        # Get or create the singleton instance
        instance = cls._instance if cls._instance else cls(dump_paths, DumpTimes())

        if not dump_paths.log_path.exists():
            return instance

        try:
            with dump_paths.log_path.open("r", encoding="utf-8") as f:
                prev_dump_data = json.load(f)

                # Load dump times
                if "last_dump_time" in prev_dump_data:
                    instance.last_dump_time = datetime.fromisoformat(
                        prev_dump_data["last_dump_time"]
                    )
                    dump_times = DumpTimes.from_file(dump_paths=dump_paths)
                    instance.dump_times = dump_times

                # Load group-node mapping if present
                if "group_node_mapping" in prev_dump_data:
                    try:
                        from aiida.tools.dumping.mapping import GroupNodeMapping

                        group_node_mapping = GroupNodeMapping.from_dict(
                            prev_dump_data["group_node_mapping"]
                        )
                        instance._group_node_mapping = group_node_mapping
                    except Exception as e:
                        logger.warning(f"Error loading group-node mapping: {e!s}")

                # Load store data
                instance.calculations = cls.deserialize_logs(
                    prev_dump_data.get("calculations", {}), dump_paths=dump_paths
                )
                instance.workflows = cls.deserialize_logs(
                    prev_dump_data.get("workflows", {}), dump_paths=dump_paths
                )
                instance.groups = cls.deserialize_logs(
                    prev_dump_data.get("groups", {}), dump_paths=dump_paths
                )
                instance.data = cls.deserialize_logs(
                    prev_dump_data.get("data", {}), dump_paths=dump_paths
                )

        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Error loading dump log: {e!s}")
            raise

        return instance

    @property
    def group_node_mapping(self) -> GroupNodeMapping:
        """Get the group-node mapping, building it if needed."""
        if self._group_node_mapping is None:
            self._group_node_mapping = self.build_current_group_node_mapping()
        return self._group_node_mapping

    @group_node_mapping.setter
    def group_node_mapping(self, mapping: GroupNodeMapping) -> None:
        """Set the group-node mapping."""
        self._group_node_mapping = mapping

    def register_node_in_group(self, group_uuid: str, node_uuid: str) -> None:
        """Register that a node is part of a group."""
        self.group_node_mapping.add_node_to_group(group_uuid, node_uuid)

    def add_entry(self, store: DumpLogStore, uuid: str, entry: DumpLog) -> None:
        """Add a log entry for a node."""
        store.add_entry(uuid, entry)

    def add_entries(
        self, store: DumpLogStore, uuids: List[str], entries: List[DumpLog]
    ) -> None:
        """Add multiple log entries."""
        for uuid, entry in zip(uuids, entries):
            store.add_entry(uuid, entry)

    def add_symlink(self, store: DumpLogStore, uuid: str, symlink_path: Path) -> bool:
        """Add a symlink path to an existing log entry."""
        entry = store.get_entry(uuid)
        if entry:
            entry.add_symlink(symlink_path)
            return True
        return False

    def del_entry(self, store: DumpLogStore, uuid: str) -> bool:
        """Delete a log entry."""
        return store.del_entry(uuid)

    @property
    def stores(self) -> DumpLogStoreCollection:
        """Retrieve the current state of the log as a dataclass."""
        return DumpLogStoreCollection(
            calculations=self.calculations,
            workflows=self.workflows,
            groups=self.groups,
            data=self.data,
        )

    def save_log(self) -> None:
        """Save the log to a JSON file."""
        log_dict = {
            "calculations": self.serialize_logs(self.calculations),
            "workflows": self.serialize_logs(self.workflows),
            "groups": self.serialize_logs(self.groups),
            "data": self.serialize_logs(self.data),
            "last_dump_time": self.dump_times.current.isoformat(),
        }

        # Save the group-node mapping if available
        if self._group_node_mapping:
            log_dict["group_node_mapping"] = self._group_node_mapping.to_dict()

        with self.dump_paths.log_path.open("w", encoding="utf-8") as f:
            json.dump(log_dict, f, indent=4)

    def serialize_logs(self, container: DumpLogStore) -> Dict:
        """Serialize log entries to a dictionary format."""
        serialized = {}
        for uuid, entry in container.entries.items():
            try:
                # Convert to relative paths for storage
                relative_path = entry.path.relative_to(self.dump_paths.parent)
                relative_symlinks = (
                    [
                        path.relative_to(self.dump_paths.parent)
                        for path in entry.symlinks
                    ]
                    if entry.symlinks
                    else []
                )

                serialized[uuid] = {
                    "path": str(relative_path),
                    "symlinks": (
                        [str(path) for path in relative_symlinks]
                        if relative_symlinks
                        else []
                    ),
                }
            except ValueError:
                # If path is not relative to parent (shouldn't happen)
                logger.warning(
                    f"Path {entry.path} is not relative to {self.dump_paths.parent}"
                )
                serialized[uuid] = entry.to_dict()

        return serialized

    @staticmethod
    def deserialize_logs(category_data: Dict, dump_paths: DumpPaths) -> DumpLogStore:
        """Deserialize log entries from a dictionary format."""
        container = DumpLogStore()

        for uuid, entry_data in category_data.items():
            # Handle old format where entry is just a string path
            if isinstance(entry_data, str):
                container.add_entry(
                    uuid, DumpLog(path=dump_paths.parent / Path(entry_data))
                )
            # Handle new format
            elif isinstance(entry_data, dict) and "path" in entry_data:
                path = dump_paths.parent / Path(entry_data["path"])

                symlinks = []
                if entry_data.get("symlinks"):
                    symlinks = [
                        dump_paths.parent / Path(path)
                        for path in entry_data["symlinks"]
                    ]

                container.add_entry(uuid, DumpLog(path=path, symlinks=symlinks))

        return container

    def get_store_by_uuid(self, uuid: str) -> DumpLogStore:
        """Find the store that contains the given UUID."""
        # Iterate over the fields of the DumpLogStoreCollection dataclass for generality
        for field_ in fields(self.stores):
            store = getattr(self.stores, field_.name)
            if uuid in store.entries:
                return store

        msg = f"No corresponding `DumpLogStore` found for UUID: `{uuid}`."
        raise NotExistent(msg)

    def get_store_by_name(self, name: StoreNameType) -> DumpLogStore:
        """Get the store by its string literal."""
        store_names = [field.name for field in fields(self.stores)]
        if name not in store_names:
            msg = f"Wrong key <{name}> selected. Choose one of {store_names}."
            raise ValueError(msg)

        return getattr(self.stores, name)

    def get_dump_path_by_uuid(self, uuid: str) -> Optional[Path]:
        """Find the path for a node with the given UUID."""
        try:
            current_store = self.get_store_by_uuid(uuid=uuid)
            if uuid in current_store.entries:
                return current_store.entries[uuid].path
            return None
        except NotExistent:
            return None
        except Exception as e:
            logger.warning(f"Error getting dump path for UUID {uuid}: {e!s}")
            return None

    def to_dict(self) -> Dict:
        """Convert the DumpLogger state to a dictionary format."""
        return {
            "calculations": self.calculations.to_dict(),
            "workflows": self.workflows.to_dict(),
            "groups": self.groups.to_dict(),
            "data": self.data.to_dict(),
        }

    def get_store_by_orm(self, orm_type) -> DumpLogStore:
        """Get the appropriate store for a given ORM type."""
        return getattr(self, DumpStoreKeys.from_class(orm_type))

    def update_paths(self, old_str: str, new_str: str) -> Dict:
        """Update all paths across all stores by replacing exact occurrences of old_str with new_str."""
        updates = {}

        # Normalize the strings
        if not old_str.startswith("/"):
            old_str = f"/{old_str}"
        if not new_str.startswith("/"):
            new_str = f"/{new_str}"

        # Update each store
        for store_name in ["calculations", "workflows", "groups", "data"]:
            store: DumpLogStore = getattr(self, store_name)
            count_before = sum(
                1 for uuid, entry in store.entries.items() if old_str in str(entry.path)
            )

            store.update_paths(old_str, new_str)

            count_after = sum(
                1 for uuid, entry in store.entries.items() if new_str in str(entry.path)
            )

            updates[store_name] = {"before": count_before, "after": count_after}

        return updates

    def build_current_group_node_mapping(self) -> GroupNodeMapping:
        """Build a group-node mapping from the current database state."""
        # Import locally to avoid circular imports
        from aiida.tools.dumping.mapping import GroupNodeMapping

        return GroupNodeMapping.build_from_db()

    def verify_group_structure(self) -> Dict:
        """
        Compare the stored group-node mapping with the current database state.

        Returns:
            Dict with verification results
        """
        # Get current mapping from DB
        current_mapping = self.build_current_group_node_mapping()

        # Compare with stored mapping
        return self.group_node_mapping.diff(current_mapping)

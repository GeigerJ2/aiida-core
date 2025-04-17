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
from typing import Dict, List, Optional, Tuple

from aiida.common.log import AIIDA_LOGGER
from aiida.tools.dumping.mapping import GroupNodeMapping
from aiida.tools.dumping.utils.paths import DumpPaths
from aiida.tools.dumping.utils.types import DumpStoreKeys, StoreNameType

logger = AIIDA_LOGGER.getChild("tools.dumping.logger")


# TODO: Possibly dump hierarchy of dumped directory inside json file
# TODO: Currently, json file has only top-level "groups", "workflows", and "calculations"
# TODO: `add_entry` and `add_entries` shouldn't _require_ passing a store, but could be automatically evaluated from the
# type of the first node in the passed entry/entries
# NOTE: Could use DumpLogger also as container for orm.Nodes, that should be dumped
# NOTE: Should DumpLogger be not provided (None), or should it rather just be empty with no entries
# NOTE: Is on `save_log` again the whole history being written to disk? Ideally, this would be incremental
# NOTE: Shouldn't the logger have the `DumpTimes` attached to it??
# NOTE: Problem with general `node_mtime` is that `Group`s don't have an `mtime` attribute

@dataclass
class DumpLog:
    """Represents a single dump log entry."""

    path: Path
    symlinks: List[Path] = field(default_factory=list)
    duplicates: List[Path] = field(default_factory=list)
    # Add mtime? Could be useful for change detection
    # mtime: datetime | None = None

    def to_dict(self) -> dict:
        # Add mtime serialization if included
        return {
            "path": str(self.path),
            "symlinks": [str(path) for path in self.symlinks] if self.symlinks else [],
            'duplicates': [str(path) for path in self.duplicates],

            # 'mtime': self.mtime.isoformat() if self.mtime else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DumpLog":
        symlinks = []
        if data.get("symlinks"):
            symlinks = [Path(path) for path in data["symlinks"]]
        # Add mtime deserialization if included
        # mtime = datetime.fromisoformat(data['mtime']) if data.get('mtime') else None
        duplicates = []
        if data.get('duplicates'):
            duplicates = [Path(path) for path in data['duplicates']]


        return cls(
            path=Path(data["path"]),
            symlinks=symlinks,
            duplicates=duplicates,
            # mtime=mtime,
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

    def add_duplicate(self, path: Path) -> None:
        """Add a duplicate dump path to this log entry."""
        if path not in self.duplicates:
            self.duplicates.append(path)

    def remove_duplicate(self, path: Path) -> bool:
        """Remove a duplicate dump path from this log entry."""
        if path in self.duplicates:
            self.duplicates.remove(path)
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
            if isinstance(entry_data, dict) and "path" in entry_data:
                store.entries[uuid] = DumpLog.from_dict(entry_data)
            elif isinstance(
                entry_data, str
            ):  # Handle old format backward compatibility
                store.entries[uuid] = DumpLog(path=Path(entry_data))
        return store

    def update_paths(self, old_str: str, new_str: str) -> None:
        """Update paths by replacing substrings."""
        # Keep this method as it operates solely on paths within the store
        for uuid, entry in self.entries.items():
            path_str = str(entry.path)
            if old_str in path_str:
                entry.path = Path(path_str.replace(old_str, new_str))
            # Update symlinks
            for i, symlink_path in enumerate(entry.symlinks):
                symlink_str = str(symlink_path)
                if old_str in symlink_str:
                    entry.symlinks[i] = Path(symlink_str.replace(old_str, new_str))
            # Update duplicates
            updated_duplicates = []
            for duplicate_path in entry.duplicates:
                duplicate_str = str(duplicate_path)
                if old_str in duplicate_str:
                    updated_duplicates.append(Path(duplicate_str.replace(old_str, new_str)))
                else:
                    updated_duplicates.append(duplicate_path)
            entry.duplicates = updated_duplicates



@dataclass
class DumpLogStoreCollection:
    """Represents the entire log data."""

    calculations: DumpLogStore = field(default_factory=DumpLogStore)
    workflows: DumpLogStore = field(default_factory=DumpLogStore)
    groups: DumpLogStore = field(default_factory=DumpLogStore)
    data: DumpLogStore = field(default_factory=DumpLogStore)


class DumpLogger:
    """Handles loading, saving, and accessing dump log data."""

    def __init__(
        self,
        dump_paths: DumpPaths,
        stores: DumpLogStoreCollection,
        last_dump_time_str: str | None = None,
    ) -> None:
        """
        Initialize the DumpLogger. Should typically be instantiated via `load`.
        """
        self.dump_paths = dump_paths
        # Stores are now passed in directly
        self.calculations = stores.calculations
        self.workflows = stores.workflows
        self.groups = stores.groups
        self.data = stores.data
        # Store the raw string time from the log
        self._last_dump_time_str = last_dump_time_str

    @staticmethod
    def load(
        dump_paths: DumpPaths,
    ) -> Tuple[DumpLogStoreCollection, GroupNodeMapping | None, str | None]:
        """
        Load log data and mapping from the log file.

        Returns:
            A tuple containing:
                - DumpLogStoreCollection: The loaded stores.
                - GroupNodeMapping | None: The loaded group mapping, or None if not found/error.
                - str | None: The ISO timestamp string of the last dump, or None.
        """
        stores = DumpLogStoreCollection()  # Default empty stores
        group_node_mapping = None
        last_dump_time_str = None

        if not dump_paths.log_path.exists():
            logger.debug(
                f"Log file not found at {dump_paths.log_path}, returning empty log data."
            )
            return stores, group_node_mapping, last_dump_time_str

        try:
            with dump_paths.log_path.open("r", encoding="utf-8") as f:
                prev_dump_data = json.load(f)

            # Load last dump time string
            last_dump_time_str = prev_dump_data.get("last_dump_time")

            # Load group-node mapping if present
            if "group_node_mapping" in prev_dump_data:
                try:
                    group_node_mapping = GroupNodeMapping.from_dict(
                        prev_dump_data["group_node_mapping"]
                    )
                except Exception as e:
                    logger.warning(f"Error loading group-node mapping: {e!s}")

            # Load store data using deserialize_logs helper
            stores.calculations = DumpLogger._deserialize_logs(
                prev_dump_data.get("calculations", {}), dump_paths=dump_paths
            )
            stores.workflows = DumpLogger._deserialize_logs(
                prev_dump_data.get("workflows", {}), dump_paths=dump_paths
            )
            stores.groups = DumpLogger._deserialize_logs(
                prev_dump_data.get("groups", {}), dump_paths=dump_paths
            )
            stores.data = DumpLogger._deserialize_logs(
                prev_dump_data.get("data", {}), dump_paths=dump_paths
            )

        except (json.JSONDecodeError, OSError, ValueError) as e:
            logger.warning(f"Error loading dump log file {dump_paths.log_path}: {e!s}")
            # Return default empty data on error
            return DumpLogStoreCollection(), None, None

        return stores, group_node_mapping, last_dump_time_str

    def get_last_dump_time(self) -> datetime | None:
        """Parse and return the last dump time, if available."""
        if self._last_dump_time_str:
            try:
                return datetime.fromisoformat(self._last_dump_time_str)
            except ValueError:
                logger.warning(
                    f"Could not parse last dump time string: {self._last_dump_time_str}"
                )
        return None

    def add_entry(self, store_key: StoreNameType, uuid: str, entry: DumpLog) -> None:
        """Add a log entry for a node to the specified store."""
        store = self.get_store_by_name(store_key)
        store.add_entry(uuid, entry)

    def del_entry(self, store_key: StoreNameType, uuid: str) -> bool:
        """Delete a log entry from the specified store."""
        store = self.get_store_by_name(store_key)
        return store.del_entry(uuid)

    @property
    def stores_collection(self) -> DumpLogStoreCollection:
        """Retrieve the current state of the log stores as a dataclass."""
        # Corrected: use the instance's stores
        return DumpLogStoreCollection(
            calculations=self.calculations,
            workflows=self.workflows,
            groups=self.groups,
            data=self.data,
        )

    # TODO: This currently requires the dump time as argument, not sure if this is what I want
    def save(
        self, current_dump_time: datetime, group_node_mapping: GroupNodeMapping | None = None
    ) -> None:
        """Save the current log state and mapping to the JSON file."""
        log_dict = {
            # Use the _serialize_logs helper method
            "calculations": self._serialize_logs(self.calculations),
            "workflows": self._serialize_logs(self.workflows),
            "groups": self._serialize_logs(self.groups),
            "data": self._serialize_logs(self.data),
            "last_dump_time": current_dump_time.isoformat(),
        }

        if group_node_mapping:
            log_dict["group_node_mapping"] = group_node_mapping.to_dict()

        try:
            with self.dump_paths.log_path.open("w", encoding="utf-8") as f:
                json.dump(log_dict, f, indent=4)
            logger.debug(f"Dump log saved to {self.dump_paths.log_path}")
        except OSError as e:
            logger.error(
                f"Failed to save dump log to {self.dump_paths.log_path}: {e!s}"
            )

    # Make serialize/deserialize static helpers or private methods
    def _serialize_logs(self, container: DumpLogStore) -> Dict:
        """Serialize log entries to a dictionary format relative to dump parent."""
        serialized = {}
        for uuid, entry in container.entries.items():
            try:
                relative_path = entry.path.relative_to(self.dump_paths.parent)
                relative_symlinks = (
                    [
                        path.relative_to(self.dump_paths.parent)
                        for path in entry.symlinks
                    ]
                    if entry.symlinks
                    else []
                )
                relative_duplicates = (
                    [
                        path.relative_to(self.dump_paths.parent)
                        for path in entry.duplicates
                    ]
                    if entry.duplicates
                    else []
                )
                serialized[uuid] = {
                    "path": str(relative_path),
                    "symlinks": [str(path) for path in relative_symlinks],
                    "duplicates": [str(path) for path in relative_duplicates],
                }
            except ValueError:
                logger.warning(
                    f"Path {entry.path} or its symlinks not relative to {self.dump_paths.parent}. Storing absolute."
                )
                # Fallback to absolute paths if relative fails (should be rare)
                serialized[uuid] = {
                    "path": str(entry.path),
                    "symlinks": [str(path) for path in entry.symlinks],
                }
        return serialized

    @staticmethod
    def _deserialize_logs(category_data: Dict, dump_paths: DumpPaths) -> DumpLogStore:
        """Deserialize log entries, converting relative paths back to absolute."""
        container = DumpLogStore()
        for uuid, entry_data in category_data.items():
            try:
                # Handle new format (dict)
                if isinstance(entry_data, dict) and "path" in entry_data:
                    # Assume paths are stored relative to parent
                    path = dump_paths.parent / Path(entry_data["path"])
                    symlinks = []
                    if entry_data.get("symlinks"):
                        symlinks = [
                            dump_paths.parent / Path(p) for p in entry_data["symlinks"]
                        ]
                    container.add_entry(uuid, DumpLog(path=path, symlinks=symlinks))
                # Handle old format (string path)
                elif isinstance(entry_data, str):
                    path = dump_paths.parent / Path(entry_data)
                    container.add_entry(uuid, DumpLog(path=path))
            except Exception as e:
                logger.warning(f"Failed to deserialize log entry for UUID {uuid}: {e}")
        return container

    # Keep helper methods to find stores/paths based on UUID
    def get_store_by_uuid(self, uuid: str) -> DumpLogStore | None:
        """Find the store that contains the given UUID."""
        stores_coll = self.stores_collection  # Use the property
        for field_ in fields(stores_coll):
            store = getattr(stores_coll, field_.name)
            if uuid in store.entries:
                return store
        # Return None instead of raising NotExistent for easier checking
        logger.debug(f"UUID {uuid} not found in any log store.")
        return None

    def get_store_by_name(self, name: StoreNameType) -> DumpLogStore:
        """Get the store by its string literal name."""
        stores_coll = self.stores_collection  # Use the property
        if hasattr(stores_coll, name):
            return getattr(stores_coll, name)
        else:
            store_names = [field.name for field in fields(stores_coll)]
            msg = f"Wrong store key <{name}> selected. Choose one of {store_names}."
            raise ValueError(msg)

    def get_dump_path_by_uuid(self, uuid: str) -> Optional[Path]:
        """Find the dump path for an entity with the given UUID."""
        store = self.get_store_by_uuid(uuid=uuid)
        if store and uuid in store.entries:
            return store.entries[uuid].path
        return None

    # Keep get_store_by_orm for convenience if needed elsewhere
    def get_store_by_orm(self, orm_type) -> DumpLogStore:
        """Get the appropriate store for a given ORM type using DumpStoreKeys."""
        store_key_str = DumpStoreKeys.from_class(orm_type)
        return self.get_store_by_name(store_key_str)  # Use existing method

    def update_paths(self, old_str: str, new_str: str) -> Dict:
        """Update all paths across all stores by replacing substrings."""
        updates = {}
        # Update each store using its own update_paths method
        for store_name in ["calculations", "workflows", "groups", "data"]:
            store: DumpLogStore = getattr(self, store_name)
            # Store could track changes internally if needed, or just report here
            count_before = sum(
                1 for entry in store.entries.values() if old_str in str(entry.path)
            )
            store.update_paths(old_str, new_str)
            count_after = sum(
                1 for entry in store.entries.values() if new_str in str(entry.path)
            )
            updates[store_name] = {"before": count_before, "after": count_after}
            if count_before > 0:
                logger.debug(
                    f"Updated {count_after} paths in '{store_name}' store replacing '{old_str}' with '{new_str}'."
                )
        return updates


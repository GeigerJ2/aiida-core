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

from aiida.common.exceptions import NotExistent
from aiida.tools.dumping.config import DumpPaths, DumpStoreKeys, DumpTimes
from aiida.tools.dumping.utils import StoreNameType

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

    # TODO: Possibly add `node_type` or something similar here

    path: Path

    def to_dict(self) -> dict:
        return {
            'path': str(self.path),
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'DumpLog':
        return cls(
            path=Path(data['path']),
        )


@dataclass
class DumpLogStore:
    """A store for DumpLog entries, indexed by UUID."""

    entries: dict[str, DumpLog] = field(default_factory=dict)

    # TODO: If I support keeping track of the symlinks, possibly should implement extending them here
    def add_entry(self, uuid: str, entry: DumpLog) -> None:
        """Add a single entry to the container."""
        self.entries[uuid] = entry

    def add_entries(self, entries: dict[str, DumpLog]) -> None:
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

    def get_entry(self, uuid: str) -> DumpLog | None:
        """Retrieve a single entry by UUID."""
        return self.entries.get(uuid)

    def __len__(self) -> int:
        """Return the number of entries in the container."""
        return len(self.entries)

    def __iter__(self):
        """Iterate over all entries."""
        return iter(self.entries.items())

    def to_dict(self) -> dict:
        return {uuid: entry.to_dict() for uuid, entry in self.entries.items()}

    @classmethod
    def from_dict(cls, data: dict) -> 'DumpLogStore':
        store = cls()
        store.entries = {uuid: DumpLog.from_dict(entry) for uuid, entry in data.items()}
        return store

    def update_paths(self, old_str: str, new_str: str) -> None:
        """Update all paths in the store by replacing exact occurrences of old_str with new_str.

        Args:
            old_str: The string to be replaced in paths
            new_str: The replacement string
        """
        if not old_str.startswith('/'):
            old_str = f'/{old_str}'
        if not new_str.startswith('/'):
            new_str = f'/{new_str}'
        for uuid, entry in self.entries.items():
            # Check if old_str exists in the path
            path_str = str(entry.path)
            if old_str in path_str:
                # Create a new path with the replaced string
                new_path = Path(path_str.replace(old_str, new_str))
                entry.path = new_path


@dataclass
class DumpLogStoreCollection:
    """Represents the entire log, with calculations and workflows (will be extended with Data)."""

    calculations: DumpLogStore
    workflows: DumpLogStore
    groups: DumpLogStore
    data: DumpLogStore


class DumpLogger:
    """Main Logger class for data dumping."""

    dump_LOG_FILE: str = '.aiida_dump_log.json'

    def __init__(
        self,
        dump_paths: DumpPaths,
        dump_times: DumpTimes,
        calculations: DumpLogStore | None = None,
        workflows: DumpLogStore | None = None,
        groups: DumpLogStore | None = None,
        data: DumpLogStore | None = None,
        last_dump_time: datetime | None = None,
    ) -> None:
        self.dump_paths = dump_paths
        self.dump_times = dump_times
        self.calculations = calculations or DumpLogStore()
        self.workflows = workflows or DumpLogStore()
        self.groups = groups or DumpLogStore()
        self.data = data or DumpLogStore()
        self.last_dump_time = last_dump_time

    def add_entry(self, store: DumpLogStore, uuid: str, entry: DumpLog) -> None:
        store.add_entry(uuid, entry)

    def add_entries(self, store: DumpLogStore, uuids: list[str], entries: list[DumpLog]) -> None:
        for uuid, entry in zip(uuids, entries):
            store.add_entry(uuid, entry)

    def del_entry(self, store: DumpLogStore, uuid: str) -> bool:
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
            'calculations': self.serialize_logs(self.calculations),
            'workflows': self.serialize_logs(self.workflows),
            'groups': self.serialize_logs(self.groups),
            'data': self.serialize_logs(self.data),
            'last_dump_time': self.dump_times.current.isoformat(),
        }

        with self.dump_paths.log_path.open('w', encoding='utf-8') as f:
            json.dump(log_dict, f, indent=4)

    def serialize_logs(self, container: DumpLogStore) -> dict:
        serialized = {}
        for uuid, entry in container.entries.items():
            relative_path = entry.path.relative_to(self.dump_paths.parent)
            serialized[uuid] = {
                'path': str(relative_path),
            }
        return serialized

    # TODO: Could also convert to normal method, such that I have access to self.dump_paths and can deserialize to
    # absolute Paths
    @staticmethod
    def deserialize_logs(category_data: dict, dump_paths: DumpPaths) -> DumpLogStore:
        container = DumpLogStore()
        for uuid, entry in category_data.items():
            container.add_entry(
                uuid,
                DumpLog(
                    path=dump_paths.parent / Path(entry['path']),
                ),
            )
        return container

    @classmethod
    def from_file(cls, dump_paths: DumpPaths) -> 'DumpLogger':
        """Alternative constructor to load from an existing JSON file."""

        if not dump_paths.log_path.exists():
            dump_times = DumpTimes()
            return cls(dump_paths=dump_paths, dump_times=dump_times)

        try:
            with dump_paths.log_path.open('r', encoding='utf-8') as f:
                prev_dump_data = json.load(f)
                dump_times = DumpTimes.from_file(dump_paths=dump_paths)
                instance = cls(dump_paths=dump_paths, dump_times=dump_times)

            instance.calculations = DumpLogger.deserialize_logs(prev_dump_data['calculations'], dump_paths=dump_paths)
            instance.workflows = DumpLogger.deserialize_logs(prev_dump_data['workflows'], dump_paths=dump_paths)
            instance.groups = DumpLogger.deserialize_logs(prev_dump_data['groups'], dump_paths=dump_paths)
            # instance.data = deserialize_logs(data['data'])

            # Load the last dump time
            if prev_dump_data.get('last_dump_time'):
                instance.last_dump_time = datetime.fromisoformat(prev_dump_data['last_dump_time'])

        except (json.JSONDecodeError, OSError):
            raise

        return instance

    def get_store_by_uuid(self, uuid: str) -> DumpLogStore:
        """Find the store that contains the given UUID."""

        # Iterate over the fields of the DumpLogStoreCollection dataclass for generality
        for field_ in fields(self.stores):
            store = getattr(self.stores, field_.name)
            if uuid in store.entries:
                return store

        msg = f'No corresponding `DumpLogStore` found for UUID: `{uuid}`.'
        raise NotExistent(msg)

    def get_store_by_name(self, name: StoreNameType) -> DumpLogStore:
        """Get the store by its string literal."""

        store_names = [field.name for field in fields(self.stores)]
        if name not in store_names:
            msg = f'Wrong key <{name}> selected. Choose one of {store_names}.'
            raise ValueError(msg)

        return getattr(self.stores, name)

    def get_dump_path_by_uuid(self, uuid: str) -> Path | None:
        """Find the store that contains the given UUID."""
        # Iterate over the fields of the DumpLogStoreCollection dataclass for generality

        try:
            current_store = self.get_store_by_uuid(uuid=uuid)
        except NotExistent as exc:
            raise NotExistent(exc.args[0]) from exc
        try:
            path = current_store.entries[uuid].path
            return path
        except KeyError as exc:
            msg = f'UUID: `{uuid}` not contained in store `{current_store}`.'
            raise KeyError(msg) from exc
        except:
            # For debugging
            raise

    def to_dict(self) -> dict:
        """
        Convert the DumpLogger state to a dictionary format.

        Returns:
            dict: A dictionary representation of the DumpLogger state,
                containing all calculations, workflows, groups, and data entries.
        """

        return {
            'calculations': self.calculations.to_dict(),
            'workflows': self.workflows.to_dict(),
            'groups': self.groups.to_dict(),
            'data': self.data.to_dict(),
        }

    def get_store_by_orm(self, orm_type) -> DumpLogStore:
        return getattr(self, DumpStoreKeys.from_class(orm_type))

    def update_paths(self, old_str: str, new_str: str):
        """Update all paths across all stores by replacing exact occurrences of old_str with new_str.

        This method iterates through all stores (calculations, workflows, groups, data)
        and updates any paths that contain the old_str.

        Args:
            old_str: The string to be replaced in paths
            new_str: The replacement string

        Returns:
            dict: A dictionary with the number of updated paths per store
        """

        # Update each store
        if not old_str.startswith('/'):
            old_str = f'/{old_str}'
        if not new_str.startswith('/'):
            new_str = f'/{new_str}'

        for store_name in ['calculations', 'workflows', 'groups', 'data']:
            store: DumpLogStore = getattr(self, store_name)
            store.update_paths(old_str, new_str)


    def _extract_expected_paths(self) -> dict:
        """
        Extract all expected paths from the log data.

        Args:
            log_data (Dict): Logger data containing UUIDs and paths

        Returns:
            Dict: Mapping of paths to their UUID and entity type
        """
        expected_paths = {}
        for entity_type in ['calculations', 'workflows', 'groups', 'data']:
            for uuid, entry in self.to_dict().get(entity_type, {}).items():
                path = entry.get('path')
                if path:
                    # Convert to Path object and normalize
                    if not isinstance(path, Path):
                        path = Path(path)
                    # Store the expected path with its UUID and type
                    expected_paths[path] = {'uuid': uuid, 'type': entity_type}

        return expected_paths

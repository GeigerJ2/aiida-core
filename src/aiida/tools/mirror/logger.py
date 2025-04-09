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
from aiida.tools.mirror.config import MirrorPaths, MirrorTimes, MirrorStoreKeys
from aiida.tools.mirror.utils import StoreKeyType

# TODO: Possibly mirror hierarchy of mirrored directory inside json file
# TODO: Currently, json file has only top-level "groups", "workflows", and "calculations"
# TODO: `add_entry` and `add_entries` shouldn't _require_ passing a store, but could be automatically evaluated from the
# type of the first node in the passed entry/entries
# NOTE: Could use MirrorLogger also as container for orm.Nodes, that should be mirrored
# NOTE: Should MirrorLogger be not provided (None), or should it rather just be empty with no entries
# NOTE: Is on `save_log` again the whole history being written to disk? Ideally, this would be incremental
# NOTE: Shouldn't the logger have the `MirrorTimes` attached to it??
# NOTE: Problem with general `node_mtime` is that `Group`s don't have an `mtime` attribute


@dataclass
class MirrorLog:
    """Represents a single mirror log entry."""

    # TODO: Possibly add `node_type` or something similar here

    path: Path

    def to_dict(self) -> dict:
        return {
            'path': str(self.path),
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'MirrorLog':
        return cls(
            path=Path(data['path']),
        )


@dataclass
class MirrorLogStore:
    """A store for MirrorLog entries, indexed by UUID."""

    entries: dict[str, MirrorLog] = field(default_factory=dict)

    # TODO: If I support keeping track of the symlinks, possibly should implement extending them here
    def add_entry(self, uuid: str, entry: MirrorLog) -> None:
        """Add a single entry to the container."""
        self.entries[uuid] = entry

    def add_entries(self, entries: dict[str, MirrorLog]) -> None:
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

    def get_entry(self, uuid: str) -> MirrorLog | None:
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
    def from_dict(cls, data: dict) -> 'MirrorLogStore':
        store = cls()
        store.entries = {uuid: MirrorLog.from_dict(entry) for uuid, entry in data.items()}
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
class MirrorLogStoreCollection:
    """Represents the entire log, with calculations and workflows (will be extended with Data)."""

    calculations: MirrorLogStore
    workflows: MirrorLogStore
    groups: MirrorLogStore
    data: MirrorLogStore


class MirrorLogger:
    """Main Logger class for data mirroring."""

    MIRROR_LOG_FILE: str = '.aiida_mirror_log.json'

    def __init__(
        self,
        mirror_paths: MirrorPaths,
        mirror_times: MirrorTimes,
        calculations: MirrorLogStore | None = None,
        workflows: MirrorLogStore | None = None,
        groups: MirrorLogStore | None = None,
        data: MirrorLogStore | None = None,
    ) -> None:
        self.mirror_paths = mirror_paths
        self.mirror_times = mirror_times
        self.calculations = calculations or MirrorLogStore()
        self.workflows = workflows or MirrorLogStore()
        self.groups = groups or MirrorLogStore()
        self.data = data or MirrorLogStore()

    def add_entry(self, store: MirrorLogStore, uuid: str, entry: MirrorLog) -> None:
        store.add_entry(uuid, entry)

    def add_entries(self, store: MirrorLogStore, uuids: list[str], entries: list[MirrorLog]) -> None:
        for uuid, entry in zip(uuids, entries):
            store.add_entry(uuid, entry)

    def del_entry(self, store: MirrorLogStore, uuid: str) -> bool:
        return store.del_entry(uuid)

    @property
    def stores(self) -> MirrorLogStoreCollection:
        """Retrieve the current state of the log as a dataclass."""
        return MirrorLogStoreCollection(
            calculations=self.calculations,
            workflows=self.workflows,
            groups=self.groups,
            data=self.data,
        )

    def save_log(self) -> None:
        """Save the log to a JSON file."""

        log_dict = {
            'calculations': MirrorLogger.serialize_logs(self.calculations),
            'workflows': MirrorLogger.serialize_logs(self.workflows),
            'groups': MirrorLogger.serialize_logs(self.groups),
            'data': MirrorLogger.serialize_logs(self.data),
            'last_mirror_time': self.mirror_times.current.isoformat(),
        }

        with self.mirror_paths.log_path.open('w', encoding='utf-8') as f:
            json.dump(log_dict, f, indent=4)

    @staticmethod
    def serialize_logs(container: MirrorLogStore) -> dict:
        serialized = {}
        for uuid, entry in container.entries.items():
            serialized[uuid] = {
                'path': str(entry.path),
            }
        return serialized

    @staticmethod
    def deserialize_logs(category_data: dict) -> MirrorLogStore:
        container = MirrorLogStore()
        for uuid, entry in category_data.items():
            container.add_entry(
                uuid,
                MirrorLog(
                    path=Path(entry['path']),
                ),
            )
        return container

    @classmethod
    def from_file(cls, mirror_paths: MirrorPaths) -> 'MirrorLogger':
        """Alternative constructor to load from an existing JSON file."""

        if not mirror_paths.log_path.exists():
            mirror_times = MirrorTimes()
            return cls(mirror_paths=mirror_paths, mirror_times=mirror_times)

        try:
            with mirror_paths.log_path.open('r', encoding='utf-8') as f:
                prev_mirror_data = json.load(f)
                mirror_times = MirrorTimes.from_file(mirror_paths=mirror_paths)
                instance = cls(mirror_paths=mirror_paths, mirror_times=mirror_times)

            instance.calculations = MirrorLogger.deserialize_logs(prev_mirror_data['calculations'])
            instance.workflows = MirrorLogger.deserialize_logs(prev_mirror_data['workflows'])
            instance.groups = MirrorLogger.deserialize_logs(prev_mirror_data['groups'])
            # instance.data = deserialize_logs(data['data'])

            # Load the last mirror time
            if prev_mirror_data.get('last_mirror_time'):
                instance.last_mirror_time = datetime.fromisoformat(prev_mirror_data['last_mirror_time'])

        except (json.JSONDecodeError, OSError):
            raise

        return instance

    def get_store_by_uuid(self, uuid: str) -> MirrorLogStore:
        """Find the store that contains the given UUID."""

        # Iterate over the fields of the MirrorLogStoreCollection dataclass for generality
        for field_ in fields(self.stores):
            store = getattr(self.stores, field_.name)
            if uuid in store.entries:
                return store

        msg = f'No corresponding `MirrorLogStore` found for UUID: `{uuid}`.'
        raise NotExistent(msg)

    # FIXME: HERE
    def get_store_by_key(self, key: StoreKeyType) -> MirrorLogStore:
        """Get the store by its string literal."""

        store_names = [field.name for field in fields(self.stores)]
        if key not in store_names:
            msg = f'Wrong key <{key}> selected. Choose one of {store_names}.'
            raise ValueError(msg)

        return getattr(self.stores, key)

    def get_mirror_path_by_uuid(self, uuid: str) -> Path | None:
        """Find the store that contains the given UUID."""
        # Iterate over the fields of the MirrorLogStoreCollection dataclass for generality

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
        Convert the MirrorLogger state to a dictionary format.

        Returns:
            dict: A dictionary representation of the MirrorLogger state,
                containing all calculations, workflows, groups, and data entries.
        """

        return {
            'calculations': self.calculations.to_dict(),
            'workflows': self.workflows.to_dict(),
            'groups': self.groups.to_dict(),
            'data': self.data.to_dict(),
        }

    def get_store_by_orm(self, orm_type) -> MirrorLogStore:
        return getattr(self, MirrorStoreKeys.from_class(orm_type))

    def update_paths(self, old_str: str, new_str: str) -> dict[str, int]:
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
            store: MirrorLogStore = getattr(self, store_name)
            _ = store.update_paths(old_str, new_str)

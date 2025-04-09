###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################
"""Functionality for mirroring of a Collection of AiiDA ORM entities."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from aiida import orm
from aiida.common.exceptions import NotExistent
from aiida.common.log import AIIDA_LOGGER
from aiida.common.progress_reporter import (
    get_progress_reporter,
    set_progress_bar_tqdm,
)
from aiida.tools.mirror.collection import BaseCollectionMirror
from aiida.tools.mirror.config import (
    GroupMirrorConfig,
    MirrorCollectorConfig,
    MirrorMode,
    MirrorPaths,
    MirrorStoreKeys,
    ProcessMirrorConfig,
)
from aiida.tools.mirror.logger import MirrorLog, MirrorLogger, MirrorLogStore
from aiida.tools.mirror.process import ProcessMirror
from aiida.tools.mirror.store import MirrorNodeStore
from aiida.tools.mirror.utils import (
    generate_group_default_mirror_path,
    generate_process_default_mirror_path,
    prepare_mirror_path,
)

logger = AIIDA_LOGGER.getChild('tools.mirror.group')

# NOTE: `load_mirror_logger` could be put in general Parent cparent class
# NOTE: Accessing via `group.nodes` might be nice, keep in mind
# NOTE: Should the `mirror_logger` even be passed as an argument???
# TODO: Don't update the logger with the UUID of a symlinked calculation as keys must be unique
# TODO: Possibly add another `symlink` attribute to `MirrorLog` which can hold a list of symlinks
# TODO: Ignore for now, as I would need to retrieve the list of links, append to it, and assign again
# TODO: Only allow for "pure" sequences of Calculation- or WorkflowNodes, or also mixed?
# TODO: If the latter possibly also have directory creation in the loop


class GroupMirror(BaseCollectionMirror):
    """Class to handle mirroring of a group of AiiDA ORM entities."""

    def __init__(
        self,
        group: orm.Group | None,
        mirror_mode: MirrorMode | None = None,
        mirror_paths: MirrorPaths | None = None,
        mirror_logger: MirrorLogger | None = None,
        config: GroupMirrorConfig | None = None,
        mirror_collector_config: MirrorCollectorConfig | None = None,
        process_mirror_config: ProcessMirrorConfig | None = None,
    ):
        """Initialize the GroupMirror class."""

        if mirror_paths is None:
            default_mirror_path = generate_group_default_mirror_path(group=group)
            mirror_paths = MirrorPaths.from_path(path=Path.cwd() / default_mirror_path)

        # Delete log file if it already exists and in overwrite mode
        if mirror_mode == MirrorMode.OVERWRITE and mirror_paths.log_path.exists():
            mirror_paths.log_path.unlink()

        super().__init__(
            mirror_mode=mirror_mode,
            mirror_paths=mirror_paths,
            mirror_logger=mirror_logger,
            mirror_collector_config=mirror_collector_config,
        )

        self.group = GroupMirror.load_given_group(group)

        self.config = config or GroupMirrorConfig()
        self.process_mirror_config = process_mirror_config or ProcessMirrorConfig()
        # FIXME: This is duplicated/overwritten here because, due to the recursive nature of the Process mirroring
        # FIXME: I need to pass the option to both, the GroupMirror and the ProcessMirror
        self.process_mirror_config.symlink_calcs = self.config.symlink_calcs

    @staticmethod
    def load_given_group(group: orm.Group | str | None) -> orm.Group:
        """Validate the given group identifier.

        :param group: The group identifier to validate.
        :return: Insance of ``orm.Group``.
        :raises NotExistent: If no ``orm.Group`` can be loaded for a given label.
        """

        if isinstance(group, str):
            try:
                return orm.load_group(group)
            # `load_group` raises the corresponding errors
            except NotExistent:
                raise
            except:
                raise

        elif isinstance(group, orm.Group):
            return group

        else:
            # return orm.Group(label='no-group')
            return None

    # staticmethod so I can use it before instantiation of the GroupDumper, as that will need the subpath already
    @staticmethod
    def get_group_subpath(group) -> Path:
        group_entry_point = group.entry_point
        if group_entry_point is None:
            return Path(group.label)

        group_entry_point_name = group_entry_point.name
        if group_entry_point_name == 'core':
            return Path(f'{group.label}')
        if group_entry_point_name == 'core.import':
            return Path('import') / f'{group.label}'

        group_subpath = Path(*group_entry_point_name.split('.'))

        return group_subpath / f'{group.label}'

    def create_symlink_from_store(self, process_uuid: str, store_instance: Any, process_mirror_path: Path) -> bool:
        """Create a symlink from an existing entry in a store to a new path.

        :param process_uuid: The UUID of the process to link
        :param store_instance: The store instance (current_store or other_store)
        :param process_mirror_path: The target path for the symlink
        :return: True if the symlink was created or already exists, False if UUID not in store
        """
        if process_uuid not in store_instance.entries.keys():
            return False

        if not process_mirror_path.exists():
            process_mirror_path.parent.mkdir(exist_ok=True, parents=True)
            try:
                os.symlink(
                    src=store_instance.entries[process_uuid].path,
                    dst=process_mirror_path,
                )
                # TODO: If this works here, call `add_link` to the MirrorLog to extend an existing MirrorLog
            except FileExistsError:
                # For debugging
                raise

        return True

    def mirror_process(
        self,
        process: orm.CalculationNode | orm.WorkflowNode,
        process_type_path: Path,
    ) -> None:
        """Mirror a single process to disk.

        :param process: An AiiDA calculation or workflow node to mirror
        :param process_type_path: Path where processes of this type are stored
        :param process_mirror: The ProcessMirror instance to use
        """
        process_mirror_path = process_type_path / generate_process_default_mirror_path(
            process_node=process, prefix=None
        )

        process_paths = MirrorPaths(
            parent=process_mirror_path.parent,
            child=process_mirror_path.name,
        )

        process_mirror_inst = ProcessMirror(
            process_node=process,
            mirror_mode=self.mirror_mode,
            mirror_paths=process_paths,
            config=self.process_mirror_config,
            mirror_logger=self.mirror_logger,
        )

        if not self.config.symlink_calcs:
            # Case: symlink_duplicates is disabled
            process_mirror_inst.mirror(top_level_caller=False)

        else:
            # Try to create symlink from current_store first
            symlinked = self.create_symlink_from_store(
                process_uuid=process.uuid,
                store_instance=self.current_store,
                process_mirror_path=process_mirror_path,
            )

            # If not found in current_store, try other_store
            if not symlinked:
                symlinked = self.create_symlink_from_store(
                    process_uuid=process.uuid,
                    store_instance=self.other_store,
                    process_mirror_path=process_mirror_path,
                )

            # If not found in either store, create a new mirror
            if not symlinked:
                process_mirror_inst.mirror(top_level_caller=False)

        # This happens regardless of which case was executed
        self.current_store.add_entry(uuid=process.uuid, entry=MirrorLog(path=process_mirror_path))

    def mirror_processes(self, processes: list[orm.CalculationNode] | list[orm.WorkflowNode]) -> None:
        """Dump a list of AiiDA calculations or workflows to disk.

        :param processes: List of AiiDA calculations or workflows from the ``ProcessesToMirrorContainer``.
        """

        if len(processes) == 0:
            return

        # Setup common resources needed for mirroring
        process_type_path = self.mirror_paths.absolute / MirrorStoreKeys.from_instance(node_inst=processes[0])
        process_type_path.mkdir(exist_ok=True, parents=True)

        # NOTE: This seems a bit hacky. Can probably be improved
        current_store_key = MirrorStoreKeys.from_instance(node_inst=next(iter(processes)))
        other_store_key = 'calculations' if current_store_key == 'workflows' else 'workflows'

        current_store = self.mirror_logger.get_store_by_key(key=current_store_key)
        other_store = self.mirror_logger.get_store_by_key(key=other_store_key)

        self.current_store: MirrorLogStore = current_store
        self.other_store: MirrorLogStore = other_store

        set_progress_bar_tqdm()

        # Mirror each process with progress tracking
        with get_progress_reporter()(desc='Mirroring new processes', total=len(processes)) as progress:
            for process in processes:
                self.mirror_process(
                    process=process,
                    process_type_path=process_type_path,
                )
                progress.update()

    def process_store_mirror(self, mirror_store: MirrorNodeStore) -> None:
        """Handle mirroring of different process collections."""

        # First, mirror calculations and then workflows, as sub-calculations of workflows can be symlinked
        for process_type in ('calculations', 'workflows'):
            processes = getattr(mirror_store, process_type)
            if len(processes) > 0:
                msg = f'Mirroring {len(processes)} {process_type}...'
                logger.report(msg)
                self.mirror_processes(processes=processes)
            else:
                if self.group:
                    msg = f'No (new) {process_type} to mirror in group `{self.group.label}`.'
                else:
                    msg = f'No (new) ungrouped {process_type} to mirror.'
                logger.report(msg)

    def mirror(self, top_level_caller: bool = True) -> None:
        """Top-level method that actually performs the mirroring of the AiiDA data for the collection.

        :return: None
        """

        self.mirror_logger = self.set_mirror_logger(mirror_logger=self.mirror_logger)
        self.mirror_collector = self.set_mirror_collector()

        if self.config.delete_missing:
            self.delete()
            # Don't write log, as to not update the `last_mirror_time`
            # If we delete, we don't mirror any other nodes, we _only_ delete
            return

        # NOTE: The problem here is that I want to set the `mirror_logger` on instantiation, but then I only clean the
        # previous directory in the `pre_mirror` step
        # self.pre_mirror(top_level_caller=top_level_caller)
        if top_level_caller:
            # self.pre_mirror(top_level_caller=top_level_caller)
            prepare_mirror_path(
                path_to_validate=self.mirror_paths.absolute,
                mirror_mode=self.mirror_mode,
                safeguard_file=self.mirror_paths.safeguard_path,
                top_level_caller=top_level_caller,
            )

        mirror_node_store: MirrorNodeStore = self.mirror_collector.collect_to_mirror(group=self.group)

        _ = self.process_store_mirror(mirror_store=mirror_node_store)

        # FIXME: This is a small hack to only write an entry into the logger for actual groups
        # and not the `no-group` container
        if self.group:
            self.mirror_logger.stores.groups.add_entry(
                uuid=self.group.uuid,
                entry=MirrorLog(
                    path=self.mirror_paths.absolute,
                ),
            )

        if top_level_caller:
            self.mirror_logger.save_log()

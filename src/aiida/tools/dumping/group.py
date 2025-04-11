###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################
"""Functionality for dumping of a Collection of AiiDA ORM entities."""

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
from aiida.tools.dumping.base import BaseDumper
from aiida.tools.dumping.collection import BaseCollectionDumper
from aiida.tools.dumping.config import (
    GroupDumperConfig,
    DumpCollectorConfig,
    DumpMode,
    DumpPaths,
    DumpStoreKeys,
    ProcessDumperConfig,
)
from aiida.tools.dumping.logger import DumpLog, DumpLogger, DumpLogStore
from aiida.tools.dumping.process import ProcessDump
from aiida.tools.dumping.store import DumpNodeStore
from aiida.tools.dumping.utils import (
    generate_group_default_dump_path,
    generate_process_default_dump_path,
    prepare_dump_path,
)
import shutil

logger = AIIDA_LOGGER.getChild('tools.dump.group')

# NOTE: `load_dump_logger` could be put in general Parent cparent class
# NOTE: Accessing via `group.nodes` might be nice, keep in mind
# NOTE: Should the `dump_logger` even be passed as an argument???
# TODO: Don't update the logger with the UUID of a symlinked calculation as keys must be unique
# TODO: Possibly add another `symlink` attribute to `DumpLog` which can hold a list of symlinks
# TODO: Ignore for now, as I would need to retrieve the list of links, append to it, and assign again
# TODO: Only allow for "pure" sequences of Calculation- or WorkflowNodes, or also mixed?
# TODO: If the latter possibly also have directory creation in the loop


class GroupDumper(BaseCollectionDumper):
    """Class to handle dumping of a group of AiiDA ORM entities."""

    def __init__(
        self,
        group: orm.Group | None,
        dump_mode: DumpMode = DumpMode.INCREMENTAL,
        dump_paths: DumpPaths | None = None,
        dump_logger: DumpLogger | None = None,
        config: GroupDumperConfig | None = None,
        dump_collector_config: DumpCollectorConfig | None = None,
        process_dump_config: ProcessDumperConfig | None = None,
    ):
        """Initialize the GroupDump class."""

        if dump_paths is None:
            default_dump_path = generate_group_default_dump_path(group=group)
            dump_paths = DumpPaths.from_path(path=Path.cwd() / default_dump_path)

        # Delete log file if it already exists and in overwrite mode
        if dump_mode == DumpMode.OVERWRITE and dump_paths.log_path.exists():
            dump_paths.log_path.unlink()

        super().__init__(
            dump_mode=dump_mode,
            dump_paths=dump_paths,
            dump_logger=dump_logger,
            dump_collector_config=dump_collector_config,
        )

        self.group = GroupDumper.load_given_group(group)

        self.config = config or GroupDumperConfig()
        self.process_dump_config = process_dump_config or ProcessDumperConfig()
        # FIXME: This is duplicated/overwritten here because, due to the recursive nature of the Process dumping
        # FIXME: I need to pass the option to both, the GroupDump and the ProcessDump
        self.process_dump_config.symlink_calcs = self.config.symlink_calcs

    @staticmethod
    def load_given_group(group: orm.Group | str | None) -> orm.Group | None:
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
            return None

    @staticmethod
    def load_given_groups(groups: list[orm.Group | str]) -> list[orm.Group]:
        """"""

        return_groups: list[orm.Group] = []
        for group in groups:
            loaded_group = GroupDumper.load_given_group(group=group)
            if loaded_group is None:
                msg = 'Cannot be None'
                raise ValueError(msg)
            else:
                return_groups.append(loaded_group)

        return return_groups

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

    def create_symlink_from_store(self, process_uuid: str, store_instance: Any, process_dump_path: Path) -> bool:
        """Create a symlink from an existing entry in a store to a new path.

        :param process_uuid: The UUID of the process to link
        :param store_instance: The store instance (current_store or other_store)
        :param process_dump_path: The target path for the symlink
        :return: True if the symlink was created or already exists, False if UUID not in store
        """
        if process_uuid not in store_instance.entries.keys():
            return False

        if not process_dump_path.exists():
            process_dump_path.parent.mkdir(exist_ok=True, parents=True)
            try:
                os.symlink(
                    src=store_instance.entries[process_uuid].path,
                    dst=process_dump_path,
                )
                # TODO: If this works here, call `add_link` to the DumpLog to extend an existing DumpLog
            except FileExistsError:
                # For debugging
                raise

        return True

    def dump_process(
        self,
        process: orm.CalculationNode | orm.WorkflowNode,
        process_type_path: Path,
    ) -> None:
        """Dump a single process to disk.

        :param process: An AiiDA calculation or workflow node to dump
        :param process_type_path: Path where processes of this type are stored
        :param process_dump: The ProcessDump instance to use
        """
        process_dump_path = process_type_path / generate_process_default_dump_path(
            process_node=process, prefix=None
        )

        process_paths = DumpPaths(
            parent=process_dump_path.parent,
            child=Path(process_dump_path.name),
        )

        process_dumper = ProcessDump(
            process_node=process,
            dump_mode=self.dump_mode,
            dump_paths=process_paths,
            config=self.process_dump_config,
            dump_logger=self.dump_logger,
        )

        if not self.config.symlink_calcs:
            # Case: symlink_duplicates is disabled
            process_dumper.dump(top_level_caller=False)

        else:
            # Try to create symlink from current_store first
            symlinked = self.create_symlink_from_store(
                process_uuid=process.uuid,
                store_instance=self.current_store,
                process_dump_path=process_dump_path,
            )

            # If not found in current_store, try other_store
            if not symlinked:
                symlinked = self.create_symlink_from_store(
                    process_uuid=process.uuid,
                    store_instance=self.other_store,
                    process_dump_path=process_dump_path,
                )

            # If not found in either store, create a new dump
            if not symlinked:
                process_dumper.dump(top_level_caller=False)

        # This happens regardless of which case was executed
        self.current_store.add_entry(uuid=process.uuid, entry=DumpLog(path=process_dump_path))

    def dump_processes(self, processes: list[orm.CalculationNode] | list[orm.WorkflowNode]) -> None:
        """Dump a list of AiiDA calculations or workflows to disk.

        :param processes: List of AiiDA calculations or workflows from the ``ProcessesToDumpContainer``.
        """

        if len(processes) == 0:
            return

        # Setup common resources needed for dumping
        process_type_path = self.dump_paths.absolute / DumpStoreKeys.from_instance(node_inst=processes[0])
        process_type_path.mkdir(exist_ok=True, parents=True)

        # NOTE: This seems a bit hacky. Can probably be improved
        # Get the store key as a string from the instance
        current_store_key_str = DumpStoreKeys.from_instance(node_inst=next(iter(processes)))

        # Convert string to actual enum members
        current_store_key = DumpStoreKeys(current_store_key_str)
        other_store_key = (
            DumpStoreKeys.CALCULATIONS
            if current_store_key == DumpStoreKeys.WORKFLOWS
            else DumpStoreKeys.WORKFLOWS
        )

        current_store = self.dump_logger.get_store_by_name(name=current_store_key.value)
        other_store = self.dump_logger.get_store_by_name(name=other_store_key.value)

        self.current_store: DumpLogStore = current_store
        self.other_store: DumpLogStore = other_store

        set_progress_bar_tqdm()

        # Dump each process with progress tracking
        with get_progress_reporter()(desc='Dumping new processes', total=len(processes)) as progress:
            for process in processes:
                self.dump_process(
                    process=process,
                    process_type_path=process_type_path,
                )
                progress.update()

    def process_store_dump(self, dump_store: DumpNodeStore) -> None:
        """Handle dumping of different process collections."""

        # First, dump calculations and then workflows, as sub-calculations of workflows can be symlinked
        for process_type in ('calculations', 'workflows'):
            processes = getattr(dump_store, process_type)
            if len(processes) > 0:
                msg = f'Dumping {len(processes)} {process_type}...'
                logger.report(msg)
                self.dump_processes(processes=processes)
            else:
                if self.group is not None:
                    msg = f'No (new) {process_type} to dump in group `{self.group.label}`.'
                else:
                    msg = f'No (new) ungrouped {process_type} to dump.'
                logger.report(msg)

    def dump(self, top_level_caller: bool = True) -> None:
        """Top-level method that actually performs the dumping of the AiiDA data for the collection.

        :return: None
        """

        self.dump_logger = self.set_dump_logger(dump_logger=self.dump_logger)
        self.dump_collector = self.set_dump_collector(dump_logger=self.dump_logger)

        if self.config.delete_missing:
            self.delete()
            # Don't write log, as to not update the `last_dump_time`
            # If we delete, we don't dump any other nodes, we _only_ delete
            return

        # NOTE: The problem here is that I want to set the `dump_logger` on instantiation, but then I only clean the
        # previous directory in the `pre_dump` step
        # self.pre_dump(top_level_caller=top_level_caller)
        if top_level_caller:
            # self.pre_dump(top_level_caller=top_level_caller)
            prepare_dump_path(
                path_to_validate=self.dump_paths.absolute,
                dump_mode=self.dump_mode,
                safeguard_file=self.dump_paths.safeguard_file,
                top_level_caller=top_level_caller,
            )

        dump_node_store: DumpNodeStore = self.dump_collector.collect_to_dump(group=self.group)

        self.process_store_dump(dump_store=dump_node_store)

        # FIXME: This is a small hack to only write an entry into the logger for actual groups
        # and not the `no-group` container
        if self.group is not None:
            self.dump_logger.stores.groups.add_entry(
                uuid=self.group.uuid,
                entry=DumpLog(
                    path=self.dump_paths.absolute,
                ),
            )

        if top_level_caller:
            self.dump_logger.save_log()

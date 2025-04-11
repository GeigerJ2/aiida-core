###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################

# TODO: Possibly use `batch_iter` from aiida.tools.archive.common
# TODO: Add option to just print the resulting directory tree
# No groups selected, dump data which is not part of any group
# If groups selected, however, this data should not also be dumped automatically
# TODO: Maybe populate the `processes_to_dump` property here, even though I don't really need it, as I get the
# TODO: nodes from the specified collection

from __future__ import annotations

import copy
import dataclasses
import shutil
from pathlib import Path
from typing import cast

from aiida import orm
from aiida.common.log import AIIDA_LOGGER
from aiida.manage import load_profile
from aiida.manage.configuration.profile import Profile
from aiida.tools.dumping.collection import BaseCollectionDumper
from aiida.tools.dumping.config import (
    GroupDumperConfig,
    DumpCollectorConfig,
    DumpMode,
    DumpPaths,
    NodeDumpGroupScope,
    ProcessDumperConfig,
    ProfileDumperConfig,
)
from aiida.tools.dumping.group import GroupDumper
from aiida.tools.dumping.logger import DumpLog, DumpLogger
from aiida.tools.dumping.utils import generate_profile_default_dump_path, prepare_dump_path

logger = AIIDA_LOGGER.getChild('tools.dump.profile')


class ProfileDumper(BaseCollectionDumper):
    """Class to handle dumping of the data of an AiiDA profile."""

    def __init__(
        self,
        profile: str | Profile | None = None,
        dump_mode: DumpMode = DumpMode.INCREMENTAL,
        dump_paths: DumpPaths | None = None,
        dump_logger: DumpLogger | None = None,
        # NOTE: Pass config here or instance
        dump_collector_config: DumpCollectorConfig | None = None,
        config: ProfileDumperConfig | None = None,
        process_dump_config: ProcessDumperConfig | None = None,
        groups: list[str | orm.Group] | None = None,
    ):
        """Initialize the ProfileDump."""

        if isinstance(profile, str):
            loaded_profile = load_profile(profile=profile, allow_switch=True)
        elif isinstance(profile, Profile):
            loaded_profile = profile
            pass
        else:
            from aiida.manage import get_manager

            manager = get_manager()
            loaded_profile = cast(Profile, manager.get_profile())

        assert loaded_profile is not None
        self.profile: Profile = loaded_profile

        if dump_paths is None:
            default_dump_path = generate_profile_default_dump_path(self.profile)
            dump_paths = DumpPaths(parent=Path.cwd(), child=default_dump_path)

        super().__init__(
            dump_mode=dump_mode,
            dump_paths=dump_paths,
            dump_logger=dump_logger,
            dump_collector_config=dump_collector_config,
        )

        if groups is not None:
            self.groups = GroupDumper.load_given_groups(groups=groups)
        else:
            self.groups = []

        self.process_dump_config = process_dump_config or ProcessDumperConfig()
        self.config = config or ProfileDumperConfig()

        # Construct `GroupDumpConfig` from options passed via `ProfileDumpConfig`
        # The arguments of `GroupDumpConfig` are a subset of `ProfileDumpConfig`
        self.group_dump_config = GroupDumperConfig(
            **{
                field.name: getattr(self.config, field.name)
                for field in dataclasses.fields(class_or_instance=GroupDumperConfig)
            }
        )

        assert self.dump_logger is not None

    def dump_per_group(self, groups: list[orm.Group]) -> None:
        """Iterate through a list of groups and dump the contained processes in their dedicated directories.

        :param groups: List of ``orm.Group`` entities.
        """

        assert self.dump_logger is not None
        group_store = self.dump_logger.groups

        for group in groups:
            if self.config.organize_by_groups:
                group_subpath = 'groups' / GroupDumper.get_group_subpath(group=group)
            else:
                group_subpath = Path('.')

            dump_paths_group = DumpPaths(parent=self.dump_paths.absolute, child=group_subpath)

            group_dumper = GroupDumper(
                group=group,
                dump_paths=dump_paths_group,
                dump_mode=self.dump_mode,
                process_dump_config=self.process_dump_config,
                config=self.group_dump_config,
                dump_logger=self.dump_logger,
                dump_collector_config=self.dump_collector_config,
            )

            msg = f'Dumping processes in group `{group.label}` for profile `{self.profile.name}`...'
            logger.report(msg)

            group_dumper.dump(top_level_caller=False)
            if dump_paths_group.absolute.exists():
                if not dump_paths_group.safeguard_path.exists():
                    dump_paths_group.safeguard_path.touch()

            group_store.add_entry(
                uuid=group.uuid,
                entry=DumpLog(
                    path=dump_paths_group.absolute,
                ),
            )

    def dump_not_in_any_group(self) -> None:
        """Dump the profile's process data not contained in any group."""

        if self.config.organize_by_groups:
            no_group_subpath = Path('no-group')
        else:
            no_group_subpath = Path('.')

        dump_paths_no_group = DumpPaths(
            parent=self.dump_paths.absolute,
            child=no_group_subpath,
        )

        # See here how to append to the parent and child of DumpPaths
        dump_collector_config_no_group = copy.deepcopy(self.dump_collector_config)
        dump_collector_config_no_group.group_scope = NodeDumpGroupScope.NO_GROUP

        no_group_dumper = GroupDumper(
            dump_paths=dump_paths_no_group,
            group=None,
            dump_mode=self.dump_mode,
            process_dump_config=self.process_dump_config,
            config=self.group_dump_config,
            dump_logger=self.dump_logger,
            dump_collector_config=dump_collector_config_no_group,
        )

        no_group_dumper.dump(top_level_caller=False)
        if dump_paths_no_group.absolute.exists():
            if not dump_paths_no_group.safeguard_path.exists():
                dump_paths_no_group.safeguard_path.touch()

    def dump(self, top_level_caller: bool = True):
        """_summary_

        :param
        """

        # self.dump_logger = self.set_dump_logger(dump_logger=self.dump_logger, top_level_caller=True)
        self.dump_collector = self.set_dump_collector(dump_logger=self.dump_logger)

        if self.config.delete_missing:
            self.delete()
            return

        if self.config.update_groups:
            self.update_groups()
            return

        if top_level_caller:
            prepare_dump_path(
                path_to_validate=self.dump_paths.absolute,
                dump_mode=self.dump_mode,
                safeguard_file=self.dump_paths.safeguard_file,
                top_level_caller=top_level_caller,
            )

        # If `groups` given on construction, dump only data within those groups
        if len(self.groups) > 0:
            self.dump_per_group(groups=self.groups)

        # Without selecting groups, by default, all profile data should be dumped
        # Thus, we obtain all groups in the profile here
        else:
            profile_groups = cast(list[orm.Group], orm.QueryBuilder().append(orm.Group).all(flat=True))
            self.dump_per_group(groups=profile_groups)

            if self.config.also_ungrouped:
                self.dump_not_in_any_group()

        if top_level_caller:
            import ipdb; ipdb.set_trace()
            self.dump_logger.save_log()

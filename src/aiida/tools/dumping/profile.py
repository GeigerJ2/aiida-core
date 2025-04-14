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

"""Enhanced ProfileDumper with robust group verification and update support."""

from __future__ import annotations
import copy
import dataclasses
from pathlib import Path
import shutil
from typing import Any, Dict, List, Optional, cast

from aiida import orm
from aiida.common.log import AIIDA_LOGGER
from aiida.manage import load_profile
from aiida.manage.configuration.profile import Profile
from aiida.tools.dumping.collection import BaseCollectionDumper
from aiida.tools.dumping.config import (
    DumpDbCollectorConfig,
    DumpMode,
    DumpPaths,
    GroupDumperConfig,
    NodeDumpGroupScope,
    ProcessDumperConfig,
    ProfileDumperConfig,
)
from aiida.tools.dumping.group import GroupDumper
from aiida.tools.dumping.group_manager import GroupNodeMappingManager
from aiida.tools.dumping.group_mapping import GroupNodeMapping
from aiida.tools.dumping.group_verify import GroupDumpVerifier
from aiida.tools.dumping.logger import DumpLog, DumpLogger
from aiida.tools.dumping.utils import (
    generate_profile_default_dump_path,
    prepare_dump_path,
)

logger = AIIDA_LOGGER.getChild('tools.dump.profile')


class ProfileDumper(BaseCollectionDumper):
    """Class to handle dumping of the data of an AiiDA profile."""

    def __init__(
        self,
        profile: Optional[str | Profile] = None,
        dump_mode: DumpMode = DumpMode.INCREMENTAL,
        dump_paths: Optional[DumpPaths] = None,
        dump_logger: Optional[DumpLogger] = None,
        dump_collector_config: Optional[DumpDbCollectorConfig] = None,
        config: Optional[ProfileDumperConfig] = None,
        process_dump_config: Optional[ProcessDumperConfig] = None,
        groups: Optional[List[str | orm.Group]] = None,
    ):
        """Initialize the ProfileDumper."""
        # Load and set profile
        self.profile = self._load_profile(profile)

        # Set default paths if not provided
        if dump_paths is None:
            default_dump_path = generate_profile_default_dump_path(self.profile)
            dump_paths = DumpPaths(parent=Path.cwd(), child=default_dump_path)

        super().__init__(
            dump_mode=dump_mode,
            dump_paths=dump_paths,
            dump_logger=dump_logger,
            dump_collector_config=dump_collector_config,
        )

        # Load specified groups or empty list
        if groups is not None:
            self.groups = GroupDumper.load_given_groups(groups=groups)
        else:
            self.groups = []

        # Configuration
        self.process_dump_config = process_dump_config or ProcessDumperConfig()
        self.config = config or ProfileDumperConfig()

        # Construct GroupDumpConfig from ProfileDumpConfig
        self.group_dump_config = GroupDumperConfig(
            **{
                field.name: getattr(self.config, field.name)
                for field in dataclasses.fields(class_or_instance=GroupDumperConfig)
            }
        )

        # Ensure dump_logger is initialized
        assert self.dump_logger is not None

        # Initialize the group mapping manager
        self.group_mapping_manager = GroupNodeMappingManager(self.dump_logger)

    def _load_profile(self, profile: Optional[str | Profile]) -> Profile:
        """Load the AiiDA profile from string or Profile object."""
        if isinstance(profile, str):
            loaded_profile = load_profile(profile=profile, allow_switch=True)
        elif isinstance(profile, Profile):
            loaded_profile = profile
        else:
            from aiida.manage import get_manager
            manager = get_manager()
            loaded_profile = cast(Profile, manager.get_profile())

        assert loaded_profile is not None
        return loaded_profile

    def dump_per_group(self, groups: List[orm.Group]) -> None:
        """Dump processes for each group in their dedicated directories."""
        assert self.dump_logger is not None
        group_store = self.dump_logger.groups

        for group in groups:
            # Set up group path
            if self.config.organize_by_groups:
                group_subpath = Path('groups') / GroupDumper.get_group_subpath(group=group)
            else:
                group_subpath = Path('.')

            dump_paths_group = DumpPaths(parent=self.dump_paths.absolute, child=group_subpath)

            # Create group dumper
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

            # Perform the actual dump
            group_dumper.dump(top_level_caller=False)

            # Ensure the safeguard file exists
            if dump_paths_group.absolute.exists():
                if not dump_paths_group.safeguard_path.exists():
                    dump_paths_group.safeguard_path.touch()

            # Add entry to the group store
            group_store.add_entry(
                uuid=group.uuid,
                entry=DumpLog(
                    path=dump_paths_group.absolute,
                ),
            )

            # Verify and update group structure if needed
            dump_verifier = GroupDumpVerifier(
                group=group_dumper.group,
                dump_paths=group_dumper.dump_paths,
                dump_logger=group_dumper.dump_logger
            )

            # Get verification results
            verification_result = dump_verifier.verify_group_nodes()

            # If validation failed and updates are enabled, update the group structure
            if not verification_result['validation_passed'] and self.config.update_groups:
                msg = f"Group structure verification for {group.label} failed - updating..."
                logger.report(msg)
                dump_verifier.update_group_structure()
            elif not verification_result['validation_passed']:
                msg = f"Group structure verification for {group.label} failed. Use --update-groups to fix."
                logger.report(msg)

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

        # Configure for ungrouped nodes
        dump_collector_config_no_group = copy.deepcopy(self.dump_collector_config)
        dump_collector_config_no_group.group_scope = NodeDumpGroupScope.NO_GROUP

        # Create group dumper for nodes not in any group
        no_group_dumper = GroupDumper(
            dump_paths=dump_paths_no_group,
            group=None,
            dump_mode=self.dump_mode,
            process_dump_config=self.process_dump_config,
            config=self.group_dump_config,
            dump_logger=self.dump_logger,
            dump_collector_config=dump_collector_config_no_group,
        )

        # Perform the dump
        no_group_dumper.dump(top_level_caller=False)

        # Ensure the safeguard file exists
        if dump_paths_no_group.absolute.exists():
            if not dump_paths_no_group.safeguard_path.exists():
                dump_paths_no_group.safeguard_path.touch()

    def update_groups(self) -> None:
        """Update directory structure based on group changes."""
        logger.report("Updating groups based on the current database state...")

        # Update the group mapping
        self.group_mapping_manager.load_mapping()
        diff_result = self.group_mapping_manager.compare_mappings()

        # If there are no changes, return early
        if not diff_result['deleted_groups'] and not diff_result['modified_groups'] and not diff_result['new_groups']:
            logger.report("No group changes detected. Directory structure is up to date.")
            return

        # Print summary of changes
        if diff_result['deleted_groups']:
            logger.report(f"Found {len(diff_result['deleted_groups'])} deleted groups")
        if diff_result['new_groups']:
            logger.report(f"Found {len(diff_result['new_groups'])} new groups")
        if diff_result['modified_groups']:
            logger.report(f"Found {len(diff_result['modified_groups'])} modified groups")

        # Update the directory structure
        self.group_mapping_manager.handle_group_updates(diff_result)

        # Update group labels (in case they changed)
        self.group_mapping_manager.update_group_labels()

        # Save the updated mapping and log
        self.group_mapping_manager.save_mapping()
        self.dump_logger.save_log()

        logger.report("Group update completed successfully")

    def dump(self, top_level_caller: bool = True):
        """Perform the main dump operation."""

        # The order of operations should be:
        # 1. Verify the group-node mapping and update the directory and previous log -> This means dumping nodes that
        #    were newly added to a group, even though they are not new themselves:
        # If, previously, no ungrouped nodes were dumped, these should be picked up by the collector -> Should check for
        # existence in the log json (first, if not there, dump), and secondly after  last mirror time. If either is
        # The first condition is stricter than the second, as strictly removing nodes based on dump_time might exclude
        # nodes that were not dumped bc they were ungrouped, and which were then added to a group (this should be picked
        # up by the GroupNodeMapping, actually)
        # 2. Obtain all newly created nodes from the DB and mirror them
        # 3. Check for deleted groups and remove those
        # (if only group deleted, also output directory of this group is deleted, removing also the sub-nodes, as those
        # are now ungrouped in the AiiDA DB)
        # 4. Now, if the option is selected, retrieve ungrouped nodes from the DB

        # Initialize logger and collector
        self.dump_logger = self.set_dump_logger(dump_logger=self.dump_logger, top_level_caller=True)
        self.dump_collector = self.set_dump_collector(dump_logger=self.dump_logger)

        # Handle special operations
        if self.config.delete_missing:
            self.delete()
            return

        # Prepare output directory for the dump
        if top_level_caller:
            prepare_dump_path(
                path_to_validate=self.dump_paths.absolute,
                dump_mode=self.dump_mode,
                safeguard_file=self.dump_paths.safeguard_file,
                top_level_caller=top_level_caller,
            )

        # Dump by groups if specified
        if len(self.groups) > 0:
            self.dump_per_group(groups=self.groups)
        else:
            # Dump all groups in the profile
            profile_groups = cast(List[orm.Group], orm.QueryBuilder().append(orm.Group).all(flat=True))
            self.dump_per_group(groups=profile_groups)

            # Dump ungrouped nodes if requested
            if self.config.also_ungrouped:
                self.dump_not_in_any_group()

        # if self.config.update_groups:
        if True:
            self.update_groups()
            # return

        # Save the log file
        if top_level_caller:
            self.dump_logger.save_log()

# from __future__ import annotations

# import copy
# import dataclasses
# import shutil
# from pathlib import Path
# from typing import cast

# from aiida import orm
# from aiida.common.log import AIIDA_LOGGER
# from aiida.manage import load_profile
# from aiida.manage.configuration.profile import Profile
# from aiida.tools.dumping.collection import BaseCollectionDumper
# from aiida.tools.dumping.config import (
#     GroupDumperConfig,
#     DumpCollectorConfig,
#     DumpMode,
#     DumpPaths,
#     NodeDumpGroupScope,
#     ProcessDumperConfig,
#     ProfileDumperConfig,
# )
# from aiida.tools.dumping.group import GroupDumper
# from aiida.tools.dumping.group_verify import GroupDumpVerifier
# from aiida.tools.dumping.logger import DumpLog, DumpLogger
# from aiida.tools.dumping.utils import generate_profile_default_dump_path, prepare_dump_path

# logger = AIIDA_LOGGER.getChild('tools.dumping.profile')


# class ProfileDumper(BaseCollectionDumper):
#     """Class to handle dumping of the data of an AiiDA profile."""

#     def __init__(
#         self,
#         profile: str | Profile | None = None,
#         dump_mode: DumpMode = DumpMode.INCREMENTAL,
#         dump_paths: DumpPaths | None = None,
#         dump_logger: DumpLogger | None = None,
#         # NOTE: Pass config here or instance
#         dump_collector_config: DumpCollectorConfig | None = None,
#         config: ProfileDumperConfig | None = None,
#         process_dump_config: ProcessDumperConfig | None = None,
#         groups: list[str | orm.Group] | None = None,
#     ):
#         """Initialize the ProfileDump."""

#         if isinstance(profile, str):
#             loaded_profile = load_profile(profile=profile, allow_switch=True)
#         elif isinstance(profile, Profile):
#             loaded_profile = profile
#             pass
#         else:
#             from aiida.manage import get_manager

#             manager = get_manager()
#             loaded_profile = cast(Profile, manager.get_profile())

#         assert loaded_profile is not None
#         self.profile: Profile = loaded_profile

#         if dump_paths is None:
#             default_dump_path = generate_profile_default_dump_path(self.profile)
#             dump_paths = DumpPaths(parent=Path.cwd(), child=default_dump_path)

#         super().__init__(
#             dump_mode=dump_mode,
#             dump_paths=dump_paths,
#             dump_logger=dump_logger,
#             dump_collector_config=dump_collector_config,
#         )

#         if groups is not None:
#             self.groups = GroupDumper.load_given_groups(groups=groups)
#         else:
#             self.groups = []

#         self.process_dump_config = process_dump_config or ProcessDumperConfig()
#         self.config = config or ProfileDumperConfig()

#         # Construct `GroupDumpConfig` from options passed via `ProfileDumpConfig`
#         # The arguments of `GroupDumpConfig` are a subset of `ProfileDumpConfig`
#         self.group_dump_config = GroupDumperConfig(
#             **{
#                 field.name: getattr(self.config, field.name)
#                 for field in dataclasses.fields(class_or_instance=GroupDumperConfig)
#             }
#         )

#         assert self.dump_logger is not None

#     def dump_per_group(self, groups: list[orm.Group]) -> None:
#         """Iterate through a list of groups and dump the contained processes in their dedicated directories.

#         :param groups: List of ``orm.Group`` entities.
#         """

#         assert self.dump_logger is not None
#         group_store = self.dump_logger.groups

#         for group in groups:
#             if self.config.organize_by_groups:
#                 group_subpath = 'groups' / GroupDumper.get_group_subpath(group=group)
#             else:
#                 group_subpath = Path('.')

#             dump_paths_group = DumpPaths(parent=self.dump_paths.absolute, child=group_subpath)

#             group_dumper = GroupDumper(
#                 group=group,
#                 dump_paths=dump_paths_group,
#                 dump_mode=self.dump_mode,
#                 process_dump_config=self.process_dump_config,
#                 config=self.group_dump_config,
#                 dump_logger=self.dump_logger,
#                 dump_collector_config=self.dump_collector_config,
#             )

#             msg = f'Dumping processes in group `{group.label}` for profile `{self.profile.name}`...'
#             logger.report(msg)

#             group_dumper.dump(top_level_caller=False)

#             dump_verifyer = GroupDumpVerifier(
#                 group=group_dumper.group, dump_paths=group_dumper.dump_paths, dump_logger=group_dumper.dump_logger
#             )
#             verification_result = dump_verifyer.verify_group_nodes()

#             if not verification_result['validation_passed']:
#                 if self.config.update_groups:
#                     # Implement the logic to update the group structure
#                     self.handle_group_updates(verification_result, group_dumper)

#                 # Log the verification status
#                 logger.report(
#                     f"Group structure verification for {group.label}: "
#                     f"{'PASSED' if verification_result['validation_passed'] else 'FAILED'}"
#                 )

#             if dump_paths_group.absolute.exists():
#                 if not dump_paths_group.safeguard_path.exists():
#                     dump_paths_group.safeguard_path.touch()

#             group_store.add_entry(
#                 uuid=group.uuid,
#                 entry=DumpLog(
#                     path=dump_paths_group.absolute,
#                 ),
#             )

#             dump_verifyer = GroupDumpVerifier(
#                 group=group_dumper.group, dump_paths=group_dumper.dump_paths, dump_logger=group_dumper.dump_logger
#             )

#             import ipdb

#             ipdb.set_trace()
#             dump_verifyer.verify_group_nodes()

#     def dump_not_in_any_group(self) -> None:
#         """Dump the profile's process data not contained in any group."""

#         if self.config.organize_by_groups:
#             no_group_subpath = Path('no-group')
#         else:
#             no_group_subpath = Path('.')

#         dump_paths_no_group = DumpPaths(
#             parent=self.dump_paths.absolute,
#             child=no_group_subpath,
#         )

#         # See here how to append to the parent and child of DumpPaths
#         dump_collector_config_no_group = copy.deepcopy(self.dump_collector_config)
#         dump_collector_config_no_group.group_scope = NodeDumpGroupScope.NO_GROUP

#         no_group_dumper = GroupDumper(
#             dump_paths=dump_paths_no_group,
#             group=None,
#             dump_mode=self.dump_mode,
#             process_dump_config=self.process_dump_config,
#             config=self.group_dump_config,
#             dump_logger=self.dump_logger,
#             dump_collector_config=dump_collector_config_no_group,
#         )

#         no_group_dumper.dump(top_level_caller=False)
#         if dump_paths_no_group.absolute.exists():
#             if not dump_paths_no_group.safeguard_path.exists():
#                 dump_paths_no_group.safeguard_path.touch()

#     def dump(self, top_level_caller: bool = True):
#         """_summary_

#         :param
#         """

#         # self.dump_logger = self.set_dump_logger(dump_logger=self.dump_logger, top_level_caller=True)
#         self.dump_collector = self.set_dump_collector(dump_logger=self.dump_logger)

#         if self.config.delete_missing:
#             self.delete()
#             return

#         if self.config.update_groups:
#             self.update_groups()
#             return

#         if top_level_caller:
#             prepare_dump_path(
#                 path_to_validate=self.dump_paths.absolute,
#                 dump_mode=self.dump_mode,
#                 safeguard_file=self.dump_paths.safeguard_file,
#                 top_level_caller=top_level_caller,
#             )

#         # If `groups` given on construction, dump only data within those groups
#         if len(self.groups) > 0:
#             self.dump_per_group(groups=self.groups)

#         # Without selecting groups, by default, all profile data should be dumped
#         # Thus, we obtain all groups in the profile here
#         else:
#             profile_groups = cast(list[orm.Group], orm.QueryBuilder().append(orm.Group).all(flat=True))
#             self.dump_per_group(groups=profile_groups)

#             if self.config.also_ungrouped:
#                 self.dump_not_in_any_group()

#         if top_level_caller:
#             self.dump_logger.save_log()

#     def handle_group_updates(self, verification_result, group_dumper):

#         """Handle necessary updates based on group verification results."""
#         if verification_result['group_changes']['modified_groups']:
#             logger.report(f"Updating modified groups...")

#             # Update entries in the dump logger
#             for group_info in verification_result['group_changes']['modified_groups']:
#                 group_uuid = group_info.get('uuid')

#                 # Update the nodes in the dump directories
#                 for node_uuid in verification_result['node_changes']['added_to_groups'].get(group_uuid, []):
#                     # Logic to add the node to the group's dump directory
#                     pass

#                 for node_uuid in verification_result['node_changes']['removed_from_groups'].get(group_uuid, []):
#                     # Logic to remove the node from the group's dump directory
#                     pass

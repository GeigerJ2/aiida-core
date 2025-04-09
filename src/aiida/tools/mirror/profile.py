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
# No groups selected, mirror data which is not part of any group
# If groups selected, however, this data should not also be mirrored automatically
# TODO: Maybe populate the `processes_to_mirror` property here, even though I don't really need it, as I get the
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
from aiida.tools.mirror.collection import BaseCollectionMirror
from aiida.tools.mirror.config import (
    GroupMirrorConfig,
    MirrorCollectorConfig,
    MirrorMode,
    MirrorPaths,
    NodeMirrorGroupScope,
    ProcessMirrorConfig,
    ProfileMirrorConfig,
)
from aiida.tools.mirror.group import GroupMirror
from aiida.tools.mirror.logger import MirrorLog, MirrorLogger
from aiida.tools.mirror.utils import generate_profile_default_mirror_path, prepare_mirror_path

logger = AIIDA_LOGGER.getChild('tools.mirror.profile')


class ProfileMirror(BaseCollectionMirror):
    """Class to handle mirroring of the data of an AiiDA profile."""

    def __init__(
        self,
        profile: str | Profile | None = None,
        mirror_mode: MirrorMode = MirrorMode.INCREMENTAL,
        mirror_paths: MirrorPaths | None = None,
        mirror_logger: MirrorLogger | None = None,
        # NOTE: Pass config here or instance
        mirror_collector_config: MirrorCollectorConfig | None = None,
        config: ProfileMirrorConfig | None = None,
        process_mirror_config: ProcessMirrorConfig | None = None,
        groups: list[str | orm.Group] | None = None,
    ):
        """Initialize the ProfileMirror."""

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

        if mirror_paths is None:
            default_mirror_path = generate_profile_default_mirror_path(self.profile)
            mirror_paths = MirrorPaths(parent=Path.cwd(), child=default_mirror_path)

        super().__init__(
            mirror_mode=mirror_mode,
            mirror_paths=mirror_paths,
            mirror_logger=mirror_logger,
            mirror_collector_config=mirror_collector_config,
        )

        if groups is not None:
            self.groups = GroupMirror.load_given_groups(groups=groups)
        else:
            self.groups = []

        self.process_mirror_config = process_mirror_config or ProcessMirrorConfig()
        self.config = config or ProfileMirrorConfig()

        # Construct `GroupMirrorConfig` from options passed via `ProfileMirrorConfig`
        # The arguments of `GroupMirrorConfig` are a subset of `ProfileMirrorConfig`
        self.group_mirror_config = GroupMirrorConfig(
            **{
                field.name: getattr(self.config, field.name)
                for field in dataclasses.fields(class_or_instance=GroupMirrorConfig)
            }
        )

        assert self.mirror_logger is not None

    def mirror_per_group(self, groups: list[orm.Group]) -> None:
        """Iterate through a list of groups and mirror the contained processes in their dedicated directories.

        :param groups: List of ``orm.Group`` entities.
        """

        assert self.mirror_logger is not None
        group_store = self.mirror_logger.groups

        for group in groups:
            if self.config.organize_by_groups:
                group_subpath = 'groups' / GroupMirror.get_group_subpath(group=group)
            else:
                group_subpath = Path('.')

            mirror_paths_group = MirrorPaths(parent=self.mirror_paths.absolute, child=group_subpath)

            group_mirror_inst = GroupMirror(
                group=group,
                mirror_paths=mirror_paths_group,
                mirror_mode=self.mirror_mode,
                process_mirror_config=self.process_mirror_config,
                config=self.group_mirror_config,
                mirror_logger=self.mirror_logger,
                mirror_collector_config=self.mirror_collector_config,
            )

            msg = f'Mirroring processes in group `{group.label}` for profile `{self.profile.name}`...'
            logger.report(msg)

            group_mirror_inst.mirror(top_level_caller=False)
            if mirror_paths_group.absolute.exists():
                if not mirror_paths_group.safeguard_path.exists():
                    mirror_paths_group.safeguard_path.touch()

            group_store.add_entry(
                uuid=group.uuid,
                entry=MirrorLog(
                    path=mirror_paths_group.absolute,
                ),
            )

    def mirror_not_in_any_group(self) -> None:
        """Mirror the profile's process data not contained in any group."""

        if self.config.organize_by_groups:
            no_group_subpath = Path('no-group')
        else:
            no_group_subpath = Path('.')

        mirror_paths_no_group = MirrorPaths(
            parent=self.mirror_paths.absolute,
            child=no_group_subpath,
        )

        # See here how to append to the parent and child of MirrorPaths
        mirror_collector_config_no_group = copy.deepcopy(self.mirror_collector_config)
        mirror_collector_config_no_group.group_scope = NodeMirrorGroupScope.NO_GROUP

        no_group_mirror_inst = GroupMirror(
            mirror_paths=mirror_paths_no_group,
            group=None,
            mirror_mode=self.mirror_mode,
            process_mirror_config=self.process_mirror_config,
            config=self.group_mirror_config,
            mirror_logger=self.mirror_logger,
            mirror_collector_config=mirror_collector_config_no_group,
        )

        no_group_mirror_inst.mirror(top_level_caller=False)
        if mirror_paths_no_group.absolute.exists():
            if not mirror_paths_no_group.safeguard_path.exists():
                mirror_paths_no_group.safeguard_path.touch()

    def mirror(self, top_level_caller: bool = True):
        """_summary_

        :param
        """

        # self.mirror_logger = self.set_mirror_logger(mirror_logger=self.mirror_logger, top_level_caller=True)
        self.mirror_collector = self.set_mirror_collector(mirror_logger=self.mirror_logger)

        if self.config.delete_missing:
            self.delete()
            return

        if self.config.update_groups:
            self.update_groups()
            return

        if top_level_caller:
            prepare_mirror_path(
                path_to_validate=self.mirror_paths.absolute,
                mirror_mode=self.mirror_mode,
                safeguard_file=self.mirror_paths.safeguard_file,
                top_level_caller=top_level_caller,
            )

        # If `groups` given on construction, mirror only data within those groups
        if len(self.groups) > 0:
            self.mirror_per_group(groups=self.groups)

        # Without selecting groups, by default, all profile data should be mirrored
        # Thus, we obtain all groups in the profile here
        else:
            profile_groups = cast(list[orm.Group], orm.QueryBuilder().append(orm.Group).all(flat=True))
            self.mirror_per_group(groups=profile_groups)

            if self.config.also_ungrouped:
                self.mirror_not_in_any_group()

        if top_level_caller:
            self.mirror_logger.save_log()

    def update_groups(self):
        mirror_logger = self.mirror_logger
        assert mirror_logger is not None

        old_mirror_logger_dict = mirror_logger.to_dict()

        # Get the list of mirrored group UUIDs
        mirrored_group_uuids = list(mirror_logger.groups.entries.keys())

        # Create mappings of group UUIDs to old paths and new labels
        old_paths = [entry.path for entry in mirror_logger.groups.entries.values()]
        new_labels = [orm.load_group(uuid=uuid).label for uuid in mirrored_group_uuids]

        # Update paths in mirror logger for changed labels
        for old_path, new_label in zip(old_paths, new_labels):
            old_label = old_path.name
            if old_label != new_label:
                mirror_logger.update_paths(old_str=old_label, new_str=new_label)
                logger.report(f'Applied group relabelling `{old_label}` -> `{new_label}` in mirror directory and log.')

        # Get updated paths
        new_mirror_logger_dict = mirror_logger.to_dict()

        # Track paths that have already been moved to avoid duplicate moves
        moved_paths = set()

        # Move files for all entity types
        for entity_type in ('groups', 'workflows', 'calculations', 'data'):
            old_store = old_mirror_logger_dict[entity_type]
            new_store = new_mirror_logger_dict[entity_type]

            for uuid, entry in old_store.items():
                old_path = entry['path']
                new_path = new_store[uuid]['path']

                if old_path != new_path and old_path not in moved_paths:
                    parent_dir = Path(new_path).parent

                    # Create parent directory if it doesn't exist
                    if not parent_dir.exists():
                        parent_dir.mkdir(parents=True, exist_ok=True)

                    try:
                        shutil.move(str(old_path), str(new_path))
                        moved_paths.add(old_path)

                        # Update the old store to reflect the completed move
                        old_store[uuid]['path'] = new_path
                    except FileNotFoundError:
                        # Path might have been implicitly moved when a parent directory was moved
                        continue

        # Save the updated log
        mirror_logger.save_log()

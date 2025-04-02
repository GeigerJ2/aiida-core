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
from datetime import datetime
from pathlib import Path
from typing import cast

from aiida import orm
from aiida.common.log import AIIDA_LOGGER
from aiida.manage import load_profile
from aiida.manage.configuration.profile import Profile
from aiida.tools.mirror.collection import BaseCollectionMirror
from aiida.tools.mirror.collector import MirrorNodeContainer
from aiida.tools.mirror.config import (
    GroupMirrorConfig,
    MirrorMode,
    MirrorPaths,
    NodeCollectorConfig,
    NodeMirrorGroupScope,
    ProcessMirrorConfig,
    ProfileMirrorConfig,
)
from aiida.tools.mirror.group import GroupMirror
from aiida.tools.mirror.logger import MirrorLog, MirrorLogger
from aiida.tools.mirror.utils import generate_profile_default_mirror_path, safe_delete_dir

logger = AIIDA_LOGGER.getChild("tools.mirror.profile")


class ProfileMirror(BaseCollectionMirror):
    """Class to handle mirroring of the data of an AiiDA profile."""

    def __init__(
        self,
        profile: str | Profile | None = None,
        mirror_mode: MirrorMode = MirrorMode.INCREMENTAL,
        mirror_paths: MirrorPaths | None = None,
        last_mirror_time: datetime | None = None,
        mirror_logger: MirrorLogger | None = None,
        config: ProfileMirrorConfig | None = None,
        node_collector_config: NodeCollectorConfig | None = None,
        process_mirror_config: ProcessMirrorConfig | None = None,
        groups: list[str] | list[orm.Group] | None = None,
    ):
        """Initialize the ProfileMirror."""

        if mirror_paths is None:
            default_mirror_path = generate_profile_default_mirror_path()
            mirror_paths = MirrorPaths(parent=Path.cwd(), child=default_mirror_path)

        # The problem is that the mirror_logger is not a singleton, but is passed around and attached to various
        # classes. During mirroring with the `overwrite` option, it gets reset for every `ProcessMirror` instantiation.
        # However, the pre_mirror is done before instantiation, so running the mirror with `overwrite` still has the
        # `dump_logger` from the JSON file of the previous run attached...
        # Solve by deleting the log file in overwrite mode here, or making pre_mirror a `classmethod` that's executed
        # before instantiation??
        # ! NOTE: THIS IS A HACK
        # import ipdb; ipdb.set_trace()
        if mirror_mode == MirrorMode.OVERWRITE and mirror_paths.logger_path.exists():
            mirror_paths.logger_path.unlink()

        super().__init__(
            mirror_mode=mirror_mode,
            mirror_paths=mirror_paths,
            last_mirror_time=last_mirror_time,
            mirror_logger=mirror_logger,
            node_collector_config=node_collector_config,
        )

        if not isinstance(profile, Profile):
            profile: Profile = load_profile(profile=profile, allow_switch=True)
        self.profile = profile

        if groups is not None:
            self.groups = [GroupMirror.load_given_group(group=g) for g in groups]
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

        # Unpack arguments for easier access
        # self.symlink_duplicates = self.config.symlink_calcs
        # self.delete_missing = self.config.delete_missing
        # self.organize_by_groups = self.config.organize_by_groups
        # self.only_groups = self.config.only_groups

        # self.group_container_mapping: dict[orm.Group, MirrorNodeContainer] = {}

    def _mirror_per_group(self, groups: list[orm.Group]) -> None:
        """Iterate through a list of groups and mirror the contained processes in their dedicated directories.

        :param groups: List of ``orm.Group`` entities.
        """

        group_store = self.mirror_logger.groups

        for group in groups:
            if self.config.organize_by_groups:
                group_subpath = "groups" / GroupMirror.get_group_subpath(group=group)
            else:
                group_subpath = Path(".")

            mirror_paths_group = MirrorPaths(
                parent=self.mirror_paths.absolute, child=group_subpath
            )

            group_mirror_inst = GroupMirror(
                group=group,
                mirror_paths=mirror_paths_group,
                mirror_mode=self.mirror_mode,
                process_mirror_config=self.process_mirror_config,
                config=self.group_mirror_config,
                mirror_logger=self.mirror_logger,
                node_collector_config=self.node_collector_config
            )

            msg = f"Mirroring processes in group `{group.label}` for profile `{self.profile.name}`..."
            logger.report(msg)

            group_mirror_inst.do_mirror()

            group_store.add_entry(
                uuid=group.uuid,
                entry=MirrorLog(
                    path=mirror_paths_group.absolute,
                    time=datetime.now().astimezone(),
                ),
            )

    def _mirror_not_in_any_group(self) -> None:
        """Mirror the profile's process data not contained in any group."""

        if self.config.organize_by_groups:
            no_group_subpath = Path("no-group")
        else:
            no_group_subpath = Path(".")

        mirror_paths_group = MirrorPaths(
            parent=self.mirror_paths.parent / self.mirror_paths.child,
            child=no_group_subpath,
        )

        # See here how to append to the parent and child of MirrorPaths
        node_collector_config_no_group = copy.deepcopy(self.node_collector_config)
        node_collector_config_no_group.group_scope = NodeMirrorGroupScope.NO_GROUP

        # no_group = orm.Group(label='no_group')

        no_group_mirror_inst = GroupMirror(
            mirror_paths=mirror_paths_group,
            group=None,
            mirror_mode=self.mirror_mode,
            process_mirror_config=self.process_mirror_config,
            config=self.group_mirror_config,
            mirror_logger=self.mirror_logger,
            node_collector_config=node_collector_config_no_group,
        )

        msg = (
            f"Mirroring processes not in any group for profile `{self.profile.name}`..."
        )
        logger.report(msg)
        no_group_mirror_inst.do_mirror()
        # TODO: Possibly add entry to logger

    def do_mirror(self, top_level_caller: bool = False):
        """_summary_

        :param
        """

        self.pre_mirror(top_level_caller=top_level_caller)

        # import ipdb; ipdb.set_trace()
        # If `groups` given on construction, mirror only data within those groups
        if self.groups:
            self._mirror_per_group(groups=self.groups)

        # If `groups` given on construction, mirror only data within those groups
        else:
            # Still, even without selecting groups, by default, all profile data should be mirrored
            # Thus, we obtain all groups in the profile here
            profile_groups = cast(
                list[orm.Group], orm.QueryBuilder().append(orm.Group).all(flat=True)
            )
            self._mirror_per_group(groups=profile_groups)

            if not self.config.only_groups:
                self._mirror_not_in_any_group()

        if self.config.delete_missing: ...
            # TODO: Only delete missing groups here, not processes. Processes handled by `GroupMirror`
        #     import ipdb; ipdb.set_trace()
        #     self.delete_container = MirrorNodeContainer()

            # self.delete_container.

        self.post_mirror()

    def get_groups_to_delete(self) -> list[str]:

        if not self.config.delete_missing:
            return []

        group_log = self.mirror_logger.stores.groups

        # Cannot use QB here because, when node deleted, it's not in the DB anymore
        mirrored_uuids = set(list(group_log.entries.keys()))

        profile_uuids = orm.QueryBuilder().append(orm.Group, project=['uuid']).all(flat=True)

        to_delete_uuids = list(mirrored_uuids - profile_uuids)

        return to_delete_uuids

    def del_missing_groups(self):
        groups_to_delete_uuids = self.get_groups_to_delete()
        if groups_to_delete_uuids:
            for to_delete_uuid in groups_to_delete_uuids:
                self.del_missing_group(group_uuid=to_delete_uuid)

    def del_missing_group(self, group_uuid):
        group_store = self.mirror_logger.stores.groups
        path = group_store.get_entry(group_uuid).path
        mirror_paths = MirrorPaths.from_path(path)
        safe_delete_dir(path=path, safeguard_file=mirror_paths.safeguard_path)
        self.mirror_logger.del_entry(store=group_store, uuid=group_uuid)

# def delete_groups(self):
#     to_delete_groups = self.groups_to_delete
#         # ! Problem: Don't have safeguard file in empty group directory

        # if

        # if delete_missing_processes:
        #     if num_processes_to_delete == 0:
        #         msg = 'No processes to delete.'
        #         logger.report(msg)
        #     else:
        #         self.delete_processes()
        #         msg = f'Deleted {num_processes_to_delete} node directories.'
        #         logger.report(msg)

        # if num_groups_to_delete == 0:
        #     echo.echo_success('No groups to delete.')
        # else:
        #     self.delete_groups()
        #     echo.echo_success(f'Deleted {num_groups_to_delete} group directories.')

        # if update_groups:
        #     relabeled_paths = self.update_groups()
        #     msg = 'Renamed group directories and updated the log file.'
        #     echo.echo_success(msg)
        #     # print(relabeled_paths)



#####



# # TODO: Also move this into a more general method that returns a `NodeContainer`
# @cached_property

# def delete_processes(self):
#     # to_mirror_processes = self.processes_to_mirror
#     to_delete_processes = self.processes_to_delete

#     # print(f'TO_MIRROR_PROCESSES: {to_mirror_processes}')
#     # print(f'TO_DELETE_PROCESSES: {to_delete_processes}')

#     for to_delete_uuid in to_delete_processes:
#         delete_missing_node_dir(mirror_logger=self.mirror_logger, to_delete_uuid=to_delete_uuid)

#     # TODO: Add also logging for node/path deletion?


# def update_groups(self) -> list[dict[str, Path]]:
    # TODO: Check if mtime of group _after_ last_mirror_time, and if so, run mirroring for new nodes
#     mirror_logger = self.mirror_logger

#     # Order is the same as in the mirroring log file -> Not using a profile QB here
#     # Also, if the group is new (and contains new nodes), it will be mirrored anyway
#     mirrored_group_uuids = list(mirror_logger.groups.entries.keys())

#     old_mapping: dict[str, Path] = dict(
#         zip(
#             mirrored_group_uuids,
#             [p.path for p in mirror_logger.groups.entries.values()],
#         )
#     )

#     new_mapping: dict[str, Path] = dict(
#         zip(
#             mirrored_group_uuids,
#             [self.mirror_parent_path / 'groups' / get_group_subpath(orm.load_group(g)) for g in mirrored_group_uuids],
#         )
#     )

#     modified_paths: list[dict[str, Path]] = []

#     for uuid, old_path in old_mapping.items():
#         new_path = new_mapping.get(uuid)

#         if new_path and old_path != new_path:
#             # logger.report(f'Renaming {old_path} -> {new_path}')
#             old_path.rename(new_path)
#             try:
#                 mirror_logger.groups.entries[uuid].path = new_path
#             except:
#                 # import ipdb, ipdb.set_trace()
#                 raise

#             modified_paths.append(
#                 {
#                     'old': old_path,
#                     'new': new_path,
#                 }
#             )

#     return modified_paths

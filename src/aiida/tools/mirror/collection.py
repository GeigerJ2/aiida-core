###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################

"""Base class for collection mirror."""

from __future__ import annotations
from pathlib import Path

from aiida import orm
from aiida.tools.mirror.base import BaseMirror
from aiida.tools.mirror.collector import MirrorNodeCollector
from aiida.tools.mirror.container import MirrorNodeContainer
from aiida.tools.mirror.config import (
    MirrorMode,
    MirrorPaths,
    MirrorTimes,
    NodeCollectorConfig,
)
from aiida.tools.mirror.logger import MirrorLogger
# from aiida.tools.mirror.group import GroupMirror
from aiida.tools.mirror.utils import NodeMirrorKeyMapper, safe_delete_dir
from dataclasses import fields
import shutil


class BaseCollectionMirror(BaseMirror):
    def __init__(
        self,
        mirror_mode: MirrorMode | None = None,
        mirror_paths: MirrorPaths | None = None,
        mirror_times: MirrorTimes | None = None,
        mirror_logger: MirrorLogger | None = None,
        node_collector_config: NodeCollectorConfig | None = None,
    ):
        super().__init__(
            mirror_mode=mirror_mode,
            mirror_paths=mirror_paths,
            mirror_times=mirror_times,
            mirror_logger=mirror_logger,
        )

        self.node_collector_config = node_collector_config or NodeCollectorConfig()

    def set_mirror_node_container(self, group: orm.Group | None = None) -> None:
        """
        Returns a NodeContainer by collecting nodes using the NodeDumpCollector.

        Returns:
            NodeContainer: The collected node container
        """
        node_collector = MirrorNodeCollector(
            config=self.node_collector_config,
            mirror_times=self.mirror_times,
            mirror_logger=self.mirror_logger,
        )

        self.mirror_node_container = node_collector.collect_to_mirror(group=group)

    def set_delete_node_container(self) -> None:
        """
        Returns a NodeContainer by collecting nodes using the NodeDumpCollector.

        Returns:
            NodeContainer: The collected node container
        """
        node_collector = MirrorNodeCollector(
            config=self.node_collector_config,
            mirror_times=self.mirror_times,
            mirror_logger=self.mirror_logger,
        )

        self.delete_node_container = node_collector.collect_to_delete()

    # Implement this here, as for the deletion, we don't care about the group
    def do_delete(self) -> None:
        """Main method to handle deletion of groups and nodes.

        This method orchestrates the deletion process by:
        1. Deleting group entities first
        2. Deleting individual marked nodes
        3. Cleaning up any nodes that were part of deleted groups

        :return: None
        """
        _ = self.set_delete_node_container()

        # First, handle groups and collect deleted group labels
        deleted_groups = self._delete_mirror_groups()

        # Then handle direct node deletions
        self._delete_mirror_nodes()

        # Finally, clean up nodes that were part of deleted groups
        if deleted_groups:
            self._delete_mirror_group_subnodes(deleted_groups)

    def _delete_mirror_groups(self) -> list:
        """Delete groups and return a list of their labels for further processing.

        Deletes all groups marked for deletion in the delete_node_container
        and collects their labels for identifying related subnodes.

        :return: Labels of deleted groups
        """

        to_delete_groups = getattr(self.delete_node_container, 'groups')
        group_store = self.mirror_logger.groups
        deleted_groups = []

        # First collect the group labels
        if len(to_delete_groups) > 0:
            for to_delete_group in to_delete_groups:
                group_label = group_store.get_entry(uuid=to_delete_group).mirror_path.name
                deleted_groups.append(group_label)

        # Then delete the groups
        for to_delete_group in to_delete_groups:
            path = group_store.get_entry(to_delete_group).mirror_path
            _ = safe_delete_dir(path=path, safeguard_file=MirrorPaths.from_path(path).safeguard)
            self.mirror_logger.del_entry(store=group_store, uuid=to_delete_group)

        return deleted_groups

    def _delete_mirror_nodes(self) -> None:
        """Delete individual nodes marked for deletion.

        Processes workflows, calculations, and data entities that were
        explicitly marked for deletion in the delete_node_container.

        :return: None
        """
        for store_name in ('workflows', 'calculations', 'data'):
            to_delete_uuids = getattr(self.delete_node_container, store_name)
            log_store = getattr(self.mirror_logger, store_name)

            for to_delete_uuid in to_delete_uuids:
                path = log_store.get_entry(to_delete_uuid).path
                _ = safe_delete_dir(path=path, safeguard_file=MirrorPaths.from_path(path).safeguard)
                self.mirror_logger.del_entry(store=log_store, uuid=to_delete_uuid)

    def _delete_mirror_group_subnodes(self, deleted_groups: list) -> None:
        """Delete nodes that were part of deleted groups but not explicitly marked for deletion.

        After groups are deleted, this method cleans up any nodes that belonged
        to those groups but weren't directly marked for deletion.

        :param deleted_groups: List of group labels that were deleted
        :type deleted_groups: list
        :return: None
        """
        for store_name in ('workflows', 'calculations', 'data'):
            log_store = getattr(self.mirror_logger, store_name)
            additional_delete_nodes = []

            # Find all nodes that belong to deleted groups
            for deleted_group in deleted_groups:
                for entry_uuid, entry in log_store.entries.items():
                    path_str = str(entry.path)
                    if deleted_group in path_str:
                        additional_delete_nodes.append(entry_uuid)

            # Delete the identified nodes
            for additional_delete_node in additional_delete_nodes:
                path = log_store.get_entry(additional_delete_node).path
                _ = safe_delete_dir(path=path, safeguard_file=MirrorPaths.from_path(path).safeguard)
                self.mirror_logger.del_entry(store=log_store, uuid=additional_delete_node)

    def update_groups(self):

        mirror_logger = self.mirror_logger
        old_mirror_logger_dict = self.mirror_logger.to_dict()

        # Order is the same as in the mirroring log file -> Not using a profile QB here
        # Also, if the group is new (and contains new nodes), it will be mirrored anyway
        mirrored_group_uuids = list(mirror_logger.groups.entries.keys())

        old_mapping: dict[str, Path] = dict(
            zip(
                mirrored_group_uuids,
                [p.mirror_path for p in mirror_logger.groups.entries.values()],
            )
        )

        new_mapping: dict[str, Path] = dict(
            zip(
                mirrored_group_uuids,
                [orm.load_group(uuid=uuid).label for uuid in mirrored_group_uuids],
            )
        )

        for old_label, new_label in zip([*[p.name for p in old_mapping.values()]], [*new_mapping.values()]):
            self.mirror_logger.update_paths(old_str=old_label, new_str=new_label)

        new_mirror_logger_dict = self.mirror_logger.to_dict()

        moved_paths = []
        for entity in ('groups', 'workflows', 'calculations', 'data'):
            old_store_dict = old_mirror_logger_dict[entity]
            new_store_dict = new_mirror_logger_dict[entity]

            for uuid, entry in old_store_dict.items():
                old_path = entry['path']
                new_path = new_store_dict[uuid]['path']

                if old_path != new_path and old_path not in moved_paths:
                    try:
                        shutil.move(str(old_path), str(new_path))
                        moved_paths.append(old_path)

                        # Update original dictionary to reflect the moves already done
                        # This works because the `store_dict`s are just references to parts of the original `mirror_logger_dict`
                        old_store_dict[uuid]['path'] = new_path

                    except FileNotFoundError:
                        # This could be handled better, the origin of this problem is that if I move the following:
                        # profile-readme-mirror/groups/add-group
                        # to
                        # profile-readme-mirror/groups/xadd-group
                        # The following move operation will fail:
                        # profile-readme-mirror/groups/add-group/calculations/ArithmeticAddCalculation-4
                        # to
                        # profile-readme-mirror/groups/xadd-group/calculations/ArithmeticAddCalculation-4
                        # Because the group directory had already been renamed.
                        # TODO: Fix better in the future...
                        continue

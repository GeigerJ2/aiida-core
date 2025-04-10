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

from aiida.common.log import AIIDA_LOGGER
from aiida.tools.mirror.base import BaseMirror
from aiida.tools.mirror.collector import MirrorCollector
from aiida.tools.mirror.config import MirrorCollectorConfig, MirrorMode, MirrorPaths, MirrorStoreKeys
from aiida.tools.mirror.logger import MirrorLogger, MirrorLogStore
from aiida.tools.mirror.store import MirrorNodeStore
from aiida.tools.mirror.utils import StoreNameType, safe_delete_dir

logger = AIIDA_LOGGER.getChild('tools.mirror.group')


class BaseCollectionMirror(BaseMirror):
    def __init__(
        self,
        mirror_mode: MirrorMode,
        mirror_paths: MirrorPaths,
        mirror_logger: MirrorLogger | None = None,
        mirror_collector_config: MirrorCollectorConfig | None = None,
    ):
        super().__init__(
            mirror_mode=mirror_mode,
            mirror_paths=mirror_paths,
            # mirror_logger=mirror_logger,
        )

        self.mirror_collector_config = mirror_collector_config or MirrorCollectorConfig()

        # The problem is that the mirror_logger is not a singleton, but is passed around and attached to various
        # classes. During mirroring with the `overwrite` option, it gets reset for every `ProcessMirror` instantiation.
        # However, the pre_mirror is done before instantiation, so running the mirror with `overwrite` still has the
        # `dump_logger` from the JSON file of the previous run attached...
        # Solve by deleting the log file in overwrite mode here, or making pre_mirror a `classmethod` that's executed
        # before instantiation??
        if mirror_mode == MirrorMode.OVERWRITE and mirror_paths.log_path.exists():
            mirror_paths.log_path.unlink()

        self.mirror_logger = self.set_mirror_logger(mirror_logger=mirror_logger, top_level_caller=True)

        # Initialize mirror_collector as None - it will be properly set by child classes
        self.mirror_collector: MirrorCollector | None = None

    # ! This shouldn't be here, because the `mirror_collector` only is required for collections of nodes
    def set_mirror_collector(self, mirror_logger: MirrorLogger) -> MirrorCollector:
        mirror_collector = MirrorCollector(
            mirror_logger=mirror_logger,
            config=self.mirror_collector_config,
        )
        return mirror_collector

    # Implement this here, as for the deletion, we don't care about the group
    def delete(self) -> None:
        """Main method to handle deletion of groups and nodes.

        This method orchestrates the deletion process by:
        1. Deleting group entities first
        2. Deleting individual marked nodes
        3. Cleaning up any nodes that were part of deleted groups

        :return: None
        """

        msg = '`--delete-missing` option selected. Will delete missing node directories and log entries.'
        logger.report(msg)

        if self.mirror_collector is None:
            msg = 'mirror_collector is not set. This should be initialized in a child class.'
            raise AttributeError(msg)

        delete_store: MirrorNodeStore = self.mirror_collector.collect_to_delete()

        # First, handle groups and collect deleted group labels
        deleted_groups = self.group_store_delete(delete_store=delete_store)

        # Then handle direct node deletions
        self.process_store_delete(delete_store=delete_store)

        # Finally, clean up nodes that were part of deleted groups
        if deleted_groups:
            self.group_store_subnodes_delete(deleted_groups)

        # TODO: Verify if the log is properly updated here (via the test)

    def group_store_delete(self, delete_store: MirrorNodeStore) -> list[str]:
        """Delete groups and return a list of their labels for further processing.

        Deletes all groups marked for deletion in the delete_node_container
        and collects their labels for identifying related subnodes.

        :return: Labels of deleted groups
        """

        to_delete_group_uuids: list[str] = getattr(delete_store, 'groups')
        log_group_store = self.mirror_logger.groups
        deleted_groups: list[str] = []

        # Early return if no groups in the delete_store
        if not to_delete_group_uuids:
            return []

        # First collect the group labels
        for to_delete_group_uuid in to_delete_group_uuids:
            entry = log_group_store.get_entry(to_delete_group_uuid)
            assert entry is not None, f'Group with UUID {to_delete_group_uuid} should exist but was not found'
            # Need to work with log entries here, as data not in AiiDA's DB anymore
            group_label = entry.path.name
            deleted_groups.append(group_label)

        # Then delete the groups
        for to_delete_group_uuid in to_delete_group_uuids:
            entry = log_group_store.get_entry(to_delete_group_uuid)
            assert entry is not None, f'Group with UUID {to_delete_group_uuid} should exist but was not found'
            path = entry.path
            safe_delete_dir(path=path, safeguard_file=MirrorPaths.from_path(path).safeguard_path)
            self.mirror_logger.del_entry(store=log_group_store, uuid=to_delete_group_uuid)

        msg = f'Deleted the groups: {deleted_groups}'
        logger.report(msg)

        return deleted_groups

    def process_store_delete(self, delete_store: MirrorNodeStore) -> None:
        """Delete individual nodes marked for deletion.

        Processes workflows, calculations, and data entities that were
        explicitly marked for deletion in the delete_node_container.

        :return: None
        """
        for store_name in ('workflows', 'calculations'):  # , 'data'):
            to_delete_uuids = getattr(delete_store, store_name)
            log_store = getattr(self.mirror_logger, store_name)

            for to_delete_uuid in to_delete_uuids:
                path = log_store.get_entry(to_delete_uuid).path
                safe_delete_dir(path=path, safeguard_file=MirrorPaths.from_path(path).safeguard_path)
                self.mirror_logger.del_entry(store=log_store, uuid=to_delete_uuid)

            msg = f'Deleted {len(to_delete_uuids)} {store_name}'
            logger.report(msg)

    # TODO: Should this even delete the node directories?
    # TODO: If so, they should also be deleted from the logger
    # TODO: Then, after the next `mirror` command, they should be dumped again in the `no-group` directory,
    # TODO: if `also-ungrouped` is set to True
    def group_store_subnodes_delete(self, deleted_group_labels: list[str]) -> None:
        """Delete nodes that were part of deleted groups but not explicitly marked for deletion.

        After groups are deleted, this method cleans up any nodes that belonged
        to those groups but weren't directly marked for deletion.

        :param deleted_groups: List of group labels that were deleted
        :type deleted_groups: list
        :return: None
        """
        store_names: list[StoreNameType] = [
            MirrorStoreKeys.WORKFLOWS.value,
            MirrorStoreKeys.CALCULATIONS.value,
            MirrorStoreKeys.DATA.value,
        ]
        for store_name in store_names:
            log_store: MirrorLogStore = self.mirror_logger.get_store_by_name(store_name)
            additional_delete_nodes = []

            # Find all nodes that belong to deleted groups
            for deleted_group_label in deleted_group_labels:
                for entry_uuid, entry in log_store.entries.items():
                    path_str = str(entry.path)
                    if deleted_group_label in path_str:
                        additional_delete_nodes.append(entry_uuid)

            # Delete the identified nodes
            for additional_delete_node in additional_delete_nodes:
                entry = log_store.get_entry(additional_delete_node)  # type: ignore[assignment]
                assert entry is not None, f'Entry with UUID {additional_delete_node} should exist but was not found'
                path = entry.path
                safe_delete_dir(path=path, safeguard_file=MirrorPaths.from_path(path).safeguard_path)
                self.mirror_logger.del_entry(store=log_store, uuid=additional_delete_node)

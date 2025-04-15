from __future__ import annotations
import os
from pathlib import Path

from aiida import orm
from aiida.common.log import AIIDA_LOGGER
from aiida.tools.dumping.config import DumpConfig, NodeDumpGroupScope
from aiida.tools.dumping.storage import DumpLog
from aiida.tools.dumping.utils.groups import get_group_subpath
from aiida.tools.dumping.utils.paths import safe_delete_dir, DumpPaths
from aiida.tools.dumping.detect.detector import DumpChangeDetector
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aiida.tools.dumping.utils.paths import DumpPaths
    from aiida.tools.dumping.config import DumpConfig
    from aiida.tools.dumping.storage.logger import DumpLogger
    from aiida.tools.dumping.managers.nodes import NodeManager

logger = AIIDA_LOGGER.getChild("tools.dumping.group_manager")


class GroupDumpManager:
    """Handles group-related operations during dumping"""

    def __init__(
        self,
        config: DumpConfig,
        dump_paths: DumpPaths,
        dump_logger: DumpLogger,
        node_processor=None,
    ):
        self.config: DumpConfig = config
        self.dump_paths: DumpPaths = dump_paths
        self.dump_logger: DumpLogger = dump_logger
        self.node_manager: NodeManager = node_processor

    def handle_groups(self):
        """
        Process all groups in the database.

        This method queries all groups from the database and dumps them
        based on their changes since the last dump, ensuring new groups
        are properly handled.
        """
        # Query all groups directly from the database to ensure we get the latest state
        qb = orm.QueryBuilder()
        qb.append(orm.Group)
        groups = qb.all(flat=True)

        # TODO: Also debug here -> This should respecct group selection and not always get all groups
        # import ipdb; ipdb.set_trace()
        logger.report(f"Found {len(groups)} groups to process")

        for group in groups:
            # Create a group-specific detector
            group_detector = DumpChangeDetector(
                self.dump_logger,
                # Create config with IN_GROUP scope
                DumpConfig(
                    **{
                        **self.config.__dict__,
                        "group_scope": NodeDumpGroupScope.IN_GROUP,
                    }
                ),
            )

            group_changes = group_detector.detect_changes(group=group)

            # Check if there are any new nodes to dump
            new_calcs = len(group_changes["new_nodes"].calculations)
            new_wfs = len(group_changes["new_nodes"].workflows)

            # TODO: Because the group is not in the log, this gets triggered
            # If there are new nodes or if this is a newly created group (not in the log yet)
            if (
                new_calcs > 0
                or new_wfs > 0
                or group.uuid not in self.dump_logger.groups.entries
            ):
                msg = f"Processing group '{group.label}' with {new_calcs} new calculations and {new_wfs} new workflows"
                logger.report(msg)

                # Handle this group
                self.handle_group_dump(group, group_changes)
            else:
                logger.report(
                    f"No changes detected for group '{group.label}', skipping"
                )

    def handle_group_dump(self, group, changes):
        """
        Handle dumping for a specific group.

        Args:
            group: The AiiDA Group to dump
            changes: Dictionary of detected changes for this group
        """
        # Update group structure if needed
        if self.config.update_groups:
            self.update_group_structure(changes["group_changes"])

        group_path = self.get_group_path(group)

        # Dump new nodes
        if self.node_manager:
            self.node_manager.dump_nodes(changes["new_nodes"], group)
        else:
            msg = "No node processor provided, skipping node dumping"
            logger.warning(msg)

        import ipdb; ipdb.set_trace()
        if group.uuid not in self.dump_logger.groups.entries:
            self.dump_logger.groups.add_entry(
                uuid=group.uuid, entry=DumpLog(path=group_path)
            )

    def update_group_structure(self, group_changes):
        """
        Update dump structure based on group changes.

        Args:
            group_changes: Dictionary containing information about group changes
        """
        # Handle deleted groups
        if "deleted_groups" in group_changes:
            for group_info in group_changes["deleted_groups"]:
                self.delete_group(group_info)

        # Handle modified groups
        if "modified_groups" in group_changes:
            for group_info in group_changes["modified_groups"]:
                self.update_group(group_info)

        # Handle new groups (usually handled by normal dump process)
        if "new_groups" in group_changes:
            for group_info in group_changes["new_groups"]:
                logger.report(f"Detected new group with UUID {group_info.get('uuid')}")

    def update_group(self, group_info):
        """
        Update a group's dump based on membership changes.

        Args:
            group_info: Dictionary containing group information and changes
        """
        group_uuid = group_info["uuid"]

        try:
            # Load the group
            group = orm.load_group(uuid=group_uuid)

            # Get the group entry from the logger
            group_entry = self.dump_logger.groups.get_entry(group_uuid)
            if group_entry is None:
                # Group exists in DB but not in log - skip
                msg = (
                    f"Group {group.label} found in DB but not in log - skipping update"
                )
                logger.warning(msg)
                return

            group_path = group_entry.path

            # Handle nodes added to this group
            if "nodes_added" in group_info and self.node_manager:
                logger.report(
                    f"Updating {len(group_info['nodes_added'])} nodes added to group {group.label}"
                )

                for node_uuid in group_info["nodes_added"]:
                    try:
                        # Get the node
                        node = orm.load_node(uuid=node_uuid)

                        # Dump the node
                        self.node_manager.dump_process(node, group)

                    except Exception as e:
                        logger.warning(
                            f"Error processing node {node_uuid} added to group: {e}"
                        )

            # Handle nodes removed from this group
            if "nodes_removed" in group_info:
                logger.report(
                    f"Cleaning up {len(group_info['nodes_removed'])} nodes removed from group {group.label}"
                )

                for node_uuid in group_info["nodes_removed"]:
                    # Try to find the node path in the logger
                    try:
                        node_path = self.dump_logger.get_dump_path_by_uuid(
                            uuid=node_uuid
                        )

                        # Check if the path exists and is within this group's directory
                        if node_path and str(group_path) in str(node_path):
                            # Delete the directory
                            safe_delete_dir(
                                path=node_path, safeguard_file=DumpPaths.safeguard_file
                            )

                            # Remove from logger
                            store_key = None
                            for key in ["calculations", "workflows", "data"]:
                                store = getattr(self.dump_logger, key)
                                if node_uuid in store.entries:
                                    store_key = key
                                    break

                            if store_key:
                                store = getattr(self.dump_logger, store_key)
                                self.dump_logger.del_entry(store=store, uuid=node_uuid)
                    except Exception as e:
                        logger.warning(
                            f"Error cleaning up node {node_uuid} removed from group: {e}"
                        )

        except Exception as e:
            logger.error(f"Error updating group {group_uuid}: {e}")
            import traceback

            logger.debug(traceback.format_exc())

    def delete_group(self, group_info):
        """
        Delete a group's dump directory.

        Args:
            group_info: Dictionary containing information about the group to delete
        """
        group_uuid = group_info["uuid"]
        group_entry = self.dump_logger.groups.get_entry(group_uuid)

        if group_entry:
            logger.report(f"Deleting group with UUID {group_uuid}")
            path = group_entry.path
            safe_delete_dir(path=path, safeguard_file=DumpPaths.safeguard_file)
            self.dump_logger.del_entry(self.dump_logger.groups, group_uuid)
        else:
            logger.warning(f"Group {group_uuid} not found in logger, cannot delete")

    def get_group_path(self, group):
        """
        Get the path for a group.

        This method determines the appropriate directory path for a group
        based on configuration settings.

        Args:
            group: The AiiDA Group object

        Returns:
            Path object representing the directory for the group
        """
        if self.config.organize_by_groups:
            # Using existing utility to create a hierarchical path
            group_path = self.dump_paths.absolute / "groups" / get_group_subpath(group)
        else:
            group_path = self.dump_paths.absolute

        # Ensure the group directory exists
        group_path.mkdir(parents=True, exist_ok=True)

        # Add the safeguard file if it doesn't exist
        safeguard_path = group_path / DumpPaths.safeguard_file
        if not safeguard_path.exists():
            safeguard_path.touch()

        return group_path

    # TODO: This method should not be needed?
    # def ensure_group_registered(self, group):
    #     """
    #     Ensure a group is registered in the logger.

    #     Args:
    #         group: The AiiDA Group object to register

    #     Returns:
    #         Path object representing the directory for the group
    #     """
    #     group_path = self.get_group_path(group)

    #     # If the group is not in the logger, register it
    #     import ipdb

    #     ipdb.set_trace()
    #     if group.uuid not in self.dump_logger.groups.entries:
    #         self.dump_logger.groups.add_entry(
    #             uuid=group.uuid, entry=DumpLog(path=group_path)
    #         )
    #         logger.debug(f"Registered group {group.label} in logger")

    #     return group_path

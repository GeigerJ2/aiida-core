from __future__ import annotations
from pathlib import Path

from aiida import orm
from aiida.common.log import AIIDA_LOGGER
from aiida.tools.dumping.config import DumpConfig, NodeDumpGroupScope
from aiida.tools.dumping.storage import DumpLog
from aiida.tools.dumping.utils.groups import get_group_subpath
from aiida.tools.dumping.utils.paths import safe_delete_dir, DumpPaths
from aiida.tools.dumping.detect.detector import DumpChangeDetector
from aiida.tools.dumping.utils.types import (
    GroupChangeInfo,
    GroupModificationInfo,
)
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aiida.tools.dumping.utils.paths import DumpPaths
    from aiida.tools.dumping.config import DumpConfig
    from aiida.tools.dumping.storage.logger import DumpLogger
    from managers.node import NodeManager

logger = AIIDA_LOGGER.getChild("tools.dumping.group_manager")


class GroupManager:
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
                import ipdb; ipdb.set_trace()
                self.handle_group_dump(group, group_changes)
            else:
                logger.report(
                    f"No changes detected for group '{group.label}', skipping"
                )

    def handle_group_dump(self, group: orm.Group, changes):
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

        # Ensure the group directory exists
        group_path.mkdir(parents=True, exist_ok=True)

        # Add the safeguard file if it doesn't exist
        safeguard_path = group_path / DumpPaths.safeguard_file
        if not safeguard_path.exists():
            safeguard_path.touch()

        # Dump new nodes
        if self.node_manager:
            self.node_manager.dump_nodes(changes["new_nodes"], group)
        else:
            msg = "No node processor provided, skipping node dumping"
            logger.warning(msg)

        # Finally, add to the logger
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

        return group_path

    def handle_group_changes(self, group_changes: GroupChangeInfo):
        logger.report("Processing group changes...")

        # 1. Handle Deleted Groups (Directory deletion handled by DeletionManager)
        # We might still need to log this or perform other cleanup
        if group_changes.deleted:
            logger.report(
                f"Detected {len(group_changes.deleted)} deleted groups (deletion handled elsewhere)."
            )

        # 2. Handle New Groups
        if group_changes.new:
            logger.report(f"Processing {len(group_changes.new)} new groups.")
            for group_info in group_changes.new:
                # Ensure the group directory exists and is logged
                try:
                    group = orm.load_group(uuid=group_info.uuid)
                    self.ensure_group_registered(group)
                    # Dumping nodes within this new group will happen if they
                    # are picked up by the NodeChanges detection based on config.
                except Exception as e:
                    logger.warning(
                        f"Could not process new group {group_info.uuid}: {e}"
                    )

        # 3. Handle Modified Groups (Membership changes)
        if group_changes.modified:
            logger.report(f"Processing {len(group_changes.modified)} modified groups.")
            for mod_info in group_changes.modified:
                self.update_group_membership(mod_info)

        # 4. Handle Node Membership Changes (Alternative perspective, might overlap with modified)
        # This provides info per-node if needed, but modified_groups usually covers it.
        # if group_changes.node_membership:
        #      logger.report(f"Processing node membership changes for {len(group_changes.node_membership)} nodes.")
        #      for node_uuid, changes in group_changes.node_membership.items():
        #           # Logic to handle specific node's add/remove across groups
        #           pass

    def update_group_membership(self, mod_info: GroupModificationInfo):
        """Update dump structure for a group with added/removed nodes."""
        logger.report(
            f"Updating group {mod_info.uuid}: {len(mod_info.nodes_added)} added, {len(mod_info.nodes_removed)} removed."
        )
        try:
            group = orm.load_group(uuid=mod_info.uuid)
        except Exception as e:
            logger.error(f"Cannot load group {mod_info.uuid} for update: {e}")
            return

        # Ensure group directory exists and is logged
        group_path = self.ensure_group_registered(group)

        # Handle added nodes (trigger dump/symlink if needed)
        # Note: These nodes might *also* be in changes.nodes.new_or_modified
        # The NodeProcessor.dump_process should handle potential duplicate dumping.
        for node_uuid in mod_info.nodes_added:
            try:
                node = orm.load_node(uuid=node_uuid)
                logger.debug(
                    f"Node {node_uuid} added to group {group.label}. Ensuring it's dumped."
                )
                # Let NodeProcessor handle the actual dumping logic
                # It will determine the correct path based on the group context
                # We might not need to explicitly call dump here if the main loop does it,
                # but ensure the node processor logic correctly places it in the group dir.
                # self.node_processor.dump_process(node, group) # If node_processor is aware
            except Exception as e:
                logger.warning(
                    f"Could not process node {node_uuid} added to group {group.label}: {e}"
                )

        # Handle removed nodes (remove symlink/copy from this group's dir)
        for node_uuid in mod_info.nodes_removed:
            logger.debug(
                f"Node {node_uuid} removed from group {group.label}. Cleaning up."
            )
            self.remove_node_from_group_dir(group_path, node_uuid)

    def ensure_group_registered(self, group: orm.Group) -> Path:
        """Ensure group exists in logger and return its path."""
        group_path = self.get_group_path(group)  # Get path using existing logic
        if group.uuid not in self.dump_logger.groups.entries:
            msg = f"Registering group '{group.label}' ({group.uuid}) in logger."
            logger.debug(msg)

            self.dump_logger.add_entry(
                self.dump_logger.groups,  # Access the groups store
                uuid=group.uuid,
                entry=DumpLog(path=group_path),
            )

        group_path.mkdir(parents=True, exist_ok=True)
        (group_path / DumpPaths.safeguard_file).touch()

        return group_path

    def remove_node_from_group_dir(self, group_path: Path, node_uuid: str):
        """Find and remove a node's dump dir/symlink within a specific group path."""
        node_path_in_logger = self.dump_logger.get_dump_path_by_uuid(node_uuid)
        if not node_path_in_logger:
            logger.warning(
                f"Cannot find logger path for node {node_uuid} to remove from group."
            )
            return

        # Construct potential paths within the group dir
        possible_paths = [
            group_path / "calculations" / node_path_in_logger.name,
            group_path / "workflows" / node_path_in_logger.name,
            group_path / node_path_in_logger.name,  # If not in subdirs
        ]

        for potential_path in possible_paths:
            if potential_path.exists():  # Check if it exists (could be dir or symlink)
                # Check if it's a symlink *to the logged path* or the actual logged path itself
                # This logic needs refinement based on symlinking strategy
                is_symlink_to_target = (
                    potential_path.is_symlink()
                )  # and os.readlink(potential_path) == str(node_path_in_logger)
                is_target_dir = potential_path == node_path_in_logger

                # Decide whether to remove the symlink or the directory
                # This example just removes whatever exists at the potential path
                # CAUTION: Be careful not to delete the *original* dump if only removing from group
                logger.report(
                    f"Removing '{potential_path.name}' from group directory '{group_path.name}'."
                )
                if potential_path.is_symlink():
                    potential_path.unlink()
                    # Also update logger if symlinks are tracked per entry
                    # self.dump_logger.remove_symlink(...)
                elif potential_path.is_dir() and not is_target_dir:
                    # If it's a directory copy within the group, remove it safely

                    safe_delete_dir(
                        potential_path, safeguard_file=".aiida_node_metadata.yaml"
                    )  # Use node safeguard
                elif is_target_dir:
                    # If this *is* the primary dump path, removing from a group
                    # shouldn't delete it entirely unless the node itself is deleted.
                    logger.debug(
                        f"Node {node_uuid} removed from group, but its primary dump path {potential_path} is not deleted here."
                    )
                else:
                    logger.warning(
                        f"Cannot determine how to handle removed node path: {potential_path}"
                    )

                break  # Assume found

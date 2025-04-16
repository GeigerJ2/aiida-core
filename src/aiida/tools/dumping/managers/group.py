from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from aiida import orm
from aiida.common.log import AIIDA_LOGGER
from aiida.tools.dumping.config import DumpConfig
from aiida.tools.dumping.storage import DumpLog
from aiida.tools.dumping.utils.groups import get_group_subpath
from aiida.tools.dumping.utils.paths import DumpPaths, prepare_dump_path, safe_delete_dir
from aiida.tools.dumping.utils.types import (
    GroupChanges,
    GroupModificationInfo,
)

if TYPE_CHECKING:
    from aiida.tools.dumping.config import DumpConfig
    from aiida.tools.dumping.logger import DumpLogger
    from aiida.tools.dumping.utils.paths import DumpPaths

logger = AIIDA_LOGGER.getChild('tools.dumping.managers.group')


class GroupManager:
    """Handles group-related operations during dumping"""

    def __init__(
        self,
        config: DumpConfig,
        dump_paths: DumpPaths,
        dump_logger: DumpLogger,
    ):
        self.config: DumpConfig = config
        self.dump_paths: DumpPaths = dump_paths
        self.dump_logger: DumpLogger = dump_logger
        # TODO: dump_times needed here for any logic?

    def prepare_group_path(self, group: orm.Group | None) -> Path:  # Renamed method
        """
        Calculate, prepare (create/clean), and return the dump path for a specific group.

        Ensures the directory exists, handles overwrite mode, and adds the safeguard file.
        """
        # 1. Calculate the target path
        if self.config.organize_by_groups:
            if group:
                # Hierarchical structure under 'groups/' using entry point/label
                group_path = self.dump_paths.absolute / 'groups' / get_group_subpath(group)
            else:
                group_path = self.dump_paths.absolute / 'ungrouped'

        else:
            # Flat structure - group itself doesn't get a dedicated *prepared* directory.
            # Nodes will be placed directly under type subdirs by NodeManager.
            # Return the main dump path, but don't prepare it here (Engine handles root prep).
            # Note: If flat structure *did* require group dirs, logic would change.
            return self.dump_paths.absolute

        # 2. Prepare the calculated path using the utility function
        # This handles mkdir, overwrite (via safe_delete_dir), and safeguard file.
        try:
            prepare_dump_path(
                path_to_validate=group_path,
                dump_mode=self.config.dump_mode,  # Pass current dump mode
                safeguard_file=DumpPaths.safeguard_file,  # Use standard safeguard
                top_level_caller=False,  # Indicate it's not the absolute root dump dir
            )
        except Exception as e:
            # Log error during specific group path preparation
            logger.error(f'Failed to prepare path for group {group.label}: {e}', exc_info=True)
            # Re-raise or handle as appropriate? Re-raising might stop the process.
            # Depending on desired robustness, you might want to allow skipping a group.
            raise  # Or return None / log and continue

        # 3. Return the prepared path
        return group_path

    def handle_group_changes(self, group_changes: GroupChanges):
        logger.report('Processing group changes...')

        # 1. Handle Deleted Groups (Directory deletion handled by DeletionManager)
        # We might still need to log this or perform other cleanup
        if group_changes.deleted:
            logger.report(f'Detected {len(group_changes.deleted)} deleted groups (deletion handled elsewhere).')

        # 2. Handle New Groups
        if group_changes.new:
            logger.report(f'Processing {len(group_changes.new)} new groups.')
            for group_info in group_changes.new:
                # Ensure the group directory exists and is logged
                try:
                    group = orm.load_group(uuid=group_info.uuid)
                    self.ensure_group_registered(group)
                    # Dumping nodes within this new group will happen if they
                    # are picked up by the NodeChanges detection based on config.
                except Exception as e:
                    logger.warning(f'Could not process new group {group_info.uuid}: {e}')

        # 3. Handle Modified Groups (Membership changes)
        if group_changes.modified:
            logger.report(f'Processing {len(group_changes.modified)} modified groups.')
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
            f'Updating group {mod_info.uuid}: {len(mod_info.nodes_added)} added, {len(mod_info.nodes_removed)} removed.'
        )
        try:
            group = orm.load_group(uuid=mod_info.uuid)
        except Exception as e:
            logger.error(f'Cannot load group {mod_info.uuid} for update: {e}')
            return

        # Ensure group directory exists and is logged
        group_path = self.ensure_group_registered(group)

        # Handle added nodes (trigger dump/symlink if needed)
        # Note: These nodes might *also* be in changes.nodes.new_or_modified
        # The NodeProcessor.dump_process should handle potential duplicate dumping.
        for node_uuid in mod_info.nodes_added:
            try:
                node = orm.load_node(uuid=node_uuid)
                logger.debug(f"Node {node_uuid} added to group {group.label}. Ensuring it's dumped.")
                # Let NodeProcessor handle the actual dumping logic
                # It will determine the correct path based on the group context
                # We might not need to explicitly call dump here if the main loop does it,
                # but ensure the node processor logic correctly places it in the group dir.
                self.node_manager.dump_process(node, group)
            except Exception as e:
                logger.warning(f'Could not process node {node_uuid} added to group {group.label}: {e}')

        # Handle removed nodes (remove symlink/copy from this group's dir)
        for node_uuid in mod_info.nodes_removed:
            logger.debug(f'Node {node_uuid} removed from group {group.label}. Cleaning up.')
            self.remove_node_from_group_dir(group_path, node_uuid)

        # --- Handle removed nodes ---
        # Remove the representation (symlink or maybe copy) from this group's directory.
        if self.config.organize_by_groups and mod_info.nodes_removed:
            logger.debug(f"Handling {len(mod_info.nodes_removed)} nodes removed from group '{group.label}'")
            for node_uuid in mod_info.nodes_removed:
                self.remove_node_representation_from_group_dir(group_path, node_uuid)

    def ensure_group_registered(self, group: orm.Group) -> Path:
        """Ensure group exists in logger and return its path."""
        group_path = self.prepare_group_path(group)  # Get path using existing logic
        if group.uuid not in self.dump_logger.groups.entries:
            msg = f"Registering group '{group.label}' ({group.uuid}) in logger."
            logger.debug(msg)

            group_store = self.dump_logger.groups
            group_store.add_entry(
                uuid=group.uuid,
                entry=DumpLog(path=group_path),
            )

        return group_path

    # TODO: Possibly update this method
    def remove_node_from_group_dir(self, group_path: Path, node_uuid: str):
        """Find and remove a node's dump dir/symlink within a specific group path."""
        node_path_in_logger = self.dump_logger.get_dump_path_by_uuid(node_uuid)
        if not node_path_in_logger:
            logger.warning(f'Cannot find logger path for node {node_uuid} to remove from group.')
            return

        # Construct potential paths within the group dir
        possible_paths = [
            group_path / 'calculations' / node_path_in_logger.name,
            group_path / 'workflows' / node_path_in_logger.name,
            group_path / node_path_in_logger.name,  # If not in subdirs
        ]

        for potential_path in possible_paths:
            if potential_path.exists():  # Check if it exists (could be dir or symlink)
                # Check if it's a symlink *to the logged path* or the actual logged path itself
                # This logic needs refinement based on symlinking strategy
                # TODO: This variable is not being used
                is_symlink_to_target = (
                    potential_path.is_symlink()
                )  # and os.readlink(potential_path) == str(node_path_in_logger)
                is_target_dir = potential_path == node_path_in_logger

                # Decide whether to remove the symlink or the directory
                # This example just removes whatever exists at the potential path
                # CAUTION: Be careful not to delete the *original* dump if only removing from group
                logger.report(f"Removing '{potential_path.name}' from group directory '{group_path.name}'.")
                if potential_path.is_symlink():
                    potential_path.unlink()
                    # Also update logger if symlinks are tracked per entry
                    # self.dump_logger.remove_symlink(...)
                elif potential_path.is_dir() and not is_target_dir:
                    # If it's a directory copy within the group, remove it safely

                    safe_delete_dir(potential_path, safeguard_file='.aiida_node_metadata.yaml')  # Use node safeguard
                elif is_target_dir:
                    # If this *is* the primary dump path, removing from a group
                    # shouldn't delete it entirely unless the node itself is deleted.
                    logger.debug(
                        f'Node {node_uuid} removed from group, but its primary dump path {potential_path} is not deleted here.'
                    )
                else:
                    logger.warning(f'Cannot determine how to handle removed node path: {potential_path}')

                break  # Assume found

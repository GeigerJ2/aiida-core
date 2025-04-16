from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from aiida import orm
from aiida.common.log import AIIDA_LOGGER
from aiida.tools.dumping.logger import DumpLog
from aiida.tools.dumping.utils.groups import get_group_subpath
from aiida.tools.dumping.utils.paths import DumpPaths, prepare_dump_path, safe_delete_dir

if TYPE_CHECKING:
    from aiida.tools.dumping.config import DumpConfig
    from aiida.tools.dumping.engine import DumpEngine
    from aiida.tools.dumping.logger import DumpLogger
    from aiida.tools.dumping.utils.paths import DumpPaths
    from aiida.tools.dumping.utils.types import GroupChanges, GroupModificationInfo

logger = AIIDA_LOGGER.getChild('tools.dumping.managers.group')


class GroupManager:
    """Handles group-related operations during dumping"""

    def __init__(
        self,
        config: DumpConfig,
        dump_paths: DumpPaths,
        dump_logger: DumpLogger,
        engine: DumpEngine
    ):
        self.config: DumpConfig = config
        self.dump_paths: DumpPaths = dump_paths
        self.dump_logger: DumpLogger = dump_logger
        self.engine: DumpEngine = engine
        # self.node_manager: NodeManager = node_manager
        # TODO: dump_times needed here for any logic?

    def prepare_group_path(self, group: orm.Group | None) -> Path:
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
        msg = (
            f'Updating group {mod_info.label}: {len(mod_info.nodes_added)} added, '
            f'{len(mod_info.nodes_removed)} removed.'
        )

        logger.report(msg)
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
                self.engine.request_node_dump(node, group)
                # This would introduce a circular dependency
                # self.node_manager.dump_process(node, group)
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
                self.remove_node_from_group_dir(group_path, node_uuid)

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

    def remove_node_from_group_dir(self, group_path: Path, node_uuid: str):
        """
        Find and remove a node's dump dir/symlink within a specific group path.
        Handles nodes potentially deleted from the DB by checking filesystem paths.
        """
        node_path_in_logger = self.dump_logger.get_dump_path_by_uuid(node_uuid)
        if not node_path_in_logger:
            logger.warning(f'Cannot find logger path for node {node_uuid} to remove from group.')
            return

        # Even if node is deleted from DB, we expect the dump_logger to know the original path name
        node_filename = node_path_in_logger.name

        # Construct potential paths within the group dir where the node might be represented
        # The order matters if duplicates could somehow exist; checks stop on first find.
        possible_paths_to_check = [
            group_path / 'calculations' / node_filename,
            group_path / 'workflows' / node_filename,
            group_path / node_filename,  # Check group root last
        ]

        found_path: Path | None = None
        for potential_path in possible_paths_to_check:
            # Use exists() which works for files, dirs, and symlinks (even broken ones)
            if potential_path.exists():
                found_path = potential_path
                logger.debug(f'Found existing path for node {node_uuid} representation at: {found_path}')
                break  # Stop searching once a potential candidate is found

        if not found_path:
            logger.debug(
                f"Node {node_uuid} representation ('{node_filename}') not found in standard "
                f"group locations within '{group_path.name}'. No removal needed."
            )
            return

        # --- Removal Logic applied to the found_path ---
        try:
            # Determine if the found path IS the original logged path.
            # This is crucial to avoid deleting the source if it was stored directly in the group path.
            is_target_dir = False
            try:
                # Use resolve() for robust comparison, handles symlinks, '.', '..' etc.
                # This comparison is only meaningful if the original logged path *still exists*.
                # If node_path_in_logger points to a non-existent location, found_path cannot be it.
                if node_path_in_logger.exists():
                    # Resolving might fail if permissions are wrong, hence the inner try/except
                    is_target_dir = found_path.resolve() == node_path_in_logger.resolve()
            except OSError as e:
                # Error resolving paths, cannot be certain it's not the target. Err on safe side.
                logger.error(
                    f'Error resolving path {found_path} or {node_path_in_logger}: {e}. '
                    f"Cannot safely determine if it's the target directory. Skipping removal."
                )
                return

            log_suffix = f" from group directory '{group_path.name}'"

            # Proceed with removal based on what found_path is
            if found_path.is_symlink():
                logger.info(f"Removing symlink '{found_path.name}'{log_suffix}.")
                try:
                    # Unlink works even if the symlink target doesn't exist
                    found_path.unlink()
                    # TODO: Update logger if symlinks are tracked?
                    # self.dump_logger.remove_symlink(...)
                except OSError as e:
                    logger.error(f'Failed to remove symlink {found_path}: {e}')

            elif found_path.is_dir() and not is_target_dir:
                # It's a directory *within* the group structure (likely a copy), and NOT the original. Safe to remove.
                logger.info(f"Removing directory '{found_path.name}'{log_suffix}.")
                try:
                    # Ensure safe_delete_dir handles non-empty dirs and potential errors
                    safe_delete_dir(found_path, safeguard_file='.aiida_node_metadata.yaml')  # Use node safeguard
                except Exception as e:  # Catch specific exceptions from safe_delete_dir if possible
                    logger.error(f'Failed to safely delete directory {found_path}: {e}')

            elif is_target_dir:
                # The path found *is* the primary logged path.
                # Removing the node from a group shouldn't delete its primary data here.
                logger.debug(
                    f'Node {node_uuid} representation found at {found_path} is the primary dump path. '
                    f'It is intentionally not deleted by this operation.'
                )
            else:
                # Exists, but isn't a symlink, and isn't a directory that's safe to remove (e.g., it's a file, or is_target_dir was True but it wasn't a dir?)
                logger.warning(
                    f'Path {found_path} exists but is not a symlink or a directory designated '
                    f'for removal in this context (is_dir={found_path.is_dir()}, is_target_dir={is_target_dir}). Skipping removal.'
                )

        except Exception as e:
            # Catch unexpected errors during the removal logic
            logger.exception(
                f'An unexpected error occurred while processing path {found_path} for node {node_uuid}: {e}'
            )

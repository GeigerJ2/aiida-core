"""Group Mapper Manager implementing SRP by separating mapping from logging."""

from __future__ import annotations

from typing import Dict, List

from aiida import orm
from aiida.common.log import AIIDA_LOGGER
from aiida.tools.dumping.mapping.mapping import GroupNodeMapping

logger = AIIDA_LOGGER.getChild('tools.dump.group_mapper')


class GroupNodeMappingManager:
    """Manager class responsible for handling group-node mappings."""

    def __init__(self, dump_logger):
        """
        Initialize the GroupNodeMappingManager.

        Args:
            dump_logger: The DumpLogger instance to work with
        """
        self.dump_logger = dump_logger
        self.current_mapping = None

    def load_mapping(self) -> None:
        """Load the mapping from the dump logger."""
        self.current_mapping = self.dump_logger.group_node_mapping

    def build_current_mapping(self) -> None:
        """Build a mapping from the current database state and store it."""
        self.current_mapping = self.dump_logger.build_current_group_node_mapping()
        self.dump_logger.group_node_mapping = self.current_mapping

    def compare_mappings(self) -> Dict:
        """
        Compare the stored mapping with the current database state.

        Returns:
            Dict containing the differences between the mappings
        """
        # Get current mapping from DB using direct database query
        # to avoid circular imports with GroupNodeMapping
        stored_mapping = self.dump_logger.group_node_mapping

        # Build a new mapping from the database
        current_mapping = GroupNodeMapping.build_from_db()

        # Compare the mappings
        return stored_mapping.diff(current_mapping)

    def handle_group_updates(self, diff_result: Dict) -> None:
        """
        Update the directory structure and logger based on the mapping differences.

        Args:
            diff_result: The result of the mapping comparison
        """
        # Log the changes
        if diff_result['deleted_groups']:
            logger.report(f"Found {len(diff_result['deleted_groups'])} deleted groups")

        if diff_result['new_groups']:
            logger.report(f"Found {len(diff_result['new_groups'])} new groups")

        if diff_result['modified_groups']:
            logger.report(f"Found {len(diff_result['modified_groups'])} modified groups")

            # Update paths for nodes that changed group membership
            self._update_paths_for_modified_groups(diff_result['modified_groups'],
                                                 diff_result['nodes_membership_changes'])

    def _update_paths_for_modified_groups(self, modified_groups: List[Dict], node_changes: Dict) -> None:
        """
        Update paths for nodes that changed group membership.

        Args:
            modified_groups: List of modified group information
            node_changes: Dictionary of node membership changes
        """
        from aiida.tools.dumping.utils import safe_delete_dir

        for group_info in modified_groups:
            group_uuid = group_info['uuid']

            try:
                # Get the group object
                group = orm.load_group(uuid=group_uuid)
                group_label = group.label

                # Get the group entry from the logger
                group_entry = self.dump_logger.groups.get_entry(group_uuid)
                if group_entry is None:
                    logger.warning(f"Group {group_uuid} not found in logger - skipping updates")
                    continue

                group_path = group_entry.path

                # Handle nodes added to the group
                for node_uuid in group_info.get('nodes_added', []):
                    # Find if node is already dumped elsewhere
                    try:
                        node_path = self.dump_logger.get_dump_path_by_uuid(uuid=node_uuid)
                        if node_path:
                            # Node is already dumped, create symlink or copy to the group directory
                            # This assumes group has a calculations/ or workflows/ subdirectory
                            node = orm.load_node(uuid=node_uuid)
                            if isinstance(node, orm.CalculationNode):
                                target_dir = group_path / 'calculations'
                                target_dir.mkdir(exist_ok=True)
                            elif isinstance(node, orm.WorkflowNode):
                                target_dir = group_path / 'workflows'
                                target_dir.mkdir(exist_ok=True)
                            else:
                                # Skip other node types for now
                                continue

                            # Create symlink to the node
                            # Implementation depends on your config options for symlinking
                            # Here we assume just creating the symlink
                            import os
                            target_path = target_dir / node_path.name
                            if not target_path.exists():
                                os.symlink(node_path, target_path)
                    except Exception as e:
                        logger.warning(f"Error updating node {node_uuid} for group {group_label}: {e!s}")

                # Handle nodes removed from the group
                for node_uuid in group_info.get('nodes_removed', []):
                    try:
                        # Find the node path within the group directory
                        for node_type in ['calculations', 'workflows']:
                            type_dir = group_path / node_type
                            if type_dir.exists():
                                for node_dir in type_dir.iterdir():
                                    # Check if this directory corresponds to the removed node
                                    # This is a simplified approach and might need refinement
                                    metadata_file = node_dir / '.aiida_node_metadata.yaml'
                                    if metadata_file.exists():
                                        import yaml
                                        with open(metadata_file, 'r') as f:
                                            metadata = yaml.safe_load(f)
                                            if metadata.get('Node data', {}).get('uuid') == node_uuid:
                                                # Found the node directory, remove it
                                                safe_delete_dir(
                                                    path=node_dir,
                                                    safeguard_file='.aiida_dump_safeguard'
                                                )
                                                break
                    except Exception as e:
                        logger.warning(f"Error removing node {node_uuid} from group {group_label}: {e!s}")

            except Exception as e:
                logger.warning(f"Error updating group {group_uuid}: {e!s}")

        # Update the group-node mapping in the logger
        self.build_current_mapping()

    def update_group_labels(self) -> None:
        """Update directory structure and mappings when group labels change."""
        # Get all groups from the database
        qb = orm.QueryBuilder()
        qb.append(orm.Group, project=['uuid', 'label'])
        current_groups = {uuid: label for uuid, label in qb.all()}

        # Check each group in the logger
        for group_uuid, entry in self.dump_logger.groups.entries.items():
            if group_uuid in current_groups:
                current_label = current_groups[group_uuid]
                path = entry.path
                old_label = path.name

                # If the label has changed, update paths
                if old_label != current_label:
                    logger.report(f"Updating group label from '{old_label}' to '{current_label}'")
                    self.dump_logger.update_paths(old_str=old_label, new_str=current_label)

    def save_mapping(self) -> None:
        """Save the current mapping to the logger."""
        if self.current_mapping:
            self.dump_logger.group_node_mapping = self.current_mapping

###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################

"""Enhanced group verification with improved handling of group structure changes."""

from __future__ import annotations

from typing import Dict, Optional

from aiida import orm
from aiida.common.log import AIIDA_LOGGER
from aiida.tools.dumping.config import DumpPaths
from aiida.tools.dumping.logger import DumpLogger
from aiida.tools.dumping.utils import safe_delete_dir

logger = AIIDA_LOGGER.getChild('tools.dump.group_verifier')


class GroupDumpVerifier:
    """Class for verifying and updating group structures."""

    def __init__(
        self,
        group: Optional[orm.Group],
        dump_paths: DumpPaths,
        dump_logger: DumpLogger,
    ):
        """
        Initialize the GroupDumpVerifier.

        Args:
            group: The group being verified, or None for ungrouped nodes
            dump_paths: The paths where dumps are stored
            dump_logger: The dump logger instance
        """
        self.group = group
        self.dump_paths = dump_paths
        self.dump_logger = dump_logger
        self.validation_result = None

    def verify_group_nodes(self) -> Dict:
        """
        Verify the group structure by comparing database state with the logged information.

        Returns:
            Dict: Verification results with details about discrepancies
        """
        # Get the differences between stored mapping and current database state
        diff_result = self.dump_logger.verify_group_structure()

        # Check if the specific group (if any) has been modified
        validation_passed = True

        if self.group is not None:
            group_uuid = self.group.uuid

            # Check if the group is in any of the modified/deleted lists
            for deleted_group in diff_result.get('deleted_groups', []):
                if deleted_group.get('uuid') == group_uuid:
                    validation_passed = False
                    break

            for modified_group in diff_result.get('modified_groups', []):
                if modified_group.get('uuid') == group_uuid:
                    validation_passed = False
                    break
        else:
            # For ungrouped nodes, check for any changes
            validation_passed = (
                len(diff_result.get('deleted_groups', [])) == 0 and
                len(diff_result.get('modified_groups', [])) == 0
            )

        # Store and return the validation result
        self.validation_result = {
            'validation_passed': validation_passed,
            'group_changes': {
                'deleted_groups': diff_result.get('deleted_groups', []),
                'new_groups': diff_result.get('new_groups', []),
                'modified_groups': diff_result.get('modified_groups', []),
            },
            'node_changes': diff_result.get('nodes_membership_changes', {}),
        }

        return self.validation_result

    def update_group_structure(self) -> bool:
        """
        Update the directory structure based on verification results.

        Returns:
            bool: True if updates were performed successfully
        """
        if self.validation_result is None:
            self.verify_group_nodes()

        if self.validation_result['validation_passed']:
            logger.report("No updates needed - group structure is consistent")
            return True

        logger.report("Updating group structure based on verification results...")

        # Handle deleted groups
        self._handle_deleted_groups()

        # Handle modified groups
        self._handle_modified_groups()

        # Update the mapping in the logger
        self.dump_logger.group_node_mapping = self.dump_logger.build_current_group_node_mapping()
        self.dump_logger.save_log()

        return True

    def _handle_deleted_groups(self) -> None:
        """Handle groups that have been deleted from the database."""
        deleted_groups = self.validation_result['group_changes']['deleted_groups']

        if not deleted_groups:
            return

        logger.report(f"Processing {len(deleted_groups)} deleted groups")

        for group_info in deleted_groups:
            group_uuid = group_info['uuid']

            # Get the group entry from the logger
            group_entry = self.dump_logger.groups.get_entry(group_uuid)
            if group_entry is None:
                continue

            group_path = group_entry.path

            # Delete the group directory if it exists
            if group_path.exists():
                try:
                    logger.report(f"Deleting directory for removed group: {group_path.name}")
                    safe_delete_dir(
                        path=group_path,
                        safeguard_file='.aiida_dump_safeguard'
                    )
                except Exception as e:
                    logger.warning(f"Error deleting directory for group {group_uuid}: {e!s}")

            # Remove the group from the logger
            self.dump_logger.del_entry(self.dump_logger.groups, group_uuid)

    def _handle_modified_groups(self) -> None:
        """Handle groups with modified node membership."""
        modified_groups = self.validation_result['group_changes']['modified_groups']
        node_changes = self.validation_result['node_changes']

        if not modified_groups:
            return

        logger.report(f"Processing {len(modified_groups)} modified groups")

        from aiida.tools.dumping.group_mapping import GroupNodeMappingManager

        # Create a mapping manager to handle the updates
        mapping_manager = GroupNodeMappingManager(self.dump_logger)
        mapping_manager.handle_group_updates({
            'modified_groups': modified_groups,
            'nodes_membership_changes': node_changes
        })

    def print_validation_results(self) -> None:
        """Print the validation results in a human-readable format."""
        if self.validation_result is None:
            self.verify_group_nodes()

        result = self.validation_result

        print(f"Group structure validation: {'PASSED' if result['validation_passed'] else 'FAILED'}")

        group_changes = result['group_changes']
        node_changes = result['node_changes']

        # Print group changes
        if group_changes['deleted_groups']:
            print('\nDeleted groups:')
            for group in group_changes['deleted_groups']:
                try:
                    print(f"  - UUID: {group.get('uuid', 'Unknown UUID')}")
                    print(f"    Contained {group.get('node_count', 'unknown')} nodes")
                except Exception as e:
                    print(f"  - Error printing group info: {e!s}")

        if group_changes['new_groups']:
            print('\nNew groups:')
            for group in group_changes['new_groups']:
                try:
                    # Try to get the group from DB
                    group_obj = orm.load_group(uuid=group.get('uuid'))
                    print(f"  - {group_obj.label} ({group.get('uuid', 'Unknown UUID')})")
                    print(f"    Contains {group.get('node_count', 'unknown')} nodes")
                except Exception:
                    print(f"  - UUID: {group.get('uuid', 'Unknown UUID')}")
                    print(f"    Contains {group.get('node_count', 'unknown')} nodes")

        if group_changes['modified_groups']:
            print('\nModified groups:')
            for group in group_changes['modified_groups']:
                try:
                    # Try to get the group from DB
                    group_obj = orm.load_group(uuid=group.get('uuid'))
                    print(f"  - {group_obj.label} ({group.get('uuid', 'Unknown UUID')})")
                    print(f"    Nodes added: {group.get('nodes_added_count', 0)}")
                    print(f"    Nodes removed: {group.get('nodes_removed_count', 0)}")
                except Exception:
                    print(f"  - UUID: {group.get('uuid', 'Unknown UUID')}")
                    print(f"    Nodes added: {group.get('nodes_added_count', 0)}")
                    print(f"    Nodes removed: {group.get('nodes_removed_count', 0)}")

        # Print detailed node changes
        if node_changes:
            print('\nDetailed node membership changes:')
            for node_uuid, changes in node_changes.items():
                added_to = changes.get('added_to', [])
                removed_from = changes.get('removed_from', [])

                if added_to:
                    try:
                        node = orm.load_node(uuid=node_uuid)
                        print(f"  - Node {node.pk} ({node_uuid}) added to {len(added_to)} group(s)")
                    except Exception:
                        print(f"  - Node {node_uuid} added to {len(added_to)} group(s)")

                if removed_from:
                    try:
                        node = orm.load_node(uuid=node_uuid)
                        print(f"  - Node {node.pk} ({node_uuid}) removed from {len(removed_from)} group(s)")
                    except Exception:
                        print(f"  - Node {node_uuid} removed from {len(removed_from)} group(s)")

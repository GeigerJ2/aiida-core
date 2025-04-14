###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################

"""Enhanced implementation of GroupNodeMapping to handle group-node relationships."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Set

from aiida import orm


@dataclass
class GroupNodeMapping:
    """Stores the mapping between groups and their member nodes."""

    # Map of group UUID to set of node UUIDs
    group_to_nodes: Dict[str, Set[str]] = field(default_factory=dict)

    # Map of node UUID to set of group UUIDs (for faster lookups)
    node_to_groups: Dict[str, Set[str]] = field(default_factory=dict)

    def add_node_to_group(self, group_uuid: str, node_uuid: str) -> None:
        """Add a node to a group in the mapping."""
        # Add to group->nodes mapping
        if group_uuid not in self.group_to_nodes:
            self.group_to_nodes[group_uuid] = set()
        self.group_to_nodes[group_uuid].add(node_uuid)

        # Add to node->groups mapping
        if node_uuid not in self.node_to_groups:
            self.node_to_groups[node_uuid] = set()
        self.node_to_groups[node_uuid].add(group_uuid)

    def remove_node_from_group(self, group_uuid: str, node_uuid: str) -> None:
        """Remove a node from a group in the mapping."""
        # Remove from group->nodes mapping
        if group_uuid in self.group_to_nodes and node_uuid in self.group_to_nodes[group_uuid]:
            self.group_to_nodes[group_uuid].remove(node_uuid)
            # Clean up empty entries
            if not self.group_to_nodes[group_uuid]:
                del self.group_to_nodes[group_uuid]

        # Remove from node->groups mapping
        if node_uuid in self.node_to_groups and group_uuid in self.node_to_groups[node_uuid]:
            self.node_to_groups[node_uuid].remove(group_uuid)
            # Clean up empty entries
            if not self.node_to_groups[node_uuid]:
                del self.node_to_groups[node_uuid]

    def remove_group(self, group_uuid: str) -> None:
        """Remove a group and all its node associations."""
        if group_uuid not in self.group_to_nodes:
            return

        # Get all nodes in this group
        nodes = self.group_to_nodes[group_uuid].copy()

        # Remove group from each node's groups
        for node_uuid in nodes:
            if node_uuid in self.node_to_groups:
                if group_uuid in self.node_to_groups[node_uuid]:
                    self.node_to_groups[node_uuid].remove(group_uuid)
                # Clean up empty entries
                if not self.node_to_groups[node_uuid]:
                    del self.node_to_groups[node_uuid]

        # Remove the group entry
        del self.group_to_nodes[group_uuid]

    def to_dict(self) -> Dict:
        """Convert to serializable dictionary."""
        return {
            'group_to_nodes': {group_uuid: list(node_uuids) for group_uuid, node_uuids in self.group_to_nodes.items()},
            'node_to_groups': {node_uuid: list(group_uuids) for node_uuid, group_uuids in self.node_to_groups.items()},
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'GroupNodeMapping':
        """Create from serialized dictionary."""
        mapping = cls()

        # Handle old format (backward compatibility)
        if 'group_to_nodes' in data and isinstance(data['group_to_nodes'], dict):
            for group_uuid, node_uuids in data['group_to_nodes'].items():
                for node_uuid in node_uuids:
                    mapping.add_node_to_group(group_uuid, node_uuid)

        # Handle new format with both mappings
        elif isinstance(data, dict):
            # Load group_to_nodes mapping if present
            if 'group_to_nodes' in data and isinstance(data['group_to_nodes'], dict):
                for group_uuid, node_uuids in data['group_to_nodes'].items():
                    for node_uuid in node_uuids:
                        # Just add to the group_to_nodes mapping, we'll rebuild node_to_groups after
                        if group_uuid not in mapping.group_to_nodes:
                            mapping.group_to_nodes[group_uuid] = set()
                        mapping.group_to_nodes[group_uuid].add(node_uuid)

            # Load node_to_groups mapping if present (or rebuild it)
            if 'node_to_groups' in data and isinstance(data['node_to_groups'], dict):
                for node_uuid, group_uuids in data['node_to_groups'].items():
                    for group_uuid in group_uuids:
                        if node_uuid not in mapping.node_to_groups:
                            mapping.node_to_groups[node_uuid] = set()
                        mapping.node_to_groups[node_uuid].add(group_uuid)
            else:
                # If node_to_groups is missing, rebuild it from group_to_nodes
                for group_uuid, node_uuids in mapping.group_to_nodes.items():
                    for node_uuid in node_uuids:
                        if node_uuid not in mapping.node_to_groups:
                            mapping.node_to_groups[node_uuid] = set()
                        mapping.node_to_groups[node_uuid].add(group_uuid)

        return mapping

    def diff(self, other: 'GroupNodeMapping') -> Dict:
        """
        Calculate differences between this mapping and another.

        Returns:
            Dict with the following keys:
            - deleted_groups: groups that exist in self but not in other
            - new_groups: groups that exist in other but not in self
            - modified_groups: groups that exist in both but have different node membership
            - deleted_nodes: nodes that exist in self but not in other
            - new_nodes: nodes that exist in other but not in self
            - nodes_membership_changes: detailed membership changes for nodes
        """
        result = {
            'deleted_groups': [],
            'new_groups': [],
            'modified_groups': [],
            'deleted_nodes': [],
            'new_nodes': [],
            'nodes_membership_changes': {}
        }

        # Check for deleted and new groups
        self_group_uuids = set(self.group_to_nodes.keys())
        other_group_uuids = set(other.group_to_nodes.keys())

        # Groups that exist in self but not in other
        for group_uuid in self_group_uuids - other_group_uuids:
            result['deleted_groups'].append({
                'uuid': group_uuid,
                'node_count': len(self.group_to_nodes.get(group_uuid, [])),
            })

        # Groups that exist in other but not in self
        for group_uuid in other_group_uuids - self_group_uuids:
            result['new_groups'].append({
                'uuid': group_uuid,
                'node_count': len(other.group_to_nodes.get(group_uuid, [])),
            })

        # Check for modified groups (those with different node membership)
        for group_uuid in self_group_uuids & other_group_uuids:
            self_nodes = self.group_to_nodes.get(group_uuid, set())
            other_nodes = other.group_to_nodes.get(group_uuid, set())

            # Check if node membership has changed
            added_nodes = other_nodes - self_nodes
            removed_nodes = self_nodes - other_nodes

            if added_nodes or removed_nodes:
                result['modified_groups'].append({
                    'uuid': group_uuid,
                    'nodes_added': list(added_nodes),
                    'nodes_added_count': len(added_nodes),
                    'nodes_removed': list(removed_nodes),
                    'nodes_removed_count': len(removed_nodes),
                })

                # Track detailed node membership changes
                for node_uuid in added_nodes:
                    if node_uuid not in result['nodes_membership_changes']:
                        result['nodes_membership_changes'][node_uuid] = {'added_to': [], 'removed_from': []}
                    result['nodes_membership_changes'][node_uuid]['added_to'].append(group_uuid)

                for node_uuid in removed_nodes:
                    if node_uuid not in result['nodes_membership_changes']:
                        result['nodes_membership_changes'][node_uuid] = {'added_to': [], 'removed_from': []}
                    result['nodes_membership_changes'][node_uuid]['removed_from'].append(group_uuid)

        # Check for deleted and new nodes
        self_node_uuids = set(self.node_to_groups.keys())
        other_node_uuids = set(other.node_to_groups.keys())

        # Nodes that exist in self but not in other
        for node_uuid in self_node_uuids - other_node_uuids:
            result['deleted_nodes'].append({
                'uuid': node_uuid,
                'groups': list(self.node_to_groups.get(node_uuid, [])),
            })

        # Nodes that exist in other but not in self
        for node_uuid in other_node_uuids - self_node_uuids:
            result['new_nodes'].append({
                'uuid': node_uuid,
                'groups': list(other.node_to_groups.get(node_uuid, [])),
            })

        return result

    @classmethod
    def build_from_db(cls) -> 'GroupNodeMapping':
        """Build a mapping from the current database state."""
        mapping = cls()

        # Query all groups and their nodes
        qb = orm.QueryBuilder()
        qb.append(orm.Group, tag='group', project=['uuid'])
        qb.append(orm.Node, with_group='group', project=['uuid'])

        for group_uuid, node_uuid in qb.all():
            mapping.add_node_to_group(group_uuid, node_uuid)

        return mapping

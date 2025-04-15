###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################
"""Class to collect nodes for dump feature."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aiida import orm
from aiida.common.log import AIIDA_LOGGER
from aiida.tools.dumping.config import NodeDumpGroupScope
from aiida.tools.dumping.storage.keys import DumpStoreKeys
from aiida.tools.dumping.storage.store import DumpNodeStore
from aiida.tools.dumping.detect.strategies import (
    GroupNodeQueryStrategy,
    AnyNodeQueryStrategy,
    UngroupedNodeQueryStrategy,
)

logger = AIIDA_LOGGER.getChild("tools.dumping.detect.detector")


if TYPE_CHECKING:
    pass


class DumpChangeDetector:
    """Detects changes in the database since the last dump"""

    def __init__(self, dump_logger, config):
        self.dump_logger = dump_logger
        self.config = config

    def detect_changes(self, group=None):
        """Detect all changes since last dump"""
        logger.report("Detecting changes since the last dump")

        # Create the appropriate query strategy
        if group is not None:
            query_strategy = GroupNodeQueryStrategy(
                self.dump_logger, self.config, group
            )
        elif self.config.group_scope == NodeDumpGroupScope.NO_GROUP:
            query_strategy = UngroupedNodeQueryStrategy(self.dump_logger, self.config)
        else:
            query_strategy = AnyNodeQueryStrategy(self.dump_logger, self.config)

        # Collect changes
        all_changes = {
            "new_nodes": self.detect_new_nodes(query_strategy),
            "deleted_nodes": self.detect_deleted_nodes(),
            "group_changes": self.detect_group_changes(group),
        }

        return all_changes

    def detect_new_nodes(self, query_strategy):
        """Detect new nodes using the provided query strategy"""
        node_store = DumpNodeStore()

        if self.config.get_processes:
            # Get workflow nodes
            workflows = query_strategy.get_nodes(orm.WorkflowNode, filters=None)

            # Apply top-level filtering if needed
            if self.config.only_top_level_workflows:
                workflows = [wf for wf in workflows if wf.caller is None]

            node_store.workflows = workflows

            # Get calculation nodes
            calculations = query_strategy.get_nodes(orm.CalculationNode, filters=None)

            # Apply top-level filtering if needed
            if self.config.only_top_level_calcs:
                calculations = [calc for calc in calculations if calc.caller is None]

            # Add descendant calculations from workflows if needed
            if workflows and not self.config.only_top_level_calcs:
                descendant_calcs = self.get_workflow_descendants(
                    workflows, target_type=orm.CalculationNode
                )
                calculations = list(set(calculations + descendant_calcs))

            node_store.calculations = calculations

        if self.config.get_data:
            # Future implementation for data nodes
            pass

        return node_store

    def detect_deleted_nodes(self):
        """Detect nodes that have been deleted from the database"""
        delete_node_container = DumpNodeStore()

        for orm_type in (orm.CalculationNode, orm.WorkflowNode, orm.Data, orm.Group):
            store_name = DumpStoreKeys.from_class(orm_class=orm_type)
            dump_store = getattr(self.dump_logger, store_name)
            dumped_uuids = set(dump_store.entries.keys())

            # Find current UUIDs in database
            qb = orm.QueryBuilder()
            qb.append(orm_type, project=["uuid"])
            db_uuids = set(qb.all(flat=True))

            # Only consider UUIDs that were previously dumped
            db_uuids = {uuid for uuid in db_uuids if uuid in dumped_uuids}

            # UUIDs in logger but not in DB anymore
            to_delete_uuids = dumped_uuids - db_uuids
            setattr(delete_node_container, store_name, to_delete_uuids)

        return delete_node_container

    def detect_group_changes(self, specific_group=None):
        """Detect changes in group membership"""
        # Get current mapping from DB
        current_mapping = self.dump_logger.build_current_group_node_mapping()

        # Get the stored mapping
        stored_mapping = self.dump_logger.group_node_mapping

        # Get the diff
        diff_result = stored_mapping.diff(current_mapping)

        # Filter for specific group if needed
        if specific_group:
            return self.filter_diff_for_group(diff_result, specific_group.uuid)

        return diff_result

    def filter_diff_for_group(self, diff_result, group_uuid):
        """Filter diff results for a specific group"""
        filtered_diff = {
            "deleted_groups": [
                g for g in diff_result["deleted_groups"] if g.get("uuid") == group_uuid
            ],
            "modified_groups": [
                g for g in diff_result["modified_groups"] if g.get("uuid") == group_uuid
            ],
            "new_groups": [
                g for g in diff_result["new_groups"] if g.get("uuid") == group_uuid
            ],
            "nodes_membership_changes": {},
        }

        # Filter node membership changes
        for node_uuid, changes in diff_result["nodes_membership_changes"].items():
            added_to = [g for g in changes.get("added_to", []) if g == group_uuid]
            removed_from = [
                g for g in changes.get("removed_from", []) if g == group_uuid
            ]

            if added_to or removed_from:
                filtered_diff["nodes_membership_changes"][node_uuid] = {
                    "added_to": added_to,
                    "removed_from": removed_from,
                }

        return filtered_diff

    def get_workflow_descendants(self, workflows, target_type):
        """Get descendants of workflows matching the target type"""
        descendants = []
        for workflow in workflows:
            for node in workflow.called_descendants:
                if isinstance(node, target_type):
                    descendants.append(node)
        return descendants


# class DumpChangeDetector:
#     def __init__(self, dump_logger: DumpLogger, config: DumpConfig):
#         self.dump_logger: DumpLogger = dump_logger
#         self.config: DumpConfig = config

#     def detect_changes(self, group: orm.Group | None = None):
#         """Detect all changes since last dump."""
#         if group:
#             logger.report(f"Detecting changes for group: {group.label}")

#         if self.dump_logger.dump_times is None:
#             msg = "Getting database structure for the first dumping."
#         else:
#             msg = "Getting changes since the last dumping."
#         logger.report(msg)

#         all_changes = {
#             "new_nodes": self.detect_new_nodes(group=group),
#             "deleted_nodes": self.detect_deleted_nodes(),
#             "group_changes": self.detect_group_changes(specific_group=group),
#         }

#         return all_changes

#     def detect_new_nodes(
#         self, group: orm.Group | None = None, filters: dict | None = None
#     ) -> DumpNodeStore:
#         """Detect nodes that should be dumped based on configuration and group scope."""
#         dump_times = self.dump_logger.dump_times
#         if dump_times.last is None:
#             msg = "For the first dump, this can take a while."
#             logger.report(msg)

#         node_store = DumpNodeStore()

#         # For newly created groups, we need to get all nodes regardless of time filter
#         is_new_group = group is not None and group.uuid not in self.dump_logger.groups.entries

#         if is_new_group:
#             logger.report(f"Detected new group: {group.label} - will dump all nodes in this group")

#             # We'll temporarily modify filters to bypass the mtime filter for new groups
#             if filters is None:
#                 filters = {}

#             # Remove any existing time filters for new groups
#             if 'mtime' in filters:
#                 del filters['mtime']
#         # TODO: Exception occurs here
#         else:
#             # Use normal filters for existing groups
#             if filters is None:
#                 filters = {}

#         if self.config.get_processes:
#             # Get workflow nodes
#             workflows = self.get_nodes(
#                 orm.WorkflowNode,
#                 group=group,
#                 top_level_only=self.config.only_top_level_workflows,
#                 filters=filters,
#             )
#             node_store.workflows = workflows

#             # Get calculation nodes
#             calculations = self.get_nodes(
#                 orm.CalculationNode,
#                 group=group,
#                 top_level_only=self.config.only_top_level_calcs,
#                 filters=filters,
#             )

#             # If not using top-level-only filter, add descendant calculations from workflows
#             if workflows and not self.config.only_top_level_calcs:
#                 descendant_calcs = self._get_workflow_descendant_calcs(workflows)
#                 # Combine and remove duplicates
#                 calculations = list(set(calculations + descendant_calcs))

#             node_store.calculations = calculations

#         if self.config.get_data:
#             msg = "Dumping of data nodes not implemented yet."
#             raise NotImplementedError(msg)

#         return node_store

#     def detect_deleted_nodes(self) -> DumpNodeStore:
#         """ """
#         delete_node_container = DumpNodeStore()

#         for orm_type in (orm.CalculationNode, orm.WorkflowNode, orm.Data, orm.Group):
#             store_name = DumpStoreKeys.from_class(orm_class=orm_type)
#             dump_store = getattr(self.dump_logger, store_name)
#             dumped_uuids = set(dump_store.entries.keys())
#             qb = orm.QueryBuilder()
#             qb.append(orm_type, project=["uuid"])

#             db_uuids = set(qb.all(flat=True))
#             # Ensure that the nodes were _actually_ already dumped in the past
#             db_uuids = set([db_uuid for db_uuid in db_uuids if db_uuid in dumped_uuids])
#             to_delete_uuids = dumped_uuids - db_uuids
#             setattr(delete_node_container, store_name, to_delete_uuids)

#         return delete_node_container

#     def detect_group_changes(self, specific_group: orm.Group | None = None) -> Dict:
#         """Detect changes in group membership."""
#         # Get current mapping from DB
#         current_mapping = self.dump_logger.build_current_group_node_mapping()

#         # Get the stored mapping
#         stored_mapping = self.dump_logger.group_node_mapping

#         # Get the diff between the two mappings
#         diff_result = stored_mapping.diff(current_mapping)

#         # If we're only interested in a specific group, filter the results
#         if specific_group:
#             return self._filter_diff_for_group(diff_result, specific_group.uuid)

#         return diff_result

#     def _filter_diff_for_group(self, diff_result: Dict, group_uuid: str) -> Dict:
#         """Filter diff results for a specific group."""
#         filtered_diff = {
#             "deleted_groups": [
#                 g for g in diff_result["deleted_groups"] if g.get("uuid") == group_uuid
#             ],
#             "modified_groups": [
#                 g for g in diff_result["modified_groups"] if g.get("uuid") == group_uuid
#             ],
#             "new_groups": [
#                 g for g in diff_result["new_groups"] if g.get("uuid") == group_uuid
#             ],
#             "nodes_membership_changes": {},
#         }

#         # Filter node membership changes to only those involving this group
#         for node_uuid, changes in diff_result["nodes_membership_changes"].items():
#             added_to = [g for g in changes.get("added_to", []) if g == group_uuid]
#             removed_from = [
#                 g for g in changes.get("removed_from", []) if g == group_uuid
#             ]

#             if added_to or removed_from:
#                 filtered_diff["nodes_membership_changes"][node_uuid] = {
#                     "added_to": added_to,
#                     "removed_from": removed_from,
#                 }

#         return filtered_diff

#     def _resolve_filters(self, orm_class: Any) -> Dict[str, Any]:
#         """Resolve filters for queries based on configuration."""
#         filters: Dict[str, Any] = {}

#         # Initialize mtime filter as a dictionary
#         mtime_filter: Dict[str, Any] = {}

#         # Add current dump time as upper bound
#         mtime_filter["<="] = self.dump_logger.dump_times.current.astimezone()

#         # Check if we should filter by last dump time
#         if (
#             self.config.filter_by_last_dump_time
#             and not self.dump_logger.dump_times.last
#         ):
#             msg = "Cannot filter by last dump time if no last dump time available. Will not filter nodes by time."
#             logger.debug(msg)

#         # Add last dump time as lower bound if available and configured
#         elif self.config.filter_by_last_dump_time and self.dump_logger.dump_times.last:
#             mtime_filter[">="] = self.dump_logger.dump_times.last.astimezone()

#         # Add the mtime filter to the main filters dictionary
#         filters["mtime"] = mtime_filter

#         # Filter out already logged nodes if dump_logger is available
#         store_key = DumpStoreKeys.from_class(orm_class=orm_class)
#         store = getattr(self.dump_logger, store_key, None)

#         if store and len(store.entries) > 0:
#             filters["uuid"] = {"!in": list(store.entries.keys())}

#         return filters

#     def get_nodes(
#         self,
#         orm_type: Any,
#         group: orm.Group | None = None,
#         top_level_only: bool = False,
#         filters: dict | None = None,
#     ) -> list[Any]:
#         """Get nodes of the specified type based on scope and filters."""
#         # Basic filters for the query
#         if not filters:
#             # Create type-specific filters for the exact node type requested
#             filters = self._resolve_filters(orm_type)

#         # Check if scope is valid
#         if self.config.group_scope not in (
#             NodeDumpGroupScope.IN_GROUP,
#             NodeDumpGroupScope.ANY,
#             NodeDumpGroupScope.NO_GROUP,
#         ):
#             msg = f"Unknown scope: {self.config.group_scope}"
#             raise ValueError(msg)

#         # If scope is IN_GROUP but no group is provided, use ANY scope instead
#         effective_scope = self.config.group_scope
#         if effective_scope == NodeDumpGroupScope.IN_GROUP and group is None:
#             effective_scope = NodeDumpGroupScope.ANY
#             logger.debug(
#                 "Scope is IN_GROUP but no group provided. Using ANY scope instead."
#             )

#         # Special case: if this is a new group (not in logger yet), we need to get all nodes
#         # regardless of any mtime filters to ensure we capture all nodes in the group
#         is_new_group = group is not None and group.uuid not in self.dump_logger.groups.entries
#         if is_new_group and effective_scope == NodeDumpGroupScope.IN_GROUP:
#             logger.report(f"Fetching all nodes for new group: {group.label}")
#             # Remove mtime filters for new groups to get all nodes
#             if 'mtime' in filters:
#                 del filters['mtime']
#             # Remove UUID filters as well to ensure we get all nodes
#             if 'uuid' in filters:
#                 del filters['uuid']

#         # Build query based on scope
#         if effective_scope == NodeDumpGroupScope.IN_GROUP:
#             nodes = self._query_group_nodes(orm_type, group, filters)

#             # Extend "group" nodes to descendants
#             if not self.config.only_top_level_calcs:
#                 descendant_calcs = []
#                 for node in nodes:
#                     if isinstance(node, orm.WorkflowNode):
#                         descendant_calcs.extend(
#                             [
#                                 n
#                                 for n in node.called_descendants
#                                 if isinstance(n, orm.CalculationNode)
#                             ]
#                         )
#                 nodes += descendant_calcs

#             # Extend "group" nodes to descendants
#             if not self.config.only_top_level_workflows:
#                 descendant_wfs = []
#                 for node in nodes:
#                     if isinstance(node, orm.ProcessNode):
#                         descendant_wfs.extend(
#                             [
#                                 n
#                                 for n in node.called_descendants
#                                 if isinstance(n, orm.WorkflowNode)
#                             ]
#                         )
#                 nodes += descendant_wfs

#         elif effective_scope == NodeDumpGroupScope.ANY:
#             nodes = self._query_all_nodes(orm_type, filters)

#         elif effective_scope == NodeDumpGroupScope.NO_GROUP:
#             nodes = self._query_no_group_nodes(orm_type, filters)

#         # Apply top-level filtering if requested
#         if top_level_only:
#             nodes = [node for node in nodes if node.caller is None]

#         return nodes

#     def _query_group_nodes(
#         self,
#         orm_class: QbDumpEntityType,
#         group: orm.Group,
#         filters: Dict[str, Any] = {},
#     ) -> list[Any]:
#         qb = orm.QueryBuilder()
#         qb.append(orm.Group, filters={"id": group.pk}, tag="group")
#         qb.append(orm_class, filters=filters, with_group="group", tag="node")
#         return qb.all(flat=True)

#     def _query_all_nodes(
#         self, orm_class: QbDumpEntityType, filters: Dict[str, Any]
#     ) -> list[Any]:
#         qb = orm.QueryBuilder()
#         qb.append(orm_class, filters=filters, tag="node")
#         return qb.all(flat=True)

#     def _query_no_group_nodes(
#         self, orm_class: QbDumpEntityType, filters: Dict[str, Any]
#     ) -> list[Any]:
#         # First get all nodes
#         all_nodes = self._query_all_nodes(orm_class, filters)

#         # Then get all nodes that are in groups
#         qb = orm.QueryBuilder()
#         qb.append(orm.Group, tag="group")
#         qb.append(orm_class, with_group="group", tag="node")
#         grouped_nodes = qb.all(flat=True)

#         # Also include descendant nodes of process nodes
#         descendant_nodes = []
#         for node in grouped_nodes:
#             if isinstance(node, orm.ProcessNode):
#                 descendant_nodes.extend(node.called_descendants)

#         # Combine and convert to a set for efficient membership checking
#         all_grouped_nodes = set(grouped_nodes + descendant_nodes)

#         # Return only nodes that are not in any group
#         return [node for node in all_nodes if node not in all_grouped_nodes]

#     # NOTE: Should this method be specific to sub-calculations, or should it also include workflows??
#     def _get_workflow_descendant_calcs(
#         self, workflows: list[orm.WorkflowNode]
#     ) -> list[orm.CalculationNode]:
#         descendants: list[orm.CalculationNode] = []
#         for workflow in workflows:
#             for node in workflow.called_descendants:
#                 if isinstance(node, orm.CalculationNode):
#                     descendants.append(node)
#         return descendants

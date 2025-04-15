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

from typing import TYPE_CHECKING, Any, Dict

from aiida import orm
from aiida.common.log import AIIDA_LOGGER
from aiida.tools.dumping.config import NodeDumpGroupScope
from aiida.tools.dumping.storage.keys import DumpStoreKeys
from aiida.tools.dumping.storage.store import DumpNodeStore
from aiida.tools.dumping.utils.types import QbDumpEntityType

logger = AIIDA_LOGGER.getChild("tools.dumping.detector")


if TYPE_CHECKING:
    from aiida.tools.dumping.config import DumpConfig
    from aiida.tools.dumping.storage.logger import DumpLogger

# TODO: Limit to only sealed nodes. This option is currently accessible for `verdi process dump`, but it is not a
# generally exposed option


class DumpChangeDetector:
    def __init__(self, dump_logger: DumpLogger, config: DumpConfig):
        self.dump_logger: DumpLogger = dump_logger
        self.config: DumpConfig = config

    def detect_changes(self, group: orm.Group | None = None):
        """Detect all changes since last dump."""
        # TODO: Why are the changes reported here empty???
        logger.report(f"GROUP: {group}")
        if self.dump_logger.dump_times is None:
            msg = "Getting database structure for the first dumping."
        else:
            msg = "Getting changes since the last dumping."
        logger.report(msg)

        all_changes = {
            "new_nodes": self.detect_new_nodes(group=group),
            "deleted_nodes": self.detect_deleted_nodes(),  # no group argument
            "group_changes": self.detect_group_changes(),  # specific_group=group
        }
        import ipdb; ipdb.set_trace()

        return all_changes

    def detect_new_nodes(
        self, group: orm.Group | None = None, filters: dict | None = None
    ) -> DumpNodeStore:
        # if group:
        #     msg = f'Collecting nodes from the database for group `{group.label}`.'
        # else:
        #     msg = 'Collecting ungrouped nodes from the database.'

        # logger.report(msg)

        dump_times = self.dump_logger.dump_times
        # NOTE: last dump time defined in two places, once, `DumpTimes.last`
        # NOTE: as well as `DumpLogger.last_dump_time`
        # NOTE: Should be fine, though, as in both places, the value is read from the log file, if it exists
        if dump_times.last is None:
            msg = "For the first dump, this can take a while."
            logger.report(msg)

        node_store = DumpNodeStore()

        if self.config.get_processes:
            # Get workflow nodes
            workflows = self.get_nodes(
                orm.WorkflowNode,
                group=group,
                top_level_only=self.config.only_top_level_workflows,
                filters=filters,
            )
            node_store.workflows = workflows

            # Get calculation nodes
            calculations = self.get_nodes(
                orm.CalculationNode,
                group=group,
                top_level_only=self.config.only_top_level_calcs,
                filters=filters,
            )

            # If not using top-level-only filter, add descendant calculations from workflows
            if workflows and not self.config.only_top_level_calcs:
                descendant_calcs = self._get_workflow_descendant_calcs(workflows)
                # Combine and remove duplicates
                calculations = list(set(calculations + descendant_calcs))

            node_store.calculations = calculations

        if self.config.get_data:
            msg = "Dumping of data nodes not implemented yet."
            raise NotImplementedError(msg)

        return node_store

    def detect_deleted_nodes(self) -> DumpNodeStore:
        """ """
        delete_node_container = DumpNodeStore()

        for orm_type in (orm.CalculationNode, orm.WorkflowNode, orm.Data, orm.Group):
            store_name = DumpStoreKeys.from_class(orm_class=orm_type)
            dump_store = getattr(self.dump_logger, store_name)
            dumped_uuids = set(dump_store.entries.keys())
            qb = orm.QueryBuilder()
            qb.append(orm_type, project=["uuid"])

            db_uuids = set(qb.all(flat=True))
            # Ensure that the nodes were _actually_ already dumped in the past
            db_uuids = set([db_uuid for db_uuid in db_uuids if db_uuid in dumped_uuids])
            to_delete_uuids = dumped_uuids - db_uuids
            setattr(delete_node_container, store_name, to_delete_uuids)

        return delete_node_container

    def detect_group_changes(self, specific_group: orm.Group | None = None) -> Dict:
        """Detect changes in group membership."""
        # TODO: Maybe define a dedicated container for the `group_changes` here, similar to the `DumpNodeStore`
        # Get current mapping from DB
        current_mapping = self.dump_logger.build_current_group_node_mapping()

        # Get the stored mapping
        stored_mapping = self.dump_logger.group_node_mapping

        # Get the diff between the two mappings
        diff_result = stored_mapping.diff(current_mapping)

        # If we're only interested in a specific group, filter the results
        if specific_group:
            return self._filter_diff_for_group(diff_result, specific_group.uuid)

        return diff_result

    def _filter_diff_for_group(self, diff_result: Dict, group_uuid: str) -> Dict:
        """Filter diff results for a specific group."""
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

        # Filter node membership changes to only those involving this group
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

    def _resolve_filters(self, orm_class: QbDumpEntityType) -> Dict[str, Any]:
        filters: Dict[str, Any] = {}
        orm_key = DumpStoreKeys.from_class(orm_class=orm_class)

        # Initialize mtime filter as a dictionary
        mtime_filter: Dict[str, Any] = {}

        # Add current dump time as upper bound
        mtime_filter["<="] = self.dump_logger.dump_times.current.astimezone()

        # This might be too annoying to log always, and raising here would require manually setting
        # `filter-by-last-dump-time` to False for the first dump
        if (
            self.config.filter_by_last_dump_time
            and not self.dump_logger.dump_times.last
        ):
            msg = "Cannot filter by last dump time if no last dump time available. Will not filter nodes by time."
            logger.debug(msg)

        # Add last dump time as lower bound if available and configured
        elif self.config.filter_by_last_dump_time and self.dump_logger.dump_times.last:
            mtime_filter[">="] = self.dump_logger.dump_times.last.astimezone()

        # Add the mtime filter to the main filters dictionary
        filters["mtime"] = mtime_filter

        # Filter out already logged nodes if dump_logger is available
        store = getattr(self.dump_logger, orm_key)
        if len(store) > 0:
            filters["uuid"] = {"!in": list(store.entries.keys())}

        return filters

    def get_nodes(
        self,
        orm_type: QbDumpEntityType,
        group: orm.Group | None = None,
        top_level_only: bool = False,
        filters: dict | None = None,
    ) -> list[Any]:
        # Basic filters for the query
        if not filters:
            filters = self._resolve_filters(orm_type)

        # Check if scope is valid
        if self.config.group_scope not in (
            NodeDumpGroupScope.IN_GROUP,
            NodeDumpGroupScope.ANY,
            NodeDumpGroupScope.NO_GROUP,
        ):
            msg = f"Unknown scope: {self.config.group_scope}"
            raise ValueError(msg)

        # If scope is IN_GROUP but no group is provided, use ANY scope instead
        effective_scope = self.config.group_scope
        if effective_scope == NodeDumpGroupScope.IN_GROUP and group is None:
            effective_scope = NodeDumpGroupScope.ANY
            logger.debug(
                "Scope is IN_GROUP but no group provided. Using ANY scope instead."
            )

        # Build query based on scope
        if effective_scope == NodeDumpGroupScope.IN_GROUP:
            nodes = self._query_group_nodes(orm_type, group, filters)

            # Extend "group" nodes to descendants
            if not self.config.only_top_level_calcs:
                descendant_calcs = []
                for node in nodes:
                    if isinstance(node, orm.WorkflowNode):
                        descendant_calcs.extend(
                            [
                                n
                                for n in node.called_descendants
                                if isinstance(n, orm.CalculationNode)
                            ]
                        )
                nodes += descendant_calcs

            # Extend "group" nodes to descendants
            if not self.config.only_top_level_workflows:
                descendant_wfs = []
                for node in nodes:
                    if isinstance(node, orm.ProcessNode):
                        descendant_wfs.extend(
                            [
                                n
                                for n in node.called_descendants
                                if isinstance(n, orm.WorkflowNode)
                            ]
                        )
                nodes += descendant_wfs

        elif effective_scope == NodeDumpGroupScope.ANY:
            nodes = self._query_all_nodes(orm_type, filters)

        elif effective_scope == NodeDumpGroupScope.NO_GROUP:
            nodes = self._query_no_group_nodes(orm_type, filters)

        # Apply top-level filtering if requested
        if top_level_only:
            nodes = [node for node in nodes if node.caller is None]

        return nodes

    def _query_group_nodes(
        self,
        orm_class: QbDumpEntityType,
        group: orm.Group,
        filters: Dict[str, Any] = {},
    ) -> list[Any]:
        qb = orm.QueryBuilder()
        qb.append(orm.Group, filters={"id": group.pk}, tag="group")
        qb.append(orm_class, filters=filters, with_group="group", tag="node")
        return qb.all(flat=True)

    def _query_all_nodes(
        self, orm_class: QbDumpEntityType, filters: Dict[str, Any]
    ) -> list[Any]:
        qb = orm.QueryBuilder()
        qb.append(orm_class, filters=filters, tag="node")
        return qb.all(flat=True)

    def _query_no_group_nodes(
        self, orm_class: QbDumpEntityType, filters: Dict[str, Any]
    ) -> list[Any]:
        # First get all nodes
        all_nodes = self._query_all_nodes(orm_class, filters)

        # Then get all nodes that are in groups
        qb = orm.QueryBuilder()
        qb.append(orm.Group, tag="group")
        qb.append(orm_class, with_group="group", tag="node")
        grouped_nodes = qb.all(flat=True)

        # Also include descendant nodes of process nodes
        descendant_nodes = []
        for node in grouped_nodes:
            if isinstance(node, orm.ProcessNode):
                descendant_nodes.extend(node.called_descendants)

        # Combine and convert to a set for efficient membership checking
        all_grouped_nodes = set(grouped_nodes + descendant_nodes)

        # Return only nodes that are not in any group
        return [node for node in all_nodes if node not in all_grouped_nodes]

    # NOTE: Should this method be specific to sub-calculations, or should it also include workflows??
    def _get_workflow_descendant_calcs(
        self, workflows: list[orm.WorkflowNode]
    ) -> list[orm.CalculationNode]:
        descendants: list[orm.CalculationNode] = []
        for workflow in workflows:
            for node in workflow.called_descendants:
                if isinstance(node, orm.CalculationNode):
                    descendants.append(node)
        return descendants

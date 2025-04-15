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
from aiida.tools.dumping.storage.store import DumpNodeStore, DeletedEntityStore
from aiida.tools.dumping.detect.strategies import (
    GroupNodeQueryStrategy,
    AnyNodeQueryStrategy,
    UngroupedNodeQueryStrategy,
)

logger = AIIDA_LOGGER.getChild("tools.dumping.detect.detector")


if TYPE_CHECKING:
    from aiida.tools.dumping.config import DumpConfig
    from aiida.tools.dumping.utils.paths import DumpPaths
    from aiida.tools.dumping.storage.logger import DumpLogger, DumpLogStore
    from aiida.tools.dumping.storage.store import DumpNodeStore

class DumpChangeDetector:
    """Detects changes in the database since the last dump"""

    def __init__(self, dump_logger: DumpLogger, config: DumpConfig) -> None:
        self.dump_logger: DumpLogger = dump_logger
        self.config: DumpConfig = config

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
        delete_node_container = DeletedEntityStore()

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

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

from typing import TYPE_CHECKING, Set, Optional, List

from aiida import orm
from aiida.orm.querybuilder import QueryBuilder
from aiida.tools.dumping.utils.types import GroupChangeInfo, NodeChanges, DumpChanges, NodeMembershipChange
from aiida.tools.dumping.config import NodeDumpGroupScope
from aiida.tools.dumping.utils.types import DumpNodeStore, DumpStoreKeys
from aiida.common.log import AIIDA_LOGGER
from .strategies import (
    NodeQueryStrategy,
    GroupNodeQueryStrategy,
    AnyNodeQueryStrategy,
    UngroupedNodeQueryStrategy,
)

logger = AIIDA_LOGGER.getChild("tools.dumping.detect.detector")

if TYPE_CHECKING:
    from aiida.tools.dumping.config import DumpConfig
    from aiida.tools.dumping.storage.logger import DumpLogger


class DumpChangeDetector:
    """Detects changes in the database since the last dump"""

    def __init__(self, dump_logger: DumpLogger, config: DumpConfig) -> None:
        self.dump_logger: DumpLogger = dump_logger
        self.config: DumpConfig = config

    def detect_deleted_nodes(self) -> Set[str]:
        """Detect nodes (CalcJobNode, WorkflowNode, DataNode) deleted from DB."""
        logger.debug("Detecting deleted nodes...")
        deleted_node_uuids: Set[str] = set()

        # Check node types only
        for orm_type in (orm.CalculationNode, orm.WorkflowNode, orm.Data):
            store_name = DumpStoreKeys.from_class(orm_class=orm_type)
            dump_store = getattr(self.dump_logger, store_name, None)

            if not dump_store:
                logger.debug(f"No logger store found for {store_name}, skipping deletion check.")
                continue

            dumped_uuids = set(dump_store.entries.keys())
            if not dumped_uuids:
                logger.debug(f"No dumped UUIDs found in store {store_name}, skipping deletion check.")
                continue

            # Find current UUIDs in database for this type
            try:
                qb = QueryBuilder()
                qb.append(orm_type, project=['uuid'])
                all_db_uuids_for_type = set(qb.all(flat=True))
            except Exception as e:
                 logger.warning(f"Database query failed for deleted nodes check on {orm_type.__name__}: {e}")
                 continue # Skip this type on error

            # Find UUIDs logged previously but now missing from DB
            missing_uuids = dumped_uuids - all_db_uuids_for_type
            if missing_uuids:
                logger.debug(f"Detected {len(missing_uuids)} deleted nodes of type {orm_type.__name__}")
                deleted_node_uuids.update(missing_uuids)

        logger.debug(f"Total deleted node UUIDs detected: {len(deleted_node_uuids)}")
        return deleted_node_uuids

    def detect_group_changes(
        self, specific_group: Optional[orm.Group] = None
    ) -> GroupChangeInfo:
        """Detect changes in group membership using mapping. Returns GroupChangeInfo."""
        logger.debug("Detecting group changes...")
        # Ensure mapping is built/available
        current_mapping = self.dump_logger.build_current_group_node_mapping()
        stored_mapping = self.dump_logger.group_node_mapping # Use property access

        if stored_mapping is None:
            logger.debug("No stored group mapping found, creating empty one.")
            from aiida.tools.dumping.mapping import GroupNodeMapping # Local import if needed
            stored_mapping = GroupNodeMapping()

        # Get the diff (assumes GroupNodeMapping.diff now returns GroupChangeInfo)
        try:
            diff_result: GroupChangeInfo = stored_mapping.diff(current_mapping)
            logger.debug("Group mapping diff calculated.")
        except Exception as e:
            logger.error(f"Error calculating group mapping diff: {e}")
            # Return empty changes on error
            return GroupChangeInfo()

        if specific_group:
            logger.debug(f"Filtering group changes for specific group: {specific_group.uuid}")
            return self.filter_group_changes_for_group(diff_result, specific_group.uuid)
        else:
            return diff_result

    def filter_group_changes_for_group(
        self, changes: GroupChangeInfo, group_uuid: str
    ) -> GroupChangeInfo:
         """Filter GroupChangeInfo results for a specific group."""
         logger.debug(f"Filtering GroupChangeInfo for group UUID: {group_uuid}")
         # Create a new filtered object
         filtered_changes = GroupChangeInfo(
             deleted = [g for g in changes.deleted if g.uuid == group_uuid],
             new = [g for g in changes.new if g.uuid == group_uuid],
             modified = [g for g in changes.modified if g.uuid == group_uuid],
             # Rebuild the node_membership dict, filtering involved nodes and changes
             node_membership = {} # Start empty
         )
         for node_uuid, membership in changes.node_membership.items():
              involved = False
              # Create filtered membership details for this node
              filtered_membership = NodeMembershipChange()
              if group_uuid in membership.added_to:
                   filtered_membership.added_to.append(group_uuid)
                   involved = True
              if group_uuid in membership.removed_from:
                   filtered_membership.removed_from.append(group_uuid)
                   involved = True

              # Only add the node to the filtered dict if this group was involved
              if involved:
                   filtered_changes.node_membership[node_uuid] = filtered_membership

         logger.debug(f"Filtered group changes: {filtered_changes}")
         return filtered_changes

    def detect_changes(self, group: Optional[orm.Group] = None) -> DumpChanges:
        """Detect all changes and return a structured DumpChanges object."""
        logger.info("Starting change detection...")
        query_strategy: GroupNodeQueryStrategy | UngroupedNodeQueryStrategy | AnyNodeQueryStrategy

        # 1. Determine Query Strategy
        if group is not None:
            query_strategy = GroupNodeQueryStrategy(self.dump_logger, self.config, group)
        elif self.config.group_scope == NodeDumpGroupScope.NO_GROUP:
            query_strategy = UngroupedNodeQueryStrategy(self.dump_logger, self.config)
        else: # ANY or default
            query_strategy = AnyNodeQueryStrategy(self.dump_logger, self.config)
        logger.debug(f"Using query strategy: {type(query_strategy).__name__}")

        # 2. Detect New/Modified Nodes
        # Assuming detect_new_nodes returns DumpNodeStore populated correctly
        try:
            new_nodes_store: DumpNodeStore = self.detect_new_nodes(query_strategy)
            logger.debug(f"Detected {len(new_nodes_store)} new/modified nodes.")
        except Exception as e:
            logger.error(f"Error detecting new nodes: {e}", exc_info=True)
            new_nodes_store = DumpNodeStore() # Default to empty on error

        # 3. Detect Deleted Nodes (returns Set[str] of node UUIDs)
        try:
            deleted_node_uuids: Set[str] = self.detect_deleted_nodes()
            logger.debug(f"Detected {len(deleted_node_uuids)} deleted node UUIDs.")
        except Exception as e:
            logger.error(f"Error detecting deleted nodes: {e}", exc_info=True)
            deleted_node_uuids = set() # Default to empty on error

        # 4. Detect Group Changes (returns GroupChangeInfo object)
        try:
            group_changes_info: GroupChangeInfo = self.detect_group_changes(specific_group=group)
            logger.debug("Group changes detection complete.")
        except Exception as e:
            logger.error(f"Error detecting group changes: {e}", exc_info=True)
            group_changes_info = GroupChangeInfo() # Default to empty on error

        # 5. Assemble the results into the final structure
        node_changes = NodeChanges(
            new_or_modified=new_nodes_store,
            deleted=deleted_node_uuids # Assign the Set[str] here
        )

        dump_changes = DumpChanges(
            nodes=node_changes,         # NodeChanges object
            groups=group_changes_info   # GroupChangeInfo object
        )

        logger.info("Change detection finished.")
        return dump_changes

    def detect_new_nodes(self, query_strategy: NodeQueryStrategy) -> DumpNodeStore:
        """Detect new nodes using the provided query strategy"""
        # Implementation from previous response - ensure it returns DumpNodeStore
        # Make sure DumpNodeStore is imported correctly
        # from ..storage import DumpNodeStore # Already imported above

        node_store = DumpNodeStore()
        logger.debug("Detecting new nodes...")

        if self.config.get_processes:
            # Get workflow nodes
            logger.debug("Querying workflow nodes...")
            try:
                 workflows = query_strategy.get_nodes(orm.WorkflowNode, filters=None) # Pass filters if needed
                 if self.config.only_top_level_workflows:
                      workflows = [wf for wf in workflows if getattr(wf, 'caller', None) is None]
                 node_store.workflows = workflows
                 logger.debug(f"Found {len(workflows)} workflow nodes.")
            except Exception as e:
                 logger.warning(f"Failed to query workflow nodes: {e}")


            # Get calculation nodes
            logger.debug("Querying calculation nodes...")
            try:
                 calculations = query_strategy.get_nodes(orm.CalculationNode, filters=None) # Pass filters if needed
                 if self.config.only_top_level_calcs:
                      calculations = [calc for calc in calculations if getattr(calc, 'caller', None) is None]

                 # Add descendant calculations from workflows if needed
                 if workflows and not self.config.only_top_level_calcs:
                      logger.debug("Fetching workflow descendant calculations...")
                      descendant_calcs = self.get_workflow_descendants(
                           workflows, target_type=orm.CalculationNode
                      )
                      # Combine and remove duplicates (maintaining order approximately)
                      calculations = list(dict.fromkeys(calculations + descendant_calcs))

                 node_store.calculations = calculations
                 logger.debug(f"Found {len(calculations)} calculation nodes.")
            except Exception as e:
                 logger.warning(f"Failed to query calculation nodes: {e}")

        if self.config.get_data:
            logger.warning("Data node detection is not fully implemented.")
            # try:
            #     data_nodes = query_strategy.get_nodes(orm.Data, filters=None)
            #     node_store.data = data_nodes
            #     logger.debug(f"Found {len(data_nodes)} data nodes.")
            # except Exception as e:
            #     logger.warning(f"Failed to query data nodes: {e}")
            pass # Placeholder

        logger.debug("Finished detecting new nodes.")
        return node_store

    # Ensure get_workflow_descendants method exists if called
    def get_workflow_descendants(self, workflows: List[orm.WorkflowNode], target_type) -> List[orm.Node]:
         """Get descendants of workflows matching the target type"""
         descendants = []
         logger.debug(f"Getting descendants of type {target_type.__name__} for {len(workflows)} workflows.")
         for workflow in workflows:
             try:
                 # Check if attribute exists before accessing
                 if hasattr(workflow, 'called_descendants'):
                      for node in workflow.called_descendants:
                           if isinstance(node, target_type):
                                descendants.append(node)
                 else:
                      logger.warning(f"Workflow {workflow.pk} does not have 'called_descendants' attribute.")
             except Exception as e:
                  logger.warning(f"Could not get descendants for workflow {workflow.pk}: {e}")
         logger.debug(f"Found {len(descendants)} relevant descendants.")
         return descendants

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

from typing import TYPE_CHECKING, Optional, Set

from aiida import orm
from aiida.common.log import AIIDA_LOGGER
from aiida.orm.querybuilder import QueryBuilder
from aiida.tools.dumping.config import NodeDumpGroupScope
from aiida.tools.dumping.mapping.group import GroupNodeMapping
from aiida.tools.dumping.utils.time import DumpTimes
from aiida.tools.dumping.utils.types import (
    DumpNodeStore,
    DumpStoreKeys,
    GroupChanges,
    NodeChanges,
    NodeMembershipChange,
)

from .strategies import (
    AnyNodeQueryStrategy,
    GroupNodeQueryStrategy,
    NodeQueryStrategy,
    UngroupedNodeQueryStrategy,
)

logger = AIIDA_LOGGER.getChild('tools.dumping.detect.detector')

if TYPE_CHECKING:
    from aiida.tools.dumping.config import DumpConfig
    from aiida.tools.dumping.storage.logger import DumpLogger


class DumpChangeDetector:
    """Detects changes in the database since the last dump"""

    def __init__(self, dump_logger: DumpLogger, config: DumpConfig, dump_times: DumpTimes) -> None:
        self.dump_logger: DumpLogger = dump_logger
        self.config: DumpConfig = config
        self.dump_times: DumpTimes = dump_times

    def detect_new_nodes(self, query_strategy: NodeQueryStrategy) -> DumpNodeStore:
        """Detect new nodes using the provided query strategy."""
        node_store = DumpNodeStore()
        logger.debug(f'Detecting new/modified nodes using {type(query_strategy).__name__}...')

        # --- Query Initial Nodes ---
        nodes_to_query: list[tuple[type, str]] = []  # Store type and key
        if self.config.get_processes:
            nodes_to_query.extend([(orm.WorkflowNode, 'workflows'), (orm.CalculationNode, 'calculations')])
        if self.config.get_data:
            logger.warning('Data node detection is not fully implemented.')
            # nodes_to_query.append((orm.Data, 'data'))

        initial_nodes: dict[str, list] = {'workflows': [], 'calculations': [], 'data': []}
        for orm_type, store_key in nodes_to_query:
            logger.debug(f'Querying nodes of type {orm_type.__name__}...')
            try:
                # Strategy gets nodes based on scope and base filters (time/UUID)
                # AND applies top-level filtering if applicable (via Any/Ungrouped strategy)
                nodes = query_strategy.get_nodes(orm_type, dump_times=self.dump_times)
                logger.debug(f'Strategy returned {len(nodes)} candidate nodes of type {orm_type.__name__}.')
                initial_nodes[store_key] = nodes
            except Exception as e:
                logger.warning(f'Failed to query/filter nodes of type {orm_type.__name__}: {e}')

        # --- Add Calculation Descendants if Required ---
        workflows_found = initial_nodes['workflows']
        # Add descendants only if processing processes AND only_top_level_calcs is FALSE
        if self.config.get_processes and not self.config.only_top_level_calcs and workflows_found:
            logger.debug(
                f'Fetching calculation descendants for {len(workflows_found)} workflows (only_top_level_calcs=False).'
            )
            all_calc_descendants = []
            # Ensure workflows_found contains actual WorkflowNode instances
            valid_workflows = [wf for wf in workflows_found if isinstance(wf, orm.WorkflowNode)]
            if valid_workflows:
                descendants = self.get_calculation_descendants(valid_workflows)
                all_calc_descendants.extend(descendants)
                logger.debug(f'Found {len(all_calc_descendants)} calculation descendants.')

                # Add unique descendants to the initial calculations list
                existing_calc_uuids = {calc.uuid for calc in initial_nodes['calculations']}
                unique_new_descendants = [desc for desc in all_calc_descendants if desc.uuid not in existing_calc_uuids]
                if unique_new_descendants:
                    logger.debug(
                        f'Adding {len(unique_new_descendants)} unique calculation descendants to be processed.'
                    )
                    initial_nodes['calculations'].extend(unique_new_descendants)
                else:
                    logger.debug('No *new* unique calculation descendants found.')
            else:
                logger.debug('No valid WorkflowNode instances found to fetch descendants from.')

        # --- Populate final Node Store ---
        node_store.workflows = initial_nodes['workflows']
        node_store.calculations = initial_nodes['calculations']
        node_store.data = initial_nodes['data']

        logger.debug('Finished detecting new/modified nodes.')
        return node_store

    def detect_deleted_nodes(self) -> Set[str]:
        """Detect nodes (CalcJobNode, WorkflowNode, DataNode) deleted from DB."""
        logger.debug('Detecting deleted nodes...')
        deleted_node_uuids: Set[str] = set()

        # Check node types only
        for orm_type in (orm.CalculationNode, orm.WorkflowNode, orm.Data):
            store_name = DumpStoreKeys.from_class(orm_class=orm_type)

            dump_store = self.dump_logger.get_store_by_name(name=store_name)

            if not dump_store:
                logger.debug(f'No logger store found for {store_name}, skipping deletion check.')
                continue

            dumped_uuids = set(dump_store.entries.keys())
            if not dumped_uuids:
                logger.debug(f'No dumped UUIDs found in store {store_name}, skipping deletion check.')
                continue

            # Find current UUIDs in database for this type
            try:
                qb = QueryBuilder()
                qb.append(orm_type, project=['uuid'])
                all_db_uuids_for_type = set(qb.all(flat=True))
            except Exception as e:
                logger.warning(f'Database query failed for deleted nodes check on {orm_type.__name__}: {e}')
                continue  # Skip this type on error

            # Find UUIDs logged previously but now missing from DB
            missing_uuids = dumped_uuids - all_db_uuids_for_type
            if missing_uuids:
                logger.debug(f'Detected {len(missing_uuids)} deleted nodes of type {orm_type.__name__}')
                deleted_node_uuids.update(missing_uuids)

        logger.debug(f'Total deleted node UUIDs detected: {len(deleted_node_uuids)}')
        return deleted_node_uuids

    def detect_group_changes(
        self,
        stored_mapping: GroupNodeMapping | None,
        current_mapping: GroupNodeMapping,  # Current mapping must be provided
        specific_group_uuid: str | None = None,
    ) -> GroupChanges:
        """Detect changes between stored and current group mappings."""
        logger.debug('Calculating group changes diff...')

        if stored_mapping is None:
            logger.debug('No stored group mapping provided, creating empty one for diff.')
            stored_mapping = GroupNodeMapping()  # Diff against empty mapping

        # Get the diff using GroupNodeMapping's method
        try:
            diff_result: GroupChanges = stored_mapping.diff(current_mapping)
            logger.debug(
                f'Group mapping diff calculated: {len(diff_result.new)} new, {len(diff_result.deleted)} deleted, {len(diff_result.modified)} modified.'
            )
        except Exception as e:
            logger.error(f'Error calculating group mapping diff: {e}')
            return GroupChanges()  # Return empty changes on error

        if specific_group_uuid:
            logger.debug(f'Filtering group changes for specific group UUID: {specific_group_uuid}')
            return self.filter_group_changes_for_group(diff_result, specific_group_uuid)
        else:
            return diff_result

    def detect_changes(
        self, group: Optional[orm.Group] = None
    ) -> tuple[NodeChanges, GroupNodeMapping]:  # MODIFIED return type
        """
        Detect node changes (new/modified/deleted) and return them along with
        the current group mapping state.

        Args:
            group: Optional group to limit the scope of node detection.

        Returns:
            A tuple containing:
                - NodeChanges: Object holding new/modified nodes and deleted node UUIDs.
                - GroupNodeMapping: The current mapping of groups to nodes from the DB.
        """
        logger.info('Starting node change detection...')

        # --- Pre-computation: Group Mapping ---
        # Build the current mapping once (needed for some strategies/filtering later)
        try:
            current_group_mapping = GroupNodeMapping.build_from_db()
            logger.debug('Successfully built current group-node mapping from DB.')
        except Exception as e:
            logger.error(f'Failed to build current group-node mapping: {e}', exc_info=True)
            current_group_mapping = GroupNodeMapping()  # Proceed with empty

        # Determine Query Strategy
        query_strategy: NodeQueryStrategy
        if group is not None:
            query_strategy = GroupNodeQueryStrategy(self.dump_logger, self.config, group)
        elif self.config.group_scope == NodeDumpGroupScope.NO_GROUP:
            query_strategy = UngroupedNodeQueryStrategy(self.dump_logger, self.config)
        else:  # ANY or default
            query_strategy = AnyNodeQueryStrategy(self.dump_logger, self.config)
        logger.debug(f'Using query strategy: {type(query_strategy).__name__}')

        # --- Detect Node Change Categories ---

        # 1. Detect New/Modified Nodes using the chosen strategy
        try:
            new_nodes_store: DumpNodeStore = self.detect_new_nodes(query_strategy)
            logger.debug(f'Detected {len(new_nodes_store)} new/modified nodes.')
        except Exception as e:
            logger.error(f'Error detecting new nodes: {e}', exc_info=True)
            new_nodes_store = DumpNodeStore()

        # 2. Detect Deleted Nodes (UUIDs only)
        try:
            deleted_node_uuids: Set[str] = self.detect_deleted_nodes()
            logger.debug(f'Detected {len(deleted_node_uuids)} deleted node UUIDs.')
        except Exception as e:
            logger.error(f'Error detecting deleted nodes: {e}', exc_info=True)
            deleted_node_uuids = set()

        # --- Assemble the NodeChanges object ---
        node_changes = NodeChanges(
            new_or_modified=new_nodes_store,
            deleted=deleted_node_uuids,
        )

        # --- Return NodeChanges and current mapping ---
        logger.info('Node change detection finished.')
        # Group changes (diff) are calculated separately by the engine
        return node_changes, current_group_mapping  # MODIFIED return value

    def filter_group_changes_for_group(self, changes: GroupChanges, group_uuid: str) -> GroupChanges:
        """Filter GroupChangeInfo results for a specific group."""
        logger.debug(f'Filtering GroupChangeInfo for group UUID: {group_uuid}')
        # Create a new filtered object
        filtered_changes = GroupChanges(
            deleted=[g for g in changes.deleted if g.uuid == group_uuid],
            new=[g for g in changes.new if g.uuid == group_uuid],
            modified=[g for g in changes.modified if g.uuid == group_uuid],
            # Rebuild the node_membership dict, filtering involved nodes and changes
            node_membership={},  # Start empty
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

        logger.debug(f'Filtered group changes: {filtered_changes}')
        return filtered_changes

    def get_calculation_descendants(self, workflows: list[orm.WorkflowNode]) -> list[orm.CalculationNode]:
        """Get CalculationNode descendants of the provided workflows."""
        descendants = []
        for workflow in workflows:
             try:
                  # Using iter_descendants is generally safer and more flexible
                  for node in workflow.called_descendants:
                       if isinstance(node, orm.CalculationNode):
                            descendants.append(node)
             except Exception as e:
                  logger.warning(f"Could not get descendants for workflow {workflow.pk}: {e}")
        # Remove duplicates based on UUID, preserving order roughly
        unique_descendants = list({node.uuid: node for node in descendants}.values())
        return unique_descendants

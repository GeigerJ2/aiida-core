from typing import cast

from aiida import orm
from aiida.common.log import AIIDA_LOGGER
from aiida.orm import QueryBuilder
from aiida.tools.dumping.logger import DumpLogger
from aiida.tools.dumping.strategies.base import DumpStrategy
from aiida.tools.dumping.utils.paths import get_directory_stats
from aiida.tools.dumping.utils.types import DumpChanges, DumpNodeStore

logger = AIIDA_LOGGER.getChild('tools.dumping.strategies.profile')


class ProfileDumpStrategy(DumpStrategy):
    """Strategy for dumping an entire profile."""

    def dump(self, changes: DumpChanges, dump_logger: DumpLogger) -> None:
        """Dumps the entire profile."""
        logger.info('Executing ProfileDumpStrategy')

        # --- Process Group Changes Lifecycle ---
        logger.info('Processing group lifecycle and membership changes...')
        self.engine.group_manager.handle_group_changes(changes.groups)

        # NOTE: Always update groups -> See if this degrades performance, if so, make optional
        # if self.engine.config.update_groups:
        #     logger.info('Processing group lifecycle and membership changes...')
        #     self.engine.group_manager.handle_group_changes(changes.groups)
        # else:
        #     logger.info('Skipping processing of group lifecycle changes.')

        # --- Process Nodes within Groups ---
        logger.info('Processing nodes within groups...')
        all_groups: list[orm.Group]
        try:
            qb_groups = QueryBuilder().append(orm.Group)
            all_groups = cast(list[orm.Group], qb_groups.all(flat=True))

            logger.info(f'Processing {len(all_groups)} groups found in the profile.')
        except Exception as e:
            logger.error(f'Failed to query groups from database: {e}', exc_info=True)
            all_groups = []

        current_mapping = self.engine.current_mapping  # Get current mapping

        for group in all_groups:
            logger.debug(f'Processing group: {group.label} ({group.uuid})')

            # --- Identify nodes explicitly in this group ---
            nodes_explicitly_in_group = DumpNodeStore()
            group_node_uuids = current_mapping.group_to_nodes.get(group.uuid, set())
            workflows_explicitly_in_group = []

            for store_key in ['calculations', 'workflows', 'data']:
                store_nodes = getattr(changes.nodes.new_or_modified, store_key)
                filtered_nodes = [node for node in store_nodes if node.uuid in group_node_uuids]
                if filtered_nodes:
                    setattr(nodes_explicitly_in_group, store_key, filtered_nodes)
                    # Keep track of workflows found explicitly
                    if store_key == 'workflows':
                        workflows_explicitly_in_group.extend(
                            [wf for wf in filtered_nodes if isinstance(wf, orm.WorkflowNode)]
                        )

            # --- Create the final set of nodes to dump for this group ---
            nodes_to_process_for_group = nodes_explicitly_in_group

            # --- Add descendants if only_top_level_calcs is False ---
            if not self.engine.config.only_top_level_calcs and workflows_explicitly_in_group:
                logger.debug(f"Finding calculation descendants for workflows in group '{group.label}'")
                try:
                    # Use the detector's helper method via the engine
                    descendants = self.engine.detector.get_calculation_descendants(workflows_explicitly_in_group)
                    if descendants:
                        # Add unique descendants to the calculations list for this group
                        # Need to handle potential duplicates if a descendant was *also* explicitly added
                        existing_calc_uuids = {calc.uuid for calc in nodes_to_process_for_group.calculations}
                        unique_descendants = [desc for desc in descendants if desc.uuid not in existing_calc_uuids]
                        if unique_descendants:
                            logger.debug(
                                f"Adding {len(unique_descendants)} descendants to dump for group '{group.label}'."
                            )
                            nodes_to_process_for_group.calculations.extend(unique_descendants)

                except Exception as e:
                    logger.warning(f"Could not retrieve descendants for group '{group.label}': {e}")

            # --- Dump the identified nodes for this group ---
            if nodes_to_process_for_group:  # Check if not empty
                logger.info(f"Dumping {len(nodes_to_process_for_group)} nodes for group '{group.label}'")
                try:
                    self.engine.node_manager.dump_nodes(nodes_to_process_for_group, group=group)
                except Exception as e:
                    logger.error(f"Error dumping nodes for group '{group.label}': {e}", exc_info=True)
            else:
                logger.debug(f"No nodes identified for dumping in group '{group.label}'.")

        # --- Handle Ungrouped Nodes ---
        if self.engine.config.also_ungrouped:
            logger.info('Processing ungrouped nodes...')
            # Filter the main changes for ungrouped nodes
            ungrouped_nodes_store = DumpNodeStore()
            ungrouped_workflows = []

            for store_key in ['calculations', 'workflows', 'data']:
                store_nodes = getattr(changes.nodes.new_or_modified, store_key)
                # Node is ungrouped if its UUID is not in the node_to_groups mapping
                ungrouped = [node for node in store_nodes if node.uuid not in current_mapping.node_to_groups]
                if ungrouped:
                    setattr(ungrouped_nodes_store, store_key, ungrouped)
                    if store_key == 'workflows':
                        ungrouped_workflows.extend([wf for wf in ungrouped if isinstance(wf, orm.WorkflowNode)])

            # Add descendants of ungrouped workflows if needed
            if not self.engine.config.only_top_level_calcs and ungrouped_workflows:
                logger.debug('Finding calculation descendants for ungrouped workflows')
                try:
                    descendants = self.engine.detector.get_calculation_descendants(ungrouped_workflows)
                    if descendants:
                        existing_calc_uuids = {calc.uuid for calc in ungrouped_nodes_store.calculations}
                        unique_descendants = [desc for desc in descendants if desc.uuid not in existing_calc_uuids]
                        if unique_descendants:
                            logger.debug(f'Adding {len(unique_descendants)} descendants to ungrouped dump.')
                            ungrouped_nodes_store.calculations.extend(unique_descendants)
                except Exception as e:
                    logger.warning(f'Could not retrieve descendants for ungrouped workflows: {e}')

            # Call the handler for ungrouped nodes
            self._handle_ungrouped_nodes(ungrouped_nodes_store)

        # --- Final Step: Calculate and Update Stats for ALL Registered Groups ---
        logger.info('Calculating final directory stats for all registered groups...')
        for group_uuid, group_log_entry in dump_logger.groups.entries.items():
            group_path = group_log_entry.path
            logger.debug(f'Calculating stats for group directory: {group_path} (UUID: {group_uuid})')
            try:
                dir_mtime, dir_size = get_directory_stats(group_path)
                group_log_entry.dir_mtime = dir_mtime
                group_log_entry.dir_size = dir_size
                logger.debug(f'Updated stats for group {group_uuid}: mtime={dir_mtime}, size={dir_size}')
            except Exception as e:
                # Log error but continue to next group
                logger.error(f'Failed to calculate/update stats for group {group_uuid} at {group_path}: {e}')

        logger.info('Finished ProfileDumpStrategy.')

        logger.info('Finished ProfileDumpStrategy.')

    # _handle_ungrouped_nodes remains similar, but might not need its own detector/config
    # It can call node_processor directly with group=None
    def _handle_ungrouped_nodes(self, ungrouped_nodes: DumpNodeStore) -> None:
        """Handle dumping of ungrouped nodes."""
        if not ungrouped_nodes:
            logger.info('No new/modified ungrouped nodes detected.')
            return

        logger.info(f'Dumping {len(ungrouped_nodes)} ungrouped nodes...')
        try:
            # Ensure path for ungrouped exists if needed (maybe handled by NodeManager?)
            # if self.engine.config.organize_by_groups:
            #    no_group_path = self.engine.dump_paths.absolute / 'no-group' # Or defined path
            #    no_group_path.mkdir(parents=True, exist_ok=True)

            # Dump nodes using the main node processor without group context
            self.engine.node_manager.dump_nodes(
                ungrouped_nodes,
                group=None,  # Explicitly no group context
            )
        except Exception as e:
            logger.error(f'Failed processing ungrouped nodes: {e}', exc_info=True)

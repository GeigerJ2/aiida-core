from typing import cast

from aiida import orm
from aiida.common.log import AIIDA_LOGGER
from aiida.orm import QueryBuilder
from aiida.tools.dumping.strategies.base import DumpStrategy
from aiida.tools.dumping.utils.types import DumpChanges, DumpNodeStore

logger = AIIDA_LOGGER.getChild('tools.dumping.strategies.profile')


class ProfileDumpStrategy(DumpStrategy):
    """Strategy for dumping an entire profile."""

    def dump(self, changes: DumpChanges) -> None:
        """Dumps the entire profile."""
        logger.info('Executing ProfileDumpStrategy')

        # --- Process Group Changes Lifecycle ---
        if self.engine.config.update_groups:
            logger.info('Processing group lifecycle and membership changes...')
            self.engine.group_manager.handle_group_changes(changes.groups)
        else:
            logger.info('Skipping processing of group lifecycle changes.')

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

    # def dump(self, changes: DumpChanges) -> None:  # Accept changes object
    #     """Dumps the entire profile."""
    #     # profile_name = getattr(
    #     #     self.engine.dump_logger.profile, "name", "[unknown profile]"
    #     # )  # How to get profile? Engine needs it?
    #     # logger.info(f"Executing ProfileDumpStrategy for profile: {profile_name}")

    #     # Top-level path prep happens in Engine now.

    #     # --- Process Group Changes (Lifecycle: New/Deleted/Modified) ---
    #     if self.engine.config.update_groups:
    #         logger.info("Processing group lifecycle and membership changes...")
    #         self.engine.group_manager.handle_group_changes(changes.groups)
    #     else:
    #         logger.info(
    #             "Skipping processing of group lifecycle changes (update_groups is False)."
    #         )

    #     # --- Process Nodes within Groups ---
    #     # Determine which groups need node processing based on changes
    #     # groups_with_new_nodes = set()

    #     if changes.nodes.new_or_modified:  # If any new nodes were detected at all
    #         # We need to figure out which groups these nodes belong to.
    #         # The 'changes' object from the detector *doesn't* currently link
    #         # new_or_modified nodes back to specific groups easily.
    #         # The detector strategy (e.g., AnyNodeQueryStrategy) fetches nodes based on time/UUID,
    #         # not yet filtered by group *unless* GroupNodeQueryStrategy was used.

    #         # **RETHINK:** ProfileDumpStrategy should probably iterate through ALL groups
    #         # (or new/modified groups from changes.groups) and trigger node dumping
    #         # specifically for that group context using NodeManager.

    #         # **Revised Approach:** Iterate through relevant groups and dump their nodes.
    #         logger.info("Processing nodes within groups...")

    #         # Option A: Iterate through *all* current groups in the DB
    #         try:
    #             qb_groups = QueryBuilder().append(orm.Group)
    #             all_groups = cast(list[orm.Group], qb_groups.all(flat=True))
    #             logger.info(
    #                 f"Querying nodes for {len(all_groups)} groups found in the profile."
    #             )
    #         except Exception as e:
    #             logger.error(
    #                 f"Failed to query groups from database: {e}", exc_info=True
    #             )
    #             all_groups = []

    #         for group in all_groups:
    #             logger.debug(
    #                 f"Processing nodes for group: {group.label} ({group.uuid})"
    #             )
    #             # Need to detect new/modified nodes *specifically for this group* now.
    #             # This requires running a group-specific detection or filtering the main `changes`.
    #             # Re-running detection per group might be inefficient.
    #             # Filtering `changes.nodes.new_or_modified` requires knowing group membership.

    #             # **Alternative:** The initial `detect_changes` in the engine should perhaps
    #             # return nodes already partitioned by group if possible? Or provide the
    #             # current mapping to filter here.

    #             # **Let's assume we filter the main `changes.nodes.new_or_modified`**
    #             # Requires the `current_mapping` built by the engine's detector call.
    #             # (Engine needs to pass current_mapping to strategy?) Assume it's available via engine.
    #             current_mapping = (
    #                 self.engine.current_mapping
    #             )  # Assumes engine stores it

    #             nodes_in_this_group = DumpNodeStore()
    #             group_node_uuids = current_mapping.group_to_nodes.get(group.uuid, set())

    #             for store_key in ["calculations", "workflows", "data"]:
    #                 store_nodes = getattr(changes.nodes.new_or_modified, store_key)
    #                 filtered_nodes = [
    #                     node for node in store_nodes if node.uuid in group_node_uuids
    #                 ]
    #                 if filtered_nodes:
    #                     setattr(nodes_in_this_group, store_key, filtered_nodes)

    #             if nodes_in_this_group:
    #                 logger.info(
    #                     f"Dumping {len(nodes_in_this_group)} new/modified nodes found for group '{group.label}'"
    #                 )
    #                 self.engine.node_manager.dump_nodes(
    #                     nodes_in_this_group, group=group
    #                 )
    #             else:
    #                 logger.debug(
    #                     f"No new/modified nodes from main detection belong to group '{group.label}'."
    #                 )

    #     # --- Handle Ungrouped Nodes ---
    #     if self.engine.config.also_ungrouped:
    #         logger.info("Processing ungrouped nodes...")
    #         # Filter the main `changes.nodes.new_or_modified` for ungrouped nodes
    #         current_mapping = self.engine.current_mapping  # Assumes engine stores it
    #         ungrouped_nodes_store = DumpNodeStore()

    #         for store_key in ["calculations", "workflows", "data"]:
    #             store_nodes = getattr(changes.nodes.new_or_modified, store_key)
    #             # Node is ungrouped if its UUID is not in the node_to_groups mapping
    #             ungrouped_nodes = [
    #                 node
    #                 for node in store_nodes
    #                 if node.uuid not in current_mapping.node_to_groups
    #             ]
    #             if ungrouped_nodes:
    #                 setattr(ungrouped_nodes_store, store_key, ungrouped_nodes)

    #         self._handle_ungrouped_nodes(ungrouped_nodes_store)

    #     # logger.info(f"Finished ProfileDumpStrategy for profile: {profile_name}")


# class ProfileDumpStrategy(DumpStrategy):
#     """Strategy for dumping an entire profile by iterating through groups."""

#     # Bring back _handle_ungrouped_nodes if using it
#     def _handle_ungrouped_nodes(self) -> None:
#         """Handle dumping of ungrouped nodes."""
#         logger.info("Processing ungrouped nodes...")
#         try:
#             # Create a specific config/detector for ungrouped scope
#             ungrouped_config = self.engine.config.__class__(
#                 **{
#                     **self.engine.config.__dict__,
#                     "group_scope": NodeDumpGroupScope.NO_GROUP,
#                 }
#             )
#             ungrouped_detector = DumpChangeDetector(  # Use the main detector class
#                 self.engine.dump_logger, ungrouped_config
#             )
#             ungrouped_changes: DumpChanges = ungrouped_detector.detect_changes(
#                 group=None
#             )

#             # Ensure path for ungrouped exists if needed
#             if self.engine.config.organize_by_groups:
#                 no_group_path = self.engine.dump_paths.absolute / "no-group"
#                 no_group_path.mkdir(parents=True, exist_ok=True)
#                 # Optionally add safeguard? prepare_dump_path might be overkill here.

#             if ungrouped_changes.nodes.new_or_modified:
#                 logger.info(
#                     f"Dumping {len(ungrouped_changes.nodes.new_or_modified)} ungrouped nodes."
#                 )
#                 self.engine.node_manager.dump_nodes(
#                     ungrouped_changes.nodes.new_or_modified,
#                     group=None,  # No group context
#                 )
#             else:
#                 logger.info("No new/modified ungrouped nodes detected.")
#         except Exception as e:
#             logger.error(f"Failed processing ungrouped nodes: {e}", exc_info=True)

#     def dump(self)-> None:
#         """Dumps the entire profile, iterating through groups and handling ungrouped."""
#         # self.entity is None here

#         # profile_name = getattr(
#         #     self.engine.dump_logger.profile, "name", "[unknown profile]"
#         # )
#         # logger.info(f"Executing ProfileDumpStrategy for profile: {profile_name}")

#         # Prepare top-level profile dump path
#         prepare_dump_path(
#             path_to_validate=self.engine.dump_paths.absolute,
#             dump_mode=self.engine.config.dump_mode,
#             safeguard_file=self.engine.dump_paths.safeguard_file,
#             top_level_caller=True,
#         )

#         # --- Process All Groups ---
#         logger.info("Processing groups within the profile...")
#         # Update group mapping first
#         current_mapping = self.engine.dump_logger.build_current_group_node_mapping()
#         self.engine.dump_logger.group_node_mapping = current_mapping

#         # Query all groups from the database
#         try:
#             qb = QueryBuilder()
#             qb.append(orm.Group)
#             all_groups = qb.all(flat=True)
#             logger.info(f"Found {len(all_groups)} groups in the profile.")
#         except Exception as e:
#             logger.error(f"Failed to query groups from database: {e}", exc_info=True)
#             all_groups = []

#         for group in all_groups:
#             logger.debug(f"Processing group: {group.label} ({group.uuid})")
#             try:
#                 # Detect changes specifically for this group
#                 # The detector instance might be created here or reused if stateless
#                 group_detector = DumpChangeDetector(
#                     self.engine.dump_logger, self.engine.config
#                 )
#                 group_changes: DumpChanges = group_detector.detect_changes(group=group)

#                 # Ensure group directory exists and is logged
#                 self.engine.group_manager.ensure_group_registered(group)

#                 # Process modifications specific to this group run
#                 # GroupManager handles lifecycle changes based on its internal diff if needed
#                 if (
#                     group_changes.groups.modified
#                     or group_changes.groups.node_membership
#                 ):
#                     self.engine.group_manager.handle_group_changes(group_changes.groups)

#                 # Dump nodes detected for this group
#                 if group_changes.nodes.new_or_modified:
#                     logger.info(
#                         f"Dumping {len(group_changes.nodes.new_or_modified)} nodes for group {group.label}"
#                     )
#                     self.engine.node_manager.dump_nodes(
#                         group_changes.nodes.new_or_modified,
#                         group=group,  # *** Pass correct group context ***
#                     )

#                 else:
#                     logger.debug(
#                         f"No new/modified nodes detected for group {group.label}"
#                     )

#             except Exception as e:
#                 logger.error(
#                     f"Failed processing group {group.label} ({group.uuid}): {e}",
#                     exc_info=True,
#                 )

#         # --- Handle Ungrouped Nodes ---
#         if self.engine.config.also_ungrouped:
#             self._handle_ungrouped_nodes()  # Call the helper method

#         # Log saving happens back in DumpEngine after strategy completes
#         # logger.info(f"Finished ProfileDumpStrategy for profile: {profile_name}")

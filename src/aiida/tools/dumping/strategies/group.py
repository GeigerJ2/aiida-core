from aiida.common.log import AIIDA_LOGGER
from aiida.tools.dumping.strategies.base import DumpStrategy
from aiida.tools.dumping.utils.types import DumpChanges

logger = AIIDA_LOGGER.getChild("tools.dumping.strategies.group")


class GroupDumpStrategy(DumpStrategy):
    """Strategy for dumping a group's contents"""

    def dump(self, changes: DumpChanges):
        """Dumps the specific group using pre-detected changes."""
        group = self.entity
        if group is None:
            logger.error("GroupDumpStrategy executed without a valid group entity.")
            return

        logger.info(
            f"Executing GroupDumpStrategy for group '{group.label}' ({group.uuid})"
        )

        # 1. Prepare Path (Ensure group directory exists and is logged)
        # This also ensures the group is in the logger if it's new
        try:
            self.engine.group_manager.ensure_group_registered(group)
            # Optional: Prepare path further if needed (safeguards etc.)
            # prepare_dump_path(...)
        except Exception as e:
            logger.error(
                f"Failed to get or register path for group {group.label}: {e}",
                exc_info=True,
            )
            return

        # 2. Handle Group Changes (Apply membership updates, label changes etc.)
        # group_changes_for_this_group = changes.groups # Changes should already be filtered for this group
        # Delegate processing to GroupManager using the relevant part of changes
        if self.engine.config.update_groups and changes.groups:
            logger.info(
                f"Dispatching group lifecycle/membership changes for {group.label} to GroupManager..."
            )
            self.engine.group_manager.handle_group_changes(changes.groups)

        # 3. Handle New/Modified Nodes for this Group
        nodes_to_dump = changes.nodes.new_or_modified  # Nodes detected for this scope
        if nodes_to_dump:  # Check if the DumpNodeStore is not empty
            logger.info(
                f"Dispatching {len(nodes_to_dump)} new/modified nodes to NodeProcessor for group '{group.label}'..."
            )
            try:
                # Pass the node store and the group context to the NodeManager
                self.engine.node_manager.dump_nodes(
                    nodes_to_dump,
                    group=group,  # Provide group context
                )
            except Exception as e:
                logger.error(
                    f"Failed during node dumping for group '{group.label}': {e}",
                    exc_info=True,
                )
        else:
            logger.info(
                f"No new/modified nodes detected to dump for group '{group.label}'."
            )

        logger.info(f"Finished GroupDumpStrategy for group '{group.label}'.")


# def dump(self):
#     # Detect changes for this group
#     group = self.entity
#     changes = self.engine.detector.detect_changes(group=group)

#     # Update group structure if needed
#     if self.engine.config.update_groups:
#         self.engine._update_group_structure(changes['group_changes'])

#     # Dump new nodes
#     self.engine._dump_nodes(changes['new_nodes'], group)

# def dump(self):
#     group = self.entity  # The group passed during instantiation

#     # Prepare path specific to this group if needed
#     # Example: Use get_group_path from GroupManager
#     group_dump_path = self.engine.group_manager.get_group_path(group)
#     # Ensure top-level path exists (could be done once in engine or here)
#     prepare_dump_path(
#         path_to_validate=group_dump_path,  # Validate the specific group path
#         dump_mode=self.engine.config.dump_mode,
#         safeguard_file=self.engine.dump_paths.safeguard_file,
#         top_level_caller=False,  # Not the absolute top level
#     )

#     # Detect changes specifically for this group
#     changes: DumpChanges = self.engine.detector.detect_changes(group=group)

#     # Process group changes (e.g., modified memberships within this group)
#     # Note: new/deleted groups shouldn't apply when dumping a specific group
#     if changes.groups.modified or changes.groups.node_membership:
#         self.engine.group_manager.handle_group_changes(changes.groups)

#     # Dump new/modified nodes found within this group
#     if changes.nodes.new_or_modified:
#         self.engine.node_manager.dump_nodes(
#             changes.nodes.new_or_modified, group=group  # Provide group context
#         )

# def dump(self):
#     """Dumps the specific group associated with this strategy."""
#     group = self.entity # The group passed during instantiation
#     if group is None:
#          logger.error("GroupDumpStrategy executed without a valid group entity.")
#          return

#     logger.report(f"Executing GroupDumpStrategy for group: {group.label} ({group.uuid})")

#     # Prepare path specific to this group using the GroupManager helper
#     # This also ensures the group is registered in the logger
#     try:
#         group_dump_path = self.engine.group_manager.ensure_group_registered(group)
#     except Exception as e:
#         logger.error(f"Failed to get or register path for group {group.label}: {e}")
#         return

#     # Ensure the specific group directory path is validated/prepared
#     # Note: Top-level path prep happens in DumpEngine or Profile strategy
#     prepare_dump_path(
#         path_to_validate=group_dump_path, # Validate the specific group path
#         dump_mode=self.engine.config.dump_mode,
#         safeguard_file=self.engine.dump_paths.safeguard_file,
#         top_level_caller=False # Not the absolute top level dump dir
#     )

#     # Detect changes specifically for this group
#     logger.debug(f"Detecting changes for group: {group.label}")
#     try:
#         changes: DumpChanges = self.engine.detector.detect_changes(group=group)
#     except Exception as e:
#         logger.error(f"Failed to detect changes for group {group.label}: {e}")
#         return

#     # Process group changes (e.g., modified memberships within this group)
#     # Should mostly be relevant for node membership changes here.
#     if changes.groups.modified or changes.groups.node_membership:
#          logger.debug(f"Handling group modifications/membership changes for {group.label}")
#          self.engine.group_manager.handle_group_changes(changes.groups) # Pass GroupChangeInfo

#     # Dump new/modified nodes found within this group
#     if changes.nodes.new_or_modified: # Check the DumpNodeStore part
#         logger.report(f"Dumping {len(changes.nodes.new_or_modified)} new/modified nodes for group {group.label}")
#         try:
#             self.engine.node_manager.dump_nodes(
#                 changes.nodes.new_or_modified,
#                 group=group # Provide group context
#             )
#         except Exception as e:
#             logger.error(f"Failed to dump nodes for group {group.label}: {e}")
#     else:
#         logger.report(f"No new/modified nodes to dump for group {group.label}")

#     # Note: Deletion checks/handling are done earlier in DumpEngine
#     # Note: Log saving happens back in DumpEngine after strategy completes
#     logger.report(f"Finished GroupDumpStrategy for group: {group.label}")

#     def dump(self, changes: DumpChanges): # Receive changes from engine
#         """Dumps the specific group using pre-detected changes."""
#         group = self.entity
#         if group is None:
#              logger.error("GroupDumpStrategy executed without a valid group entity.")
#              return

#         logger.info(f"GroupDumpStrategy: Processing changes for group {group.label} ({group.uuid})")

#         # Path preparation might happen here or in engine before calling strategy

#         # 1. Handle Group Changes (will be filtered for this group by detector)
#         # Delegate processing to GroupManager
#         if changes.groups: # Should only contain info relevant to this group
#              logger.info("Dispatching group changes to GroupManager...")
#              self.engine.group_manager.handle_group_changes(changes.groups)

#         # 2. Handle New/Modified Nodes for this Group
#         # Delegate dumping to NodeProcessor, providing the group context
#         if changes.nodes.new_or_modified:
#              logger.info(f"Dispatching {len(changes.nodes.new_or_modified)} nodes to NodeProcessor for group {group.label}...")
#              self.engine.node_manager.dump_nodes(
#                  changes.nodes.new_or_modified,
#                  group=group # Pass the specific group context
#              )
#         else:
#              logger.info(f"No new/modified nodes detected for group {group.label}.")

#         logger.info(f"GroupDumpStrategy finished for group {group.label}.")

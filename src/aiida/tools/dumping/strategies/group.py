from aiida.common.log import AIIDA_LOGGER
from aiida.tools.dumping.logger import DumpLog, DumpLogger
from aiida.tools.dumping.strategies.base import DumpStrategy
from aiida.tools.dumping.utils.types import DumpChanges

logger = AIIDA_LOGGER.getChild("tools.dumping.strategies.group")


class GroupDumpStrategy(DumpStrategy):
    """Strategy for dumping a group's contents"""

    def dump(self, changes: DumpChanges, dump_logger: DumpLogger):
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
            group_path = self.engine.group_manager.ensure_group_registered(group)
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
                # TODO:

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

        # dump_logger.groups.add_entry(
        #     uuid=group.uuid,
        #     entry=DumpLog(path=group_path.resolve())
        # )

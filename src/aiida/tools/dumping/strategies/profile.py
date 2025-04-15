from aiida.common.log import AIIDA_LOGGER
from aiida.tools.dumping.strategies.base import DumpStrategy
from aiida import orm
from aiida.orm import QueryBuilder
from aiida.tools.dumping.strategies.base import DumpStrategy
from aiida.tools.dumping.utils.types import DumpChanges
from aiida.tools.dumping.detect.detector import DumpChangeDetector
from aiida.tools.dumping.config import NodeDumpGroupScope
from aiida.tools.dumping.utils.paths import prepare_dump_path


logger = AIIDA_LOGGER.getChild("tools.dumping.strategies.profile")


class ProfileDumpStrategy(DumpStrategy):
    """Strategy for dumping an entire profile by iterating through groups."""

    # Bring back _handle_ungrouped_nodes if using it
    def _handle_ungrouped_nodes(self) -> None:
        """Handle dumping of ungrouped nodes."""
        logger.info("Processing ungrouped nodes...")
        try:
            # Create a specific config/detector for ungrouped scope
            ungrouped_config = self.engine.config.__class__(
                **{
                    **self.engine.config.__dict__,
                    "group_scope": NodeDumpGroupScope.NO_GROUP,
                }
            )
            ungrouped_detector = DumpChangeDetector(  # Use the main detector class
                self.engine.dump_logger, ungrouped_config
            )
            ungrouped_changes: DumpChanges = ungrouped_detector.detect_changes(
                group=None
            )

            # Ensure path for ungrouped exists if needed
            if self.engine.config.organize_by_groups:
                no_group_path = self.engine.dump_paths.absolute / "no-group"
                no_group_path.mkdir(parents=True, exist_ok=True)
                # Optionally add safeguard? prepare_dump_path might be overkill here.

            if ungrouped_changes.nodes.new_or_modified:
                logger.info(
                    f"Dumping {len(ungrouped_changes.nodes.new_or_modified)} ungrouped nodes."
                )
                self.engine.node_processor.dump_nodes(
                    ungrouped_changes.nodes.new_or_modified,
                    group=None,  # No group context
                )
            else:
                logger.info("No new/modified ungrouped nodes detected.")
        except Exception as e:
            logger.error(f"Failed processing ungrouped nodes: {e}", exc_info=True)

    def dump(self)-> None:
        """Dumps the entire profile, iterating through groups and handling ungrouped."""
        # self.entity is None here

        # profile_name = getattr(
        #     self.engine.dump_logger.profile, "name", "[unknown profile]"
        # )
        # logger.info(f"Executing ProfileDumpStrategy for profile: {profile_name}")

        # Prepare top-level profile dump path
        prepare_dump_path(
            path_to_validate=self.engine.dump_paths.absolute,
            dump_mode=self.engine.config.dump_mode,
            safeguard_file=self.engine.dump_paths.safeguard_file,
            top_level_caller=True,
        )

        # --- Process All Groups ---
        logger.info("Processing groups within the profile...")
        # Update group mapping first
        current_mapping = self.engine.dump_logger.build_current_group_node_mapping()
        self.engine.dump_logger.group_node_mapping = current_mapping

        # Query all groups from the database
        try:
            qb = QueryBuilder()
            qb.append(orm.Group)
            all_groups = qb.all(flat=True)
            logger.info(f"Found {len(all_groups)} groups in the profile.")
        except Exception as e:
            logger.error(f"Failed to query groups from database: {e}", exc_info=True)
            all_groups = []

        for group in all_groups:
            logger.debug(f"Processing group: {group.label} ({group.uuid})")
            try:
                # Detect changes specifically for this group
                # The detector instance might be created here or reused if stateless
                group_detector = DumpChangeDetector(
                    self.engine.dump_logger, self.engine.config
                )
                group_changes: DumpChanges = group_detector.detect_changes(group=group)

                # Ensure group directory exists and is logged
                self.engine.group_manager.ensure_group_registered(group)

                # Process modifications specific to this group run
                # GroupManager handles lifecycle changes based on its internal diff if needed
                if (
                    group_changes.groups.modified
                    or group_changes.groups.node_membership
                ):
                    self.engine.group_manager.handle_group_changes(group_changes.groups)

                # Dump nodes detected for this group
                if group_changes.nodes.new_or_modified:
                    logger.info(
                        f"Dumping {len(group_changes.nodes.new_or_modified)} nodes for group {group.label}"
                    )
                    self.engine.node_processor.dump_nodes(
                        group_changes.nodes.new_or_modified,
                        group=group,  # *** Pass correct group context ***
                    )

                else:
                    logger.debug(
                        f"No new/modified nodes detected for group {group.label}"
                    )

            except Exception as e:
                logger.error(
                    f"Failed processing group {group.label} ({group.uuid}): {e}",
                    exc_info=True,
                )

        # --- Handle Ungrouped Nodes ---
        if self.engine.config.also_ungrouped:
            self._handle_ungrouped_nodes()  # Call the helper method

        # Log saving happens back in DumpEngine after strategy completes
        # logger.info(f"Finished ProfileDumpStrategy for profile: {profile_name}")


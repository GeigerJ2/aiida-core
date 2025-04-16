from __future__ import annotations

from typing import TYPE_CHECKING

from aiida import orm
from aiida.common.log import AIIDA_LOGGER
from aiida.tools.dumping.config import DumpMode
from aiida.tools.dumping.detect.detector import DumpChangeDetector
from aiida.tools.dumping.logger import DumpLogger
from aiida.tools.dumping.managers.deletion import DeletionManager
from aiida.tools.dumping.managers.group import GroupManager
from aiida.tools.dumping.managers.node import NodeManager
from aiida.tools.dumping.strategies.base import DumpStrategy
from aiida.tools.dumping.strategies.group import GroupDumpStrategy
from aiida.tools.dumping.strategies.process import ProcessDumpStrategy
from aiida.tools.dumping.strategies.profile import ProfileDumpStrategy
from aiida.tools.dumping.utils.paths import prepare_dump_path
from aiida.tools.dumping.utils.time import DumpTimes
from aiida.tools.dumping.utils.types import DumpChanges, GroupChanges

if TYPE_CHECKING:
    from aiida.manage import Profile
    from aiida.tools.dumping.config import DumpConfig
    from aiida.tools.dumping.mapping import GroupNodeMapping
    from aiida.tools.dumping.utils.paths import DumpPaths


logger = AIIDA_LOGGER.getChild('tools.dumping.engine')


class DumpEngine:
    """Core engine that orchestrates the dump process."""

    def __init__(self, config: DumpConfig, dump_paths: DumpPaths):
        self.config = config
        self.dump_paths = dump_paths

        # --- Initialize Times and Logger ---
        self.dump_times, self.dump_logger, self.stored_mapping = self._initialize_logger_and_mapping()

        # --- Initialize Managers (pass dependencies) ---
        # GroupManager might need DumpTimes if doing time-based logic internally
        self.group_manager = GroupManager(config, dump_paths, self.dump_logger, self)
        # NodeManager needs GroupManager for path calculation
        self.node_manager = NodeManager(config, dump_paths, self.dump_logger, self.dump_times, self.group_manager)
        # Detector needs logger and times
        self.detector = DumpChangeDetector(self.dump_logger, self.config, self.dump_times)
        # DeletionManager needs logger
        self.deletion_manager = DeletionManager(config, dump_paths, self.dump_logger)

    def _initialize_logger_and_mapping(
        self,
    ) -> tuple[DumpTimes, DumpLogger, GroupNodeMapping | None]:
        """Initialize dump times, load logger data, and load stored mapping."""
        logger.debug('Initializing dump times and logger...')
        # Clear log file if overwriting
        if self.config.dump_mode == DumpMode.OVERWRITE and self.dump_paths.log_path.exists():
            try:
                logger.info(f'Overwrite mode: Deleting existing log file {self.dump_paths.log_path}')
                self.dump_paths.log_path.unlink()
            except OSError as e:
                logger.error(f'Failed to delete existing log file: {e}')
                # Decide whether to proceed or raise an error

        # Load log data, stored mapping, and last dump time string from file
        stores_coll, stored_mapping, last_dump_time_str = DumpLogger.load(self.dump_paths)

        # Initialize DumpTimes based on loaded time string
        dump_times = DumpTimes.from_last_log_time(last_dump_time_str)
        logger.debug(f'Dump times initialized: Current={dump_times.current}, Last={dump_times.last}')

        # Initialize DumpLogger instance with loaded data
        dump_logger = DumpLogger(self.dump_paths, stores_coll, last_dump_time_str)
        msg = (
            f'Dump logger initialized. Found {len(dump_logger.calculations)} calc logs, '
            f'{len(dump_logger.workflows)} wf logs, {len(dump_logger.groups)} group logs.'
        )
        logger.debug(msg)

        if stored_mapping:
            msg = f'Loaded stored group mapping with {len(stored_mapping.group_to_nodes)} groups.'
            logger.debug(msg)
        else:
            msg = 'No stored group mapping found in log file.'
            logger.debug(msg)

        return dump_times, dump_logger, stored_mapping

    def dump(self, entity: orm.ProcessNode | orm.Group | Profile | None = None) -> None:
        """Selects and executes the appropriate dump strategy."""
        msg = f'Starting dump process (Mode: {self.config.dump_mode.name})'
        logger.info(msg)

        # NOTE: Should this maybe be after `prepare_dump_path`
        # --- Handle Deletion First (if requested) ---
        if self.config.delete_missing:
            logger.info('Deletion requested. Handling deleted entities...')
            # --- Change Detection (needed *only* for deletion info) ---
            logger.info('Detecting changes to identify deletions...')
            # Detect node changes (yields NodeChanges and mapping)
            node_changes_for_deletion, current_mapping_for_deletion = self.detector.detect_changes(group=None)
            # Detect group changes (yields GroupChanges)
            group_changes_for_deletion = self.detector.detect_group_changes(
                stored_mapping=self.stored_mapping,
                current_mapping=current_mapping_for_deletion,
                specific_group_uuid=None,
            )
            # Assemble changes object specifically for deletion manager
            deletion_changes = DumpChanges(
                nodes=node_changes_for_deletion,
                groups=group_changes_for_deletion,
            )

            _ = self.deletion_manager.handle_deleted_entities(deletion_changes)  # Pass correctly assembled changes
            # NOTE: This
            # if deleted:
            #     logger.info('Saving log after processing deletions.')
            #     # Save the logger state using the current mapping identified during detection
            #     self.dump_logger.save(self.dump_times.current, current_mapping_for_deletion)
            # logger.info('Deletion processing finished.')
            # return  # Deletion is an exclusive action

        # --- Prepare Top-Level Path ---
        try:
            prepare_dump_path(
                path_to_validate=self.dump_paths.absolute,
                dump_mode=self.config.dump_mode,
                safeguard_file=self.dump_paths.safeguard_file,
                top_level_caller=True,
            )
        except (FileNotFoundError, FileExistsError, ValueError, OSError) as e:
            logger.critical(f'Failed to prepare dump directory {self.dump_paths.absolute}: {e}')
            return

        # --- Change Detection (for Dumping) ---
        logger.info('Detecting node changes for dump...')
        # node_changes now holds a NodeChanges object, current_mapping holds the mapping
        node_changes, current_mapping = self.detector.detect_changes(  # CORRECTED unpack
            group=entity if isinstance(entity, orm.Group) else None
        )
        # Store current mapping on engine instance if ProfileStrategy needs it
        self.current_mapping = current_mapping

        logger.info('Detecting group changes for dump...')
        group_changes: GroupChanges
        if self.config.update_groups:  # Only calculate diff if we plan to use it
            group_changes = self.detector.detect_group_changes(
                stored_mapping=self.stored_mapping,  # Use mapping loaded at init
                current_mapping=current_mapping,  # Use mapping from node detection
                specific_group_uuid=(entity.uuid if isinstance(entity, orm.Group) else None),
            )
        else:
            logger.info('Skipping group change detection (update_groups is False).')
            group_changes = GroupChanges()  # Use empty changes

        # Combine detected changes correctly
        all_changes = DumpChanges(
            nodes=node_changes,  # Assign the NodeChanges object
            groups=group_changes,  # Assign the GroupChanges object
        )

        # --- Select and Execute Strategy ---
        strategy = self._create_strategy(entity)
        logger.info(f'Executing strategy: {type(strategy).__name__}')

        try:
            # Pass the correctly assembled changes object
            strategy.dump(changes=all_changes, dump_logger=self.dump_logger)  # Strategies should expect DumpChanges
        except Exception as e:
            logger.critical(
                f'Error during execution of strategy {type(strategy).__name__}: {e}',
                exc_info=True,
            )

        # --- Finalize ---
        logger.info('Saving final dump log and mapping...')
        try:
            # Pass the current mapping detected earlier
            self.dump_logger.save(self.dump_times.current, current_mapping)
        except Exception as e:
            logger.error(f'Failed to save final dump log: {e}', exc_info=True)

        logger.info(f"Dump process finished successfully for entity: {entity or 'Profile'}.")

    def _create_strategy(self, entity) -> DumpStrategy:
        """Create the appropriate dump strategy based on entity type."""
        # Pass the engine instance (self) to strategies
        if isinstance(entity, orm.Group):
            return GroupDumpStrategy(entity, engine=self)
        elif isinstance(entity, orm.ProcessNode):
            return ProcessDumpStrategy(entity, engine=self)
        elif entity is None:  # Assuming None entity means dump profile
            return ProfileDumpStrategy(entity, engine=self)  # Pass None entity
        else:
            # Handle unexpected entity types
            raise TypeError(f'Unsupported entity type for dumping: {type(entity)}')

    def request_node_dump(self, node: orm.Node, group: orm.Group | None):
        # NOTE: Avoids circular dependency between NodeManager and GroupManager
        # NOTE: Uses mediator pattern
        """Handles request from GroupManager to dump a node."""
        logger.debug(f"Engine received request to dump node {node.pk} for group {group.label if group else 'None'}")
        try:
            # Delegate to NodeManager
            self.node_manager.dump_process(node, group)
        except Exception as e:
            logger.error(f'Engine failed to delegate dump request for node {node.pk}: {e}', exc_info=True)

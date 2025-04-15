from __future__ import annotations
import json

from aiida import orm
from aiida.tools.dumping.config import DumpConfig, DumpMode
from aiida.tools.dumping.detect.detector import DumpChangeDetector
from aiida.tools.dumping.utils.types import DumpChanges
from aiida.tools.dumping.storage import DumpLogger
from aiida.tools.dumping.strategies.group import GroupDumpStrategy
from aiida.tools.dumping.strategies.process import ProcessDumpStrategy
from aiida.tools.dumping.strategies.profile import ProfileDumpStrategy
from aiida.tools.dumping.managers.node import NodeManager
from aiida.tools.dumping.managers.group import GroupManager
from aiida.tools.dumping.utils.paths import DumpPaths
from aiida.common.log import AIIDA_LOGGER
from aiida.tools.dumping.utils.time import DumpTimes
from aiida.tools.dumping.managers.deletion import DeletionManager
from aiida.tools.dumping.utils.paths import prepare_dump_path


logger = AIIDA_LOGGER.getChild("tools.dumping.engine")


class DumpEngine:
    """Core engine that orchestrates the dump process."""

    def __init__(self, config: DumpConfig, dump_paths: DumpPaths):
        self.config = config
        self.dump_paths = dump_paths
        self.dump_logger = self._initialize_logger()
        self.detector = DumpChangeDetector(self.dump_logger, self.config)
        self.node_processor = NodeManager(config, dump_paths, self.dump_logger)
        self.group_manager = GroupManager(
            config, dump_paths, self.dump_logger, node_processor=self.node_processor
        )
        self.deletion_manager = DeletionManager(
            config, dump_paths, self.dump_logger, self.detector
        )

    def _initialize_logger(self) -> DumpLogger:
        """Initialize the dump logger."""
        if (
            self.config.dump_mode == DumpMode.OVERWRITE
            and self.dump_paths.log_path.exists()
        ):
            self.dump_paths.log_path.unlink()

        try:
            return DumpLogger.from_file(dump_paths=self.dump_paths)
        except (json.JSONDecodeError, OSError):
            return DumpLogger(dump_paths=self.dump_paths, dump_times=DumpTimes())

    def dump(self, entity=None) -> None:
        """Delegates processing to the appropriate strategy."""

        # --- Handle Deletion First ---
        if self.config.delete_missing:
            logger.info("Deletion requested. Handling deleted entities...")
            # Call the manager method responsible for deletion detection & processing
            # *** Changed method name here ***
            self.deletion_manager.handle_deleted_entities()
            logger.info("Deletion processing finished.")
            return  # Deletion is an exclusive action

        # --- Prepare Path ---
        # Path prep might be better handled within each strategy's dump method
        # logger.info("Preparing dump path...")
        # prepare_dump_path(...) # Consider removing from here

        # --- Get Strategy and Execute ---
        strategy = self._create_strategy(entity)
        logger.info(f"Executing strategy: {type(strategy).__name__}")
        # *** Call strategy dump without changes argument ***
        strategy.dump()

        # --- Finalize (Save Log) ---
        logger.info("Saving dump log...")
        self.dump_logger.save_log()
        logger.info("Dump process finished.")

    def _create_strategy(self, entity):
        """Create the appropriate dump strategy based on entity type"""
        if isinstance(entity, orm.Group):
            return GroupDumpStrategy(self, entity)
        elif isinstance(entity, orm.ProcessNode):
            return ProcessDumpStrategy(self, entity)
        else:
            return ProfileDumpStrategy(self, entity)

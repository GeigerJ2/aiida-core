import json

from aiida import orm
from aiida.tools.dumping.config import DumpConfig, DumpMode, ProcessDumperConfig
from aiida.tools.dumping.detect.detector import DumpChangeDetector
from aiida.tools.dumping.storage import DumpLogger
from aiida.tools.dumping.strategies.group import GroupDumpStrategy
from aiida.tools.dumping.strategies.process import ProcessDumpStrategy
from aiida.tools.dumping.strategies.profile import ProfileDumpStrategy
from aiida.tools.dumping.managers.nodes import NodeManager
from aiida.tools.dumping.managers.groups import GroupDumpManager
from aiida.tools.dumping.utils.paths import (
    DumpPaths,
    prepare_dump_path,
)
from aiida.common.log import AIIDA_LOGGER
from aiida.tools.dumping.utils.time import DumpTimes
from aiida.tools.dumping.managers.deletion import DeletionManager


logger = AIIDA_LOGGER.getChild("tools.dumping.engine")

class DumpEngine:
    """Core engine that orchestrates the dump process."""

    def __init__(self, config: DumpConfig, dump_paths: DumpPaths):
        self.config = config
        self.dump_paths = dump_paths
        self.dump_logger = self._initialize_logger()
        self.detector = DumpChangeDetector(self.dump_logger, self.config)
        self.node_processor = NodeManager(config, dump_paths, self.dump_logger)
        self.group_manager = GroupDumpManager(config, dump_paths, self.dump_logger, node_processor=self.node_processor)
        self.deletion_manager = DeletionManager(config, dump_paths, self.dump_logger)

    def _initialize_logger(self) -> DumpLogger:
        """Initialize the dump logger."""
        if self.config.dump_mode == DumpMode.OVERWRITE and self.dump_paths.log_path.exists():
            self.dump_paths.log_path.unlink()

        try:
            return DumpLogger.from_file(dump_paths=self.dump_paths)
        except (json.JSONDecodeError, OSError):
            return DumpLogger(dump_paths=self.dump_paths, dump_times=DumpTimes())

    def dump(self, entity=None) -> None:
        """Main dump entry point that handles all types of entities."""
        # Handle special case for deletion
        if self.config.delete_missing:
            self.deletion_manager.handle_deleted_nodes()

        # Prepare the dump path
        prepare_dump_path(
            path_to_validate=self.dump_paths.absolute,
            dump_mode=self.config.dump_mode,
            safeguard_file=DumpPaths.safeguard_file,
        )
        
        # Create and execute the appropriate strategy
        strategy = self._create_strategy(entity)
        strategy.dump()
        
        # Save the log
        self.dump_logger.save_log()
        
    def _create_strategy(self, entity):
        """Create the appropriate dump strategy based on entity type"""
        if isinstance(entity, orm.Group):
            return GroupDumpStrategy(self, entity)
        elif isinstance(entity, orm.ProcessNode):
            return ProcessDumpStrategy(self, entity)
        else:
            return ProfileDumpStrategy(self, entity)

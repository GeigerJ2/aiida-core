import json
import os
from pathlib import Path

from aiida import orm
from aiida.tools.dumping.config import DumpConfig, DumpMode, NodeDumpGroupScope, ProcessDumperConfig
from aiida.tools.dumping.detect.detector import DumpChangeDetector
from aiida.tools.dumping.storage import DumpLog, DumpLogger, DumpNodeStore
from aiida.tools.dumping.utils.groups import get_group_subpath
from aiida.tools.dumping.utils.paths import (
    DumpPaths,
    generate_process_default_dump_path,
    prepare_dump_path,
    safe_delete_dir,
)
from aiida.common.log import AIIDA_LOGGER
from aiida.tools.dumping.utils.time import DumpTimes
from aiida.tools.dumping.strategies.base import DumpStrategy

logger = AIIDA_LOGGER.getChild("tools.dumping.engine")

class ProcessDumpStrategy(DumpStrategy):
    """Strategy for dumping a process node"""
    
    def dump(self):
        from aiida.tools.dumping.entities.process import ProcessDumper
        
        process = self.entity
        process_dumper = ProcessDumper(
            process_node=process,
            dump_mode=self.engine.config.dump_mode,
            dump_paths=self.engine.dump_paths,
            dump_logger=self.engine.dump_logger,
            config=self.engine.config.get_process_config()
        )
        process_dumper.dump()

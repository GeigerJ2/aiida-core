from aiida import orm
from aiida.tools.dumping.entities.process import ProcessDumper
from aiida.tools.dumping.storage import DumpStoreKeys
from aiida.tools.dumping.utils.paths import generate_process_default_dump_path
from aiida.tools.dumping.storage import DumpLog
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aiida.tools.dumping.config import DumpConfig


class NodeProcessor:
    """Handles the processing and dumping of individual nodes"""
    
    def __init__(self, config, dump_paths, dump_logger):
        self.config: DumpConfig = config
        self.dump_paths = dump_paths
        self.dump_logger = dump_logger
    
    def dump_nodes(self, node_store, group=None):
        """Dump a collection of nodes from a node store"""
        from aiida.common.progress_reporter import get_progress_reporter, set_progress_bar_tqdm
        
        set_progress_bar_tqdm()
        
        for process_type in ('calculations', 'workflows'):
            processes = getattr(node_store, process_type)
            if processes:
                with get_progress_reporter()(desc=f'Dumping {process_type}', total=len(processes)) as progress:
                    for process in processes:
                        self.dump_process(process, group)
                        progress.update()

    def dump_process(self, process, group=None):
        """Dump a single process."""

        if group:
            # Use the group manager to get the proper path
            if hasattr(self, 'group_manager'):
                group_path = self.group_manager.get_group_path(group)
            else:
                # Fallback if group_manager not available
                if self.config.organize_by_groups:
                    from aiida.tools.dumping.utils.groups import get_group_subpath
                    group_path = self.dump_paths.absolute / 'groups' / get_group_subpath(group)
                else:
                    group_path = self.dump_paths.absolute
                
                # Ensure directories exist
                group_path.mkdir(parents=True, exist_ok=True)
            
            # Set the appropriate subdirectory based on process type
            if isinstance(process, orm.CalculationNode):
                process_path = group_path / 'calculations'
            else:
                process_path = group_path / 'workflows'
                
            # Ensure the process type directory exists
            process_path.mkdir(parents=True, exist_ok=True)
        else:
            process_path = self.dump_paths.absolute

        process_name = generate_process_default_dump_path(process)
        process_path = process_path / process_name

        # Create process dumper and dump the process
        from aiida.tools.dumping.config import ProcessDumperConfig
        
        process_config = ProcessDumperConfig(
            include_inputs=self.config.include_inputs,
            include_outputs=self.config.include_outputs,
            include_attributes=self.config.include_attributes,
            include_extras=self.config.include_extras,
            flat=self.config.flat,
            dump_unsealed=self.config.dump_unsealed,
            symlink_calcs=self.config.symlink_calcs,
        )
        
        from aiida.tools.dumping.utils.paths import DumpPaths
        process_paths = DumpPaths.from_path(process_path)
        
        process_dumper = ProcessDumper(
            process_node=process,
            dump_mode=self.config.dump_mode,
            dump_paths=process_paths,
            dump_logger=self.dump_logger,
            config=process_config,
        )
        
        process_dumper.dump(top_level_caller=False)
        
        # Update the logger
        current_store_key = DumpStoreKeys.from_instance(node_inst=process)
        current_store = self.dump_logger.get_store_by_name(name=current_store_key)
        current_store.add_entry(uuid=process.uuid, entry=DumpLog(path=process_path)) 
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

logger = AIIDA_LOGGER.getChild("tools.dumping.engine")

class DumpEngine:
    """Core engine that orchestrates the dump process."""

    def __init__(self, config: DumpConfig, dump_paths: DumpPaths):
        self.config = config
        self.dump_paths = dump_paths
        self.dump_logger = self._initialize_logger()
        self.detector = DumpChangeDetector(self.dump_logger, self.config)

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
            self._handle_deleted_nodes()
            return

        # Prepare the dump path
        prepare_dump_path(
            path_to_validate=self.dump_paths.absolute,
            dump_mode=self.config.dump_mode,
            safeguard_file=DumpPaths.safeguard_file,
        )

        # Detect changes
        if isinstance(entity, orm.Group):
            changes = self.detector.detect_changes(group=entity)
            self._handle_group_dump(entity, changes)
        elif isinstance(entity, orm.ProcessNode):
            self._handle_process_dump(entity)
        else:
            # Assume profile dump - handle all groups in the profile
            self._handle_profile_dump()

        # Save the log
        self.dump_logger.save_log()

    def _handle_group_dump(self, group: orm.Group, changes: dict) -> None:
        """Handle dumping for a specific group."""
        # Update group structure if needed
        if self.config.update_groups:
            self._update_group_structure(changes['group_changes'])

        # Dump new nodes
        self._dump_nodes(changes['new_nodes'], group)

    def _handle_process_dump(self, process: orm.ProcessNode) -> None:
        """Handle dumping for a specific process."""
        from aiida.tools.dumping.entities.process import ProcessDumper

        process_dumper = ProcessDumper(
            process_node=process,
            dump_mode=self.config.dump_mode,
            dump_paths=self.dump_paths,
            dump_logger=self.dump_logger,
            config=self._create_process_config(),
        )
        process_dumper.dump()

    def _handle_profile_dump(self) -> None:
        """Handle dumping for a profile."""
        # Always update the group node mapping to ensure we catch all groups
        # This is crucial for finding newly created groups
        current_mapping = self.dump_logger.build_current_group_node_mapping()
        self.dump_logger.group_node_mapping = current_mapping

        # Handle all groups, including newly created ones
        self._handle_groups()

        # Handle ungrouped nodes if needed
        if self.config.also_ungrouped:
            self._handle_ungrouped_nodes()

    def _handle_groups(self) -> None:
        """Process all groups in the database, ensuring we include newly created ones."""
        # Query all groups directly from the database to ensure we get the latest state
        qb = orm.QueryBuilder()
        qb.append(orm.Group)
        groups = qb.all(flat=True)

        logger.report(f"Found {len(groups)} groups to process")

        for group in groups:
            # Create a group-specific detector
            group_detector = DumpChangeDetector(
                self.dump_logger,
                # Create config with IN_GROUP scope
                DumpConfig(**{**self.config.__dict__, 'group_scope': NodeDumpGroupScope.IN_GROUP}),
            )

            group_changes = group_detector.detect_changes(group=group)

            # Check if there are any new nodes to dump
            new_calcs = len(group_changes['new_nodes'].calculations)
            new_wfs = len(group_changes['new_nodes'].workflows)
            
            # If there are new nodes or if this is a newly created group (not in the log yet)
            if new_calcs > 0 or new_wfs > 0 or group.uuid not in self.dump_logger.groups.entries:
                logger.report(f"Processing group '{group.label}' with {new_calcs} new calculations and {new_wfs} new workflows")
                
                # Dump the group
                self._handle_group_dump(group, group_changes)
            else:
                logger.report(f"No changes detected for group '{group.label}', skipping")

    def _update_group_structure(self, group_changes: dict) -> None:
        """Update dump structure based on group changes."""
        # Handle deleted groups
        for group_info in group_changes['deleted_groups']:
            self._delete_group(group_info)

        # Handle modified groups
        for group_info in group_changes['modified_groups']:
            self._update_group(group_info)
    
    def _update_group(self, group_info: dict) -> None:
        """Update a group's dump based on membership changes."""
        group_uuid = group_info['uuid']
        
        try:
            # Load the group
            group = orm.load_group(uuid=group_uuid)
            
            # Get the group entry from the logger
            group_entry = self.dump_logger.groups.get_entry(group_uuid)
            if group_entry is None:
                # Group exists in DB but not in log - skip
                msg = f"Group {group.label} found in DB but not in log - skipping update"
                logger.warning(msg)
                return
                
            group_path = group_entry.path
            
            # Handle nodes added to this group
            if 'nodes_added' in group_info:
                logger.report(f"Updating {len(group_info['nodes_added'])} nodes added to group {group.label}")
                
                for node_uuid in group_info['nodes_added']:
                    try:
                        # Get the node
                        node = orm.load_node(uuid=node_uuid)
                        
                        # Create appropriate path for this node
                        if isinstance(node, orm.CalculationNode):
                            node_type_path = group_path / 'calculations'
                        elif isinstance(node, orm.WorkflowNode):
                            node_type_path = group_path / 'workflows'
                        else:
                            # Skip other node types
                            continue
                            
                        # Dump the node
                        self._dump_process(node, group)
                        
                    except Exception as e:
                        logger.warning(f"Error processing node {node_uuid} added to group: {e}")
            
            # Handle nodes removed from this group
            if 'nodes_removed' in group_info:
                logger.report(f"Cleaning up {len(group_info['nodes_removed'])} nodes removed from group {group.label}")
                
                for node_uuid in group_info['nodes_removed']:
                    # Try to find the node path in the logger
                    try:
                        node_path = self.dump_logger.get_dump_path_by_uuid(uuid=node_uuid)
                        
                        # Check if the path exists and is within this group's directory
                        if node_path and str(group_path) in str(node_path):
                            # Delete the directory
                            safe_delete_dir(path=node_path, safeguard_file=DumpPaths.safeguard_file)
                            
                            # Remove from logger
                            store_key = None
                            for key in ['calculations', 'workflows', 'data']:
                                store = getattr(self.dump_logger, key)
                                if node_uuid in store.entries:
                                    store_key = key
                                    break
                                    
                            if store_key:
                                store = getattr(self.dump_logger, store_key)
                                self.dump_logger.del_entry(store=store, uuid=node_uuid)
                    except Exception as e:
                        logger.warning(f"Error cleaning up node {node_uuid} removed from group: {e}")
                        
        except Exception as e:
            logger.warning(f"Error updating group {group_uuid}: {e}")

    def _delete_group(self, group_info: dict) -> None:
        """Delete a group's dump directory."""
        group_uuid = group_info['uuid']
        group_entry = self.dump_logger.groups.get_entry(group_uuid)

        if group_entry:
            path = group_entry.path
            safe_delete_dir(path=path, safeguard_file=DumpPaths.safeguard_file)
            self.dump_logger.del_entry(self.dump_logger.groups, group_uuid)

    def _get_group_path(self, group: orm.Group) -> Path:
        """Get the path for a group."""
        if self.config.organize_by_groups:
            # Using existing utility
            return self.dump_paths.absolute / 'groups' / get_group_subpath(group)
        else:
            return self.dump_paths.absolute

    def _dump_nodes(self, node_store: DumpNodeStore, group: orm.Group | None = None) -> None:
        """Dump nodes from a node store."""
        # Dump calculations and workflows with progress reporting
        from aiida.common.progress_reporter import get_progress_reporter, set_progress_bar_tqdm

        set_progress_bar_tqdm()

        for process_type in ('calculations', 'workflows'):
            processes = getattr(node_store, process_type)
            if processes:
                with get_progress_reporter()(desc=f'Dumping {process_type}', total=len(processes)) as progress:
                    for process in processes:
                        self._dump_process(process, group)
                        progress.update()

    def _dump_process(self, process: orm.ProcessNode, group: orm.Group | None = None) -> None:
        """Dump a single process."""
        from aiida.tools.dumping.entities import ProcessDumper
        from aiida.tools.dumping.storage import DumpStoreKeys

        if group:
            group_path = self._get_group_path(group)
            # Ensure the group directory exists
            group_path.mkdir(parents=True, exist_ok=True)
            # TODO: Not sure if I should add that here
            # Add the safeguard file if it doesn't exist
            # (group_path / self.dump_paths.safeguard_file).touch(exist_ok=True)
            
            # Register the group in the logger if it's not already there
            if group.uuid not in self.dump_logger.groups.entries:
                self.dump_logger.groups.add_entry(
                    uuid=group.uuid,
                    entry=DumpLog(path=group_path)
                )
            
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

        process_paths = DumpPaths.from_path(process_path)

        # Get store instances for current and other type
        current_store_key = DumpStoreKeys.from_instance(node_inst=process)
        other_store_key = (
            DumpStoreKeys.CALCULATIONS if current_store_key == DumpStoreKeys.WORKFLOWS else DumpStoreKeys.WORKFLOWS
        )

        current_store = self.dump_logger.get_store_by_name(name=current_store_key)
        other_store = self.dump_logger.get_store_by_name(name=other_store_key)

        if not self.config.symlink_calcs:
            # No symlinking - create a new dump
            process_dumper = ProcessDumper(
                process_node=process,
                dump_mode=self.config.dump_mode,
                dump_paths=process_paths,
                dump_logger=self.dump_logger,
                config=self._create_process_config(),
            )
            process_dumper.dump(top_level_caller=False)
        else:
            # Try to create symlink from stores
            symlinked = self.create_symlink_from_store(
                process_uuid=process.uuid,
                store_instance=current_store,
                process_dump_path=process_path,
            )

            # If not found in current_store, try other_store
            if not symlinked:
                symlinked = self.create_symlink_from_store(
                    process_uuid=process.uuid,
                    store_instance=other_store,
                    process_dump_path=process_path,
                )

            # If not found in either store, create a new dump
            if not symlinked:
                process_dumper = ProcessDumper(
                    process_node=process,
                    dump_mode=self.config.dump_mode,
                    dump_paths=process_paths,
                    dump_logger=self.dump_logger,
                    config=self._create_process_config(),
                )
                process_dumper.dump(top_level_caller=False)

        # This happens regardless of which case was executed
        current_store.add_entry(uuid=process.uuid, entry=DumpLog(path=process_path))

    def _create_process_config(self) -> ProcessDumperConfig:
        """Create a ProcessDumperConfig from the unified config."""
        return ProcessDumperConfig(
            include_inputs=self.config.include_inputs,
            include_outputs=self.config.include_outputs,
            include_attributes=self.config.include_attributes,
            include_extras=self.config.include_extras,
            flat=self.config.flat,
            dump_unsealed=self.config.dump_unsealed,
            symlink_calcs=self.config.symlink_calcs,
        )

    def create_symlink_from_store(self, process_uuid: str, store_instance, process_dump_path: Path) -> bool:
        """Create a symlink from an existing entry in a store to a new path."""
        if process_uuid not in store_instance.entries.keys():
            return False

        if not process_dump_path.exists():
            process_dump_path.parent.mkdir(exist_ok=True, parents=True)
            try:
                os.symlink(
                    src=store_instance.entries[process_uuid].path,
                    dst=process_dump_path,
                )
            except FileExistsError:
                # Already exists, which is fine
                pass

        return True

    def _handle_ungrouped_nodes(self) -> None:
        """Handle dumping of ungrouped nodes."""
        # Create a detector specifically for ungrouped nodes
        ungrouped_detector = DumpChangeDetector(
            self.dump_logger,
            # Create config with NO_GROUP scope
            DumpConfig(**{**self.config.__dict__, 'group_scope': NodeDumpGroupScope.NO_GROUP}),
        )

        # Get path for ungrouped nodes
        if self.config.organize_by_groups:
            no_group_path = self.dump_paths.absolute / 'no-group'
        else:
            no_group_path = self.dump_paths.absolute

        # Get changes for ungrouped nodes
        ungrouped_changes = ungrouped_detector.detect_changes()

        # Create dump paths
        no_group_dump_paths = DumpPaths(parent=no_group_path.parent, child=no_group_path.name)

        # Create an engine for ungrouped nodes
        ungrouped_engine = DumpEngine(
            config=DumpConfig(**{**self.config.__dict__, 'group_scope': NodeDumpGroupScope.NO_GROUP}),
            dump_paths=no_group_dump_paths,
        )

        # Handle the dumping
        ungrouped_engine._dump_nodes(ungrouped_changes['new_nodes'], group=None)


# import json
# import os
# from pathlib import Path

# from aiida import orm
# from aiida.tools.dumping.config import DumpConfig, DumpMode, NodeDumpGroupScope, ProcessDumperConfig
# from aiida.tools.dumping.detector import DumpChangeDetector
# from aiida.tools.dumping.storage import DumpLog, DumpLogger, DumpNodeStore
# from aiida.tools.dumping.utils.groups import get_group_subpath
# from aiida.tools.dumping.utils.paths import (
#     DumpPaths,
#     generate_process_default_dump_path,
#     prepare_dump_path,
#     safe_delete_dir,
# )
# from aiida.common.log import AIIDA_LOGGER
# from aiida.tools.dumping.utils.time import DumpTimes

# logger = AIIDA_LOGGER.getChild("tools.dumping.engine")

# class DumpEngine:
#     """Core engine that orchestrates the dump process."""
#     # TODO: Either, overwrite not passed through, or log file not properly deleted beforehand -> Somehow before manually
#     # TODO: removing the directory, the `changes` where always empty

#     def __init__(self, config: DumpConfig, dump_paths: DumpPaths):
#         self.config = config
#         self.dump_paths = dump_paths
#         self.dump_logger = self._initialize_logger()
#         self.detector = DumpChangeDetector(self.dump_logger, self.config)

#     def _initialize_logger(self) -> DumpLogger:
#         """Initialize the dump logger."""
#         if self.config.dump_mode == DumpMode.OVERWRITE and self.dump_paths.log_path.exists():
#             self.dump_paths.log_path.unlink()

#         try:
#             return DumpLogger.from_file(dump_paths=self.dump_paths)
#         except (json.JSONDecodeError, OSError):
#             return DumpLogger(dump_paths=self.dump_paths, dump_times=DumpTimes())

#     def dump(self, entity=None) -> None:
#         """Main dump entry point that handles all types of entities."""
#         # Handle special case for deletion
#         # TODO: This is broken
#         if self.config.delete_missing:
#             self._handle_deleted_nodes()
#             return

#         # Prepare the dump path
#         prepare_dump_path(
#             path_to_validate=self.dump_paths.absolute,
#             dump_mode=self.config.dump_mode,
#             safeguard_file=DumpPaths.safeguard_file,
#         )

#         # Detect changes
#         if isinstance(entity, orm.Group):
#             changes = self.detector.detect_changes(group=entity)
#             self._handle_group_dump(entity, changes)
#         elif isinstance(entity, orm.ProcessNode):
#             self._handle_process_dump(entity)
#         else:
#             # Assume profile dump
#             # TODO: See if I even need this for top level changes
#             # changes = self.detector.detect_changes()
#             # self._handle_profile_dump(changes)
#             self._handle_profile_dump()

#         # Save the log
#         # import ipdb; ipdb.set_trace()
#         self.dump_logger.save_log()

#     def _handle_group_dump(self, group: orm.Group, changes: dict) -> None:
#         """Handle dumping for a specific group."""
#         # Update group structure if needed
#         if self.config.update_groups:
#             self._update_group_structure(changes['group_changes'])

#         # Dump new nodes
#         self._dump_nodes(changes['new_nodes'], group)


#     def _handle_process_dump(self, process: orm.ProcessNode) -> None:
#         """Handle dumping for a specific process."""
#         from aiida.tools.dumping.entities.process import ProcessDumper

#         process_dumper = ProcessDumper(
#             process_node=process,
#             dump_mode=self.config.dump_mode,
#             dump_paths=self.dump_paths,
#             dump_logger=self.dump_logger,
#             config=self._create_process_config(),
#         )
#         process_dumper.dump()

#     def _handle_profile_dump(self, global_changes: dict | None = None) -> None:
#         """Handle dumping for a profile."""
#         # Update group structure if needed
#         # TODO: Properly implement the group changes implementation
#         # if self.config.update_groups:
#         #     self._update_group_structure(global_changes['group_changes'])

#         # Handle group dumps
#         self._handle_groups()

#         # Handle ungrouped nodes if needed
#         if self.config.also_ungrouped:
#             self._handle_ungrouped_nodes()


#     def _handle_groups(self) -> None:
#         # TODO: Allow specifying groups manually
#         # TODO: Possibl move the group handling to the top-level handle profile dump method
#         qb = orm.QueryBuilder()
#         qb.append(orm.Group)
#         groups = qb.all(flat=True)

#         for group in groups:
#             # Create a group-specific detector
#             group_detector = DumpChangeDetector(
#                 self.dump_logger,
#                 # Create config with IN_GROUP scope
#                 DumpConfig(**{**self.config.__dict__, 'group_scope': NodeDumpGroupScope.IN_GROUP}),
#             )


#             group_changes = group_detector.detect_changes(group=group)
#             # import ipdb; ipdb.set_trace()

#             group_engine = DumpEngine(config=self.config, dump_paths=self.dump_paths)

#             # Dump the group
#             group_engine._handle_group_dump(group, group_changes)

#     def _update_group_structure(self, group_changes: dict) -> None:
#         """Update dump structure based on group changes."""
#         # Handle deleted groups
#         for group_info in group_changes['deleted_groups']:
#             self._delete_group(group_info)

#         # Handle modified groups
#         for group_info in group_changes['modified_groups']:
#             self._update_group(group_info)
    
#     def _update_group(self, group_info: dict) -> None:
#         """Update a group's dump based on membership changes."""
#         group_uuid = group_info['uuid']
        
#         try:
#             # Load the group
#             group = orm.load_group(uuid=group_uuid)
            
#             # Get the group entry from the logger
#             group_entry = self.dump_logger.groups.get_entry(group_uuid)
#             if group_entry is None:
#                 # Group exists in DB but not in log - skip
#                 msg = f"Group {group.label} found in DB but not in log - skipping update"
#                 logger.warning(msg)
#                 return
                
#             group_path = group_entry.path
            
#             # Handle nodes added to this group
#             if 'nodes_added' in group_info:
#                 logger.report(f"Updating {len(group_info['nodes_added'])} nodes added to group {group.label}")
                
#                 for node_uuid in group_info['nodes_added']:
#                     try:
#                         # Get the node
#                         node = orm.load_node(uuid=node_uuid)
                        
#                         # Create appropriate path for this node
#                         if isinstance(node, orm.CalculationNode):
#                             node_type_path = group_path / 'calculations'
#                         elif isinstance(node, orm.WorkflowNode):
#                             node_type_path = group_path / 'workflows'
#                         else:
#                             # Skip other node types
#                             continue
                            
#                         # Dump the node
#                         self._dump_process(node, group)
                        
#                     except Exception as e:
#                         logger.warning(f"Error processing node {node_uuid} added to group: {e}")
            
#             # Handle nodes removed from this group
#             if 'nodes_removed' in group_info:
#                 logger.report(f"Cleaning up {len(group_info['nodes_removed'])} nodes removed from group {group.label}")
                
#                 for node_uuid in group_info['nodes_removed']:
#                     # Try to find the node path in the logger
#                     try:
#                         node_path = self.dump_logger.get_dump_path_by_uuid(uuid=node_uuid)
                        
#                         # Check if the path exists and is within this group's directory
#                         if node_path and str(group_path) in str(node_path):
#                             # Delete the directory
#                             safe_delete_dir(path=node_path, safeguard_file=DumpPaths.safeguard_file)
                            
#                             # Remove from logger
#                             store_key = None
#                             for key in ['calculations', 'workflows', 'data']:
#                                 store = getattr(self.dump_logger, key)
#                                 if node_uuid in store.entries:
#                                     store_key = key
#                                     break
                                    
#                             if store_key:
#                                 store = getattr(self.dump_logger, store_key)
#                                 self.dump_logger.del_entry(store=store, uuid=node_uuid)
#                     except Exception as e:
#                         logger.warning(f"Error cleaning up node {node_uuid} removed from group: {e}")
                        
#         except Exception as e:
#             logger.warning(f"Error updating group {group_uuid}: {e}")

#     def _delete_group(self, group_info: dict) -> None:
#         """Delete a group's dump directory."""
#         group_uuid = group_info['uuid']
#         group_entry = self.dump_logger.groups.get_entry(group_uuid)

#         if group_entry:
#             path = group_entry.path
#             safe_delete_dir(path=path, safeguard_file=DumpPaths.safeguard_file)
#             self.dump_logger.del_entry(self.dump_logger.groups, group_uuid)

#     def _get_group_path(self, group: orm.Group) -> Path:
#         """Get the path for a group."""
#         if self.config.organize_by_groups:
#             # Using existing utility
#             return self.dump_paths.absolute / 'groups' / get_group_subpath(group)
#         else:
#             return self.dump_paths.absolute

#     def _dump_nodes(self, node_store: DumpNodeStore, group: orm.Group | None = None) -> None:
#         """Dump nodes from a node store."""
#         # Dump calculations and workflows with progress reporting
#         try:
#             from aiida.common.progress_reporter import get_progress_reporter, set_progress_bar_tqdm

#             set_progress_bar_tqdm()

#             for process_type in ('calculations', 'workflows'):
#                 processes = getattr(node_store, process_type)
#                 if processes:
#                     with get_progress_reporter()(desc=f'Dumping {process_type}', total=len(processes)) as progress:
#                         for process in processes:
#                             self._dump_process(process, group)
#                             progress.update()
#         except ImportError:
#             # Fallback if progress reporting isn't available
#             for calc in node_store.calculations:
#                 self._dump_process(calc, group)
#             for wf in node_store.workflows:
#                 self._dump_process(wf, group)

#     # def _dump_nodes(self, node_store: DumpNodeStore, group: orm.Group | None = None) -> None:
#     #     """Dump nodes from a node store."""
#     #     # Dump calculations
#     #     for calc in node_store.calculations:
#     #         self._dump_process(calc, group)

#     #     # Dump workflows
#     #     for wf in node_store.workflows:
#     #         self._dump_process(wf, group)

#     def _dump_process(self, process: orm.ProcessNode, group: orm.Group | None = None) -> None:
#         """Dump a single process."""
#         from aiida.tools.dumping.entities import ProcessDumper
#         from aiida.tools.dumping.storage import DumpStoreKeys

#         if group:
#             group_path = self._get_group_path(group)
#             # (group_path / self.dump_paths.safeguard_file).touch()
#             if isinstance(process, orm.CalculationNode):
#                 process_path = group_path / 'calculations'
#             else:
#                 process_path = group_path / 'workflows'
#         else:
#             process_path = self.dump_paths.absolute

#         process_name = generate_process_default_dump_path(process)
#         process_path = process_path / process_name

#         process_paths = DumpPaths.from_path(process_path)

#         # Get store instances for current and other type
#         current_store_key = DumpStoreKeys.from_instance(node_inst=process)
#         other_store_key = (
#             DumpStoreKeys.CALCULATIONS if current_store_key == DumpStoreKeys.WORKFLOWS else DumpStoreKeys.WORKFLOWS
#         )

#         current_store = self.dump_logger.get_store_by_name(name=current_store_key)
#         other_store = self.dump_logger.get_store_by_name(name=other_store_key)

#         if not self.config.symlink_calcs:
#             # No symlinking - create a new dump
#             process_dumper = ProcessDumper(
#                 process_node=process,
#                 dump_mode=self.config.dump_mode,
#                 dump_paths=process_paths,
#                 dump_logger=self.dump_logger,
#                 config=self._create_process_config(),
#             )
#             process_dumper.dump(top_level_caller=False)
#         else:
#             # Try to create symlink from stores
#             symlinked = self.create_symlink_from_store(
#                 process_uuid=process.uuid,
#                 store_instance=current_store,
#                 process_dump_path=process_path,
#             )

#             # If not found in current_store, try other_store
#             if not symlinked:
#                 symlinked = self.create_symlink_from_store(
#                     process_uuid=process.uuid,
#                     store_instance=other_store,
#                     process_dump_path=process_path,
#                 )

#             # If not found in either store, create a new dump
#             if not symlinked:
#                 process_dumper = ProcessDumper(
#                     process_node=process,
#                     dump_mode=self.config.dump_mode,
#                     dump_paths=process_paths,
#                     dump_logger=self.dump_logger,
#                     config=self._create_process_config(),
#                 )
#                 process_dumper.dump(top_level_caller=False)

#         # This happens regardless of which case was executed
#         current_store.add_entry(uuid=process.uuid, entry=DumpLog(path=process_path))

#     # def _dump_process(self, process: orm.ProcessNode, group: orm.Group | None = None) -> None:
#     #     """Dump a single process."""
#     #     from aiida.tools.dumping.entities import ProcessDumper
#     #     if group:
#     #         process_path = self._get_group_path(group)
#     #         if isinstance(process, orm.CalculationNode):
#     #             process_path = process_path / 'calculations'
#     #         else:
#     #             process_path = process_path / 'workflows'
#     #     else:
#     #         process_path = self.dump_paths.absolute

#     #     process_name = generate_process_default_dump_path(process)
#     #     process_path = process_path / process_name

#     #     process_dumper = ProcessDumper(
#     #         process_node=process,
#     #         dump_mode=self.config.dump_mode,
#     #         dump_paths=DumpPaths.from_path(process_path),
#     #         dump_logger=self.dump_logger,
#     #         config=self._create_process_config()
#     #     )

#     #     process_dumper.dump(top_level_caller=False)

#     def _create_process_config(self) -> ProcessDumperConfig:
#         """Create a ProcessDumperConfig from the unified config."""
#         return ProcessDumperConfig(
#             include_inputs=self.config.include_inputs,
#             include_outputs=self.config.include_outputs,
#             include_attributes=self.config.include_attributes,
#             include_extras=self.config.include_extras,
#             flat=self.config.flat,
#             dump_unsealed=self.config.dump_unsealed,
#             symlink_calcs=self.config.symlink_calcs,
#         )

#     def create_symlink_from_store(self, process_uuid: str, store_instance, process_dump_path: Path) -> bool:
#         """Create a symlink from an existing entry in a store to a new path."""
#         if process_uuid not in store_instance.entries.keys():
#             return False

#         if not process_dump_path.exists():
#             process_dump_path.parent.mkdir(exist_ok=True, parents=True)
#             try:
#                 os.symlink(
#                     src=store_instance.entries[process_uuid].path,
#                     dst=process_dump_path,
#                 )
#             except FileExistsError:
#                 # Already exists, which is fine
#                 pass

#         return True

#     # TODO: This doesn't respect `calculations` and `workflows` subdirectories
#     def _handle_ungrouped_nodes(self) -> None:
#         """Handle dumping of ungrouped nodes."""
#         # Create a detector specifically for ungrouped nodes
#         ungrouped_detector = DumpChangeDetector(
#             self.dump_logger,
#             # Create config with NO_GROUP scope
#             DumpConfig(**{**self.config.__dict__, 'group_scope': NodeDumpGroupScope.NO_GROUP}),
#         )

#         # Get path for ungrouped nodes
#         if self.config.organize_by_groups:
#             no_group_path = self.dump_paths.absolute / 'no-group'
#         else:
#             no_group_path = self.dump_paths.absolute

#         # Get changes for ungrouped nodes
#         ungrouped_changes = ungrouped_detector.detect_changes()

#         # Create dump paths
#         no_group_dump_paths = DumpPaths(parent=no_group_path.parent, child=no_group_path.name)

#         # Create an engine for ungrouped nodes
#         ungrouped_engine = DumpEngine(
#             config=DumpConfig(**{**self.config.__dict__, 'group_scope': NodeDumpGroupScope.NO_GROUP}),
#             dump_paths=no_group_dump_paths,
#         )

#         # Handle the dumping
#         ungrouped_engine._dump_nodes(ungrouped_changes['new_nodes'], group=None)

#     # def dump_process(
#     #     self,
#     #     process: orm.CalculationNode | orm.WorkflowNode,
#     #     process_type_path: Path,
#     # ) -> None:
#     #     """Dump a single process to disk.

#     #     :param process: An AiiDA calculation or workflow node to dump
#     #     :param process_type_path: Path where processes of this type are stored
#     #     :param process_dump: The ProcessDump instance to use
#     #     """
#     #     process_dump_path = process_type_path / generate_process_default_dump_path(process_node=process, prefix=None)

#     #     process_paths = DumpPaths(
#     #         parent=process_dump_path.parent,
#     #         child=Path(process_dump_path.name),
#     #     )

#     #     process_dumper = ProcessDumper(
#     #         process_node=process,
#     #         dump_mode=self.dump_mode,
#     #         dump_paths=process_paths,
#     #         config=self.process_dump_config,
#     #         dump_logger=self.dump_logger,
#     #     )

#     #     if not self.config.symlink_calcs:
#     #         # Case: symlink_duplicates is disabled
#     #         process_dumper.dump(top_level_caller=False)

#     #     else:
#     #         # Try to create symlink from current_store first
#     #         symlinked = self.create_symlink_from_store(
#     #             process_uuid=process.uuid,
#     #             store_instance=self.current_store,
#     #             process_dump_path=process_dump_path,
#     #         )

#     #         # If not found in current_store, try other_store
#     #         if not symlinked:
#     #             symlinked = self.create_symlink_from_store(
#     #                 process_uuid=process.uuid,
#     #                 store_instance=self.other_store,
#     #                 process_dump_path=process_dump_path,
#     #             )

#     #         # If not found in either store, create a new dump
#     #         if not symlinked:
#     #             process_dumper.dump(top_level_caller=False)

#     #     # This happens regardless of which case was executed
#     #     self.current_store.add_entry(uuid=process.uuid, entry=DumpLog(path=process_dump_path))

#     # def dump_processes(self, processes: list[orm.CalculationNode] | list[orm.WorkflowNode]) -> None:
#     #     """Dump a list of AiiDA calculations or workflows to disk.

#     #     :param processes: List of AiiDA calculations or workflows from the ``ProcessesToDumpContainer``.
#     #     """

#     #     if len(processes) == 0:
#     #         return

#     #     # Setup common resources needed for dumping
#     #     process_type_path = self.dump_paths.absolute / DumpStoreKeys.from_instance(node_inst=processes[0])
#     #     process_type_path.mkdir(exist_ok=True, parents=True)

#     #     # NOTE: This seems a bit hacky. Can probably be improved
#     #     # Get the store key as a string from the instance
#     #     current_store_key_str = DumpStoreKeys.from_instance(node_inst=next(iter(processes)))

#     #     # Convert string to actual enum members
#     #     current_store_key = DumpStoreKeys(current_store_key_str)
#     #     other_store_key = (
#     #         DumpStoreKeys.CALCULATIONS if current_store_key == DumpStoreKeys.WORKFLOWS else DumpStoreKeys.WORKFLOWS
#     #     )

#     #     current_store = self.dump_logger.get_store_by_name(name=current_store_key.value)
#     #     other_store = self.dump_logger.get_store_by_name(name=other_store_key.value)

#     #     self.current_store: DumpLogStore = current_store
#     #     self.other_store: DumpLogStore = other_store

#     #     set_progress_bar_tqdm()

#     #     # Dump each process with progress tracking
#     #     with get_progress_reporter()(desc='Dumping new processes', total=len(processes)) as progress:
#     #         for process in processes:
#     #             self.dump_process(
#     #                 process=process,
#     #                 process_type_path=process_type_path,
#     #             )
#     #             progress.update()

#     # def dump_node_store(self, dump_store: DumpNodeStore) -> None:
#     #     """Handle dumping of different process collections."""

#     #     # First, dump calculations and then workflows, as sub-calculations of workflows can be symlinked
#     #     for process_type in ('calculations', 'workflows'):
#     #         processes = getattr(dump_store, process_type)
#     #         if len(processes) > 0:
#     #             msg = f'Dumping {len(processes)} {process_type}...'
#     #             logger.report(msg)
#     #             self.dump_processes(processes=processes)
#     #         else:
#     #             if self.group is not None:
#     #                 msg = f'No (new) {process_type} to dump in group `{self.group.label}`.'
#     #             else:
#     #                 msg = f'No (new) ungrouped {process_type} to dump.'
#     #             logger.report(msg)

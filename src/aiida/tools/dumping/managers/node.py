from __future__ import annotations

import os
from typing import TYPE_CHECKING

from aiida import orm
from aiida.common.log import AIIDA_LOGGER
from aiida.common.progress_reporter import get_progress_reporter, set_progress_bar_tqdm
from aiida.tools.dumping.entities.process import ProcessDumper
from aiida.tools.dumping.managers.group import GroupManager
from aiida.tools.dumping.utils.paths import DumpPaths, generate_process_default_dump_path, safe_delete_dir
from aiida.tools.dumping.utils.time import DumpTimes
from aiida.tools.dumping.utils.types import DumpStoreKeys

if TYPE_CHECKING:
    from aiida.tools.dumping.config import DumpConfig
    from aiida.tools.dumping.logger import DumpLogger
    from aiida.tools.dumping.utils.types import DumpNodeStore

logger = AIIDA_LOGGER.getChild("tools.dumping.managers.node")


class NodeManager:
    """Handles the processing and dumping of individual nodes"""

    def __init__(
        self,
        config: DumpConfig,
        dump_paths: DumpPaths,
        dump_logger: DumpLogger,
        dump_times: DumpTimes,
        group_manager: GroupManager,
    ):
        self.config: DumpConfig = config
        self.dump_paths: DumpPaths = dump_paths
        self.dump_logger: DumpLogger = dump_logger
        self.dump_times: DumpTimes = dump_times
        self.group_manager: GroupManager = group_manager

    # Could unify that for `processes` in general
    # def dump_nodes(self, node_store: DumpNodeStore, group: orm.Group | None = None):
    #     """Dump a collection of nodes from a node store within an optional group context."""

    #     set_progress_bar_tqdm() # Initialize progress bar style

    #     nodes_to_dump = []
    #     # Combine calculations and workflows for unified progress bar
    #     nodes_to_dump.extend(node_store.calculations)
    #     nodes_to_dump.extend(node_store.workflows)
    #     # Add data nodes if applicable
    #     # nodes_to_dump.extend(node_store.data)

    #     if not nodes_to_dump:
    #          return # Nothing to dump

    #     desc = f'Dumping {len(nodes_to_dump)} nodes'
    #     if group:
    #         desc += f" for group '{group.label}'"

    #     with get_progress_reporter()(desc=desc, total=len(nodes_to_dump)) as progress:
    #         for node in nodes_to_dump:
    #             try:
    #                 self.dump_process(node, group) # Changed method name to be generic 'node'
    #             except Exception as e:
    #                  # Log error but continue with other nodes
    #                  logger.error(f"Failed to dump node PK={node.pk} (UUID={node.uuid}): {e}", exc_info=True)
    #             finally:
    #                  progress.update() # Ensure progress bar updates even on error

    def dump_nodes(self, node_store: DumpNodeStore, group=None):
        """Dump a collection of nodes from a node store"""

        set_progress_bar_tqdm()

        for process_type in ("calculations", "workflows"):
            processes = getattr(node_store, process_type)
            if processes:
                with get_progress_reporter()(
                    desc=f"Dumping {process_type}", total=len(processes)
                ) as progress:
                    for process in processes:
                        self.dump_process(process, group)
                        progress.update()

    # def dump_process(self, process, group=None):
    #     """Dump a single process."""

    #     if group:
    #         # Use the group manager to get the proper path
    #         group_base_path = self.group_manager.get_group_path(group)

    #         # Determine subdirectory within the group ('calculations', 'workflows', 'data')
    #         if isinstance(process, orm.CalculationNode):
    #             type_subdir = "calculations"
    #         elif isinstance(process, orm.WorkflowNode):
    #             type_subdir = "workflows"
    #         # elif isinstance(node, orm.Data):
    #         #     type_subdir = 'data' # Add if handling DataNodes
    #         else:
    #             # Should not happen if node_store is populated correctly
    #             logger.warning(
    #                 f"Cannot determine type subdir for node {process.pk} in group {group.label}"
    #             )
    #             type_subdir = "unknown"

    #     # Dumping outside a group context (e.g., ungrouped nodes, or flat structure)
    #     # Determine subdirectory ('calculations', 'workflows', 'data') directly under root dump path
    #     elif isinstance(process, orm.CalculationNode):
    #         type_subdir = "calculations"
    #     elif isinstance(process, orm.WorkflowNode):
    #         type_subdir = "workflows"
    #     # elif isinstance(node, orm.Data):
    #     #     type_subdir = 'data'
    #     else:
    #         type_subdir = "unknown"

    #     node_parent_path = self.dump_paths.absolute / type_subdir
    #     node_parent_path.mkdir(parents=True, exist_ok=True)

    #     process_name = generate_process_default_dump_path(process)
    #     process_path = node_parent_path / process_name

    #     store_key = DumpStoreKeys.from_instance(node_inst=process)
    #     existing_log_entry = self.dump_logger.get_store_by_name(store_key).get_entry(
    #         process.uuid
    #     )

    #     if existing_log_entry:
    #         # Node already dumped, potentially handle symlinking if configured
    #         if (
    #             self.config.symlink_calcs
    #             and isinstance(process, orm.CalculationNode)
    #             and group
    #         ):
    #             target_path = existing_log_entry.path
    #             link_path = process_path

    #             if link_path.exists():
    #                 logger.warning(
    #                     f"Path {link_path} already exists, skipping symlink creation for node {process.pk}."
    #                 )
    #                 return  # Skip dumping if path exists

    #             try:
    #                 # Create relative symlink if possible
    #                 # link_target_rel = os.path.relpath(target_path, start=link_path.parent)
    #                 os.symlink(target_path, link_path, target_is_directory=True)
    #                 logger.debug(f"Created symlink {link_path} -> {target_path}")
    #                 # Optionally update the original log entry with the symlink location?
    #                 # existing_log_entry.add_symlink(link_path) # Requires logger update/save
    #                 return  # Don't proceed with full dump
    #             except OSError as e:
    #                 logger.error(
    #                     f"Failed to create symlink {link_path} for node {process.pk}: {e}"
    #                 )
    #                 # Fall through to full dump on error? Or just return? Decide behavior.
    #                 return  # Probably safer to just skip on error
    #         else:
    #             # Already logged, but not symlinking or not applicable type/context
    #             logger.debug(
    #                 f"Node {process.pk} already logged at {existing_log_entry.path}, skipping dump."
    #             )
    #             return

    #     # --- Dump the node (if not skipped by logging/symlinking) ---
    #     # Extract ProcessDumper specific config
    #     process_config = self.config.get_process_config()
    #     # Note: Pass the specific dump mode from the main config
    #     dump_mode = self.config.dump_mode

    #     # Instantiate and run the dumper
    #     try:
    #         # We assume ProcessDumper can handle the node types we pass it
    #         # If DataNodes need a different dumper, add conditional logic here
    #         process_dumper = ProcessDumper(
    #             process_node=process,
    #             dump_paths=DumpPaths.from_path(process_path),
    #             dump_logger=self.dump_logger,
    #             dump_times=self.dump_times,
    #             config=process_config,
    #             dump_mode=dump_mode,
    #         )

    #         # Run the dump, indicating it's not the absolute top-level call
    #         process_dumper.dump(top_level_caller=False)

    #         # Logger update is now handled *inside* ProcessDumper.dump/_dump_calculation/_dump_workflow
    #         # No need to add entry here again.
    #         logger.debug(f"Successfully dumped node {process.pk} to {process_path}")

    #     except Exception as e:
    #         # Catch exceptions during the dumping of this specific node
    #         logger.error(
    #             f"Failed during dump of node PK={process.pk} (UUID={process.uuid}): {e}",
    #             exc_info=True,
    #         )
    #         # Clean up partially created directory for this failed node? Optional.
    #         try:
    #             safe_delete_dir(
    #                 process_path, DumpPaths.safeguard_file
    #             )  # Or node metadata file as safeguard
    #         except Exception as cleanup_e:
    #             logger.error(
    #                 f"Failed to cleanup directory {process_path} after dump error: {cleanup_e}"
    #             )

    #     # ? Previous implementation
    #     # # Create process dumper and dump the process
    #     # from aiida.tools.dumping.config import ProcessDumperConfig

    #     # process_config = ProcessDumperConfig(
    #     #     include_inputs=self.config.include_inputs,
    #     #     include_outputs=self.config.include_outputs,
    #     #     include_attributes=self.config.include_attributes,
    #     #     include_extras=self.config.include_extras,
    #     #     flat=self.config.flat,
    #     #     dump_unsealed=self.config.dump_unsealed,
    #     #     symlink_calcs=self.config.symlink_calcs,
    #     # )

    #     # from aiida.tools.dumping.utils.paths import DumpPaths
    #     # process_paths = DumpPaths.from_path(process_path)

    #     # process_dumper = ProcessDumper(
    #     #     process_node=process,
    #     #     dump_mode=self.config.dump_mode,
    #     #     dump_paths=process_paths,
    #     #     dump_logger=self.dump_logger,
    #     #     config=process_config,
    #     # )

    #     # process_dumper.dump(top_level_caller=False)

    #     # # Update the logger
    #     # current_store_key = DumpStoreKeys.from_instance(node_inst=process)
    #     # current_store = self.dump_logger.get_store_by_name(name=current_store_key)
    #     # current_store.add_entry(uuid=process.uuid, entry=DumpLog(path=process_path))


    def dump_process(self, process, group=None):
        """Dump a single process, placing it correctly based on group context and config."""
        node = process

        # --- Determine the correct parent path for the node's type subdirectory ---
        # if group and self.config.organize_by_groups:
        if self.config.organize_by_groups:
            # === Grouped & Organized Path ===
            # get_group_path ensures .../groups/group_label exists
            group_base_path = self.group_manager.prepare_group_path(group)
            if isinstance(node, orm.CalculationNode):
                type_subdir = "calculations"
            elif isinstance(node, orm.WorkflowNode):
                type_subdir = "workflows"
            else:
                type_subdir = "unknown"
            # Place type subdir inside the group's base path
            node_parent_path = group_base_path / type_subdir
        else:
            # === Flat or Ungrouped Path ===
            # Place type subdir directly under the main dump root
            if isinstance(node, orm.CalculationNode):
                type_subdir = "calculations"
            elif isinstance(node, orm.WorkflowNode):
                type_subdir = "workflows"
            else:
                type_subdir = "unknown"
            node_parent_path = self.dump_paths.absolute / type_subdir

        # Ensure the determined parent path exists (e.g., .../groups/group/calculations OR .../calculations)
        node_parent_path.mkdir(parents=True, exist_ok=True)

        # --- Determine the final path for this specific node's directory ---
        process_name = generate_process_default_dump_path(process)
        process_path = node_parent_path / process_name

        # --- Check Logging & Symlinking ---
        store_key = DumpStoreKeys.from_instance(node_inst=node)
        existing_log_entry = self.dump_logger.get_store_by_name(store_key).get_entry(node.uuid)

        if existing_log_entry:
             # Handle symlinking or skipping if already logged
             # ... (Symlink/Skip logic from previous step - check if path exists before symlinking) ...
             if (self.config.symlink_calcs and isinstance(node, orm.CalculationNode) and group):
                  target_path = existing_log_entry.path
                  link_path = process_path # Where the link *should* be placed
                  if link_path.exists() or link_path.is_symlink():
                      logger.debug(f"Path {link_path} already exists, skipping symlink for node {node.pk}.")
                      return
                  try:
                      os.symlink(target_path, link_path, target_is_directory=True)
                      logger.debug(f"Created symlink {link_path} -> {target_path}")
                      # Optionally update log with symlink info here
                      return # Don't proceed
                  except OSError as e:
                      logger.error(f"Failed symlink creation for node {node.pk} at {link_path}: {e}")
                      return # Skip on error
            #  else:
            #       logger.debug(f"Node {node.pk} already logged at {existing_log_entry.path}, skipping dump.")
            #       return # Skip dumping

        # --- Dump the node ---
        process_config = self.config.get_process_config()
        dump_mode = self.config.dump_mode
        try:
            process_dumper = ProcessDumper(
                process_node=node,
                # Pass the CORRECT final path wrapped in DumpPaths
                dump_paths=DumpPaths.from_path(process_path),
                dump_logger=self.dump_logger,
                dump_times=self.dump_times, # Pass times instance
                config=process_config,
                dump_mode=dump_mode,
            )
            process_dumper.dump(top_level_caller=False)
            logger.debug(f"Successfully dumped node {node.pk} to {process_path}")
        except Exception as e:
            logger.error(
                f"Failed during dump of node PK={node.pk} (UUID={node.uuid}): {e}",
                exc_info=True,
            )
            # Optional cleanup
            try:
                # Use metadata file as safeguard for node deletion cleanup
                safe_delete_dir(process_path, '.aiida_node_metadata.yaml')
            except Exception as cleanup_e:
                logger.error(
                    f"Failed to cleanup directory {process_path} after dump error: {cleanup_e}"
                )

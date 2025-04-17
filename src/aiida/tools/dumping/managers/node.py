from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from aiida import orm
from aiida.common.log import AIIDA_LOGGER
from aiida.common.progress_reporter import get_progress_reporter, set_progress_bar_tqdm
from aiida.orm.utils import LinkTriple
from aiida.tools.archive.exceptions import ExportValidationError
from aiida.tools.dumping.logger import DumpLog
from aiida.tools.dumping.utils.process_handlers import (
    NodeMetadataWriter,
    NodeRepoIoDumper,
    ReadmeGenerator,
    WorkflowWalker,
)
from aiida.tools.dumping.utils.paths import (
    DumpPaths,
    prepare_dump_path,
    safe_delete_dir,
)
from aiida.tools.dumping.utils.types import DumpStoreKeys
from aiida.tools.dumping.utils.paths import generate_process_default_dump_path


if TYPE_CHECKING:
    from aiida.tools.dumping.config import DumpConfig
    from aiida.tools.dumping.engine import DumpEngine
    from aiida.tools.dumping.logger import DumpLogger
    from aiida.tools.dumping.managers.group import GroupManager
    from aiida.tools.dumping.utils.time import DumpTimes
    from aiida.tools.dumping.utils.types import DumpNodeStore

logger = AIIDA_LOGGER.getChild("tools.dumping.managers.node")

# TODO: Possibly could be only NodeManager
class ProcessNodeManager:
    """Handles the processing and dumping of individual nodes"""

    def __init__(
        self,
        config: DumpConfig,
        dump_paths: DumpPaths,
        dump_logger: DumpLogger,
        dump_times: DumpTimes,
        group_manager: GroupManager,
        engine: DumpEngine,
    ):
        self.config: DumpConfig = config
        self.dump_paths: DumpPaths = dump_paths
        self.dump_logger: DumpLogger = dump_logger
        self.dump_times: DumpTimes = dump_times
        self.group_manager: GroupManager = group_manager
        self.engine: DumpEngine = engine

        # Instantiate helper classes
        self.metadata_writer = NodeMetadataWriter(config)
        self.repo_io_dumper = NodeRepoIoDumper(config)
        # Pass the bound method self.dump_process for recursion
        self.workflow_walker = WorkflowWalker(self.dump_process)
        self.readme_generator = ReadmeGenerator()  # No config needed currently

    def dump_nodes(self, node_store: DumpNodeStore, group: orm.Group | None = None):
        """Dump a collection of nodes from a node store within an optional group context."""
        # (Keep the existing dump_nodes logic with progress bar)
        set_progress_bar_tqdm()
        nodes_to_dump = []
        nodes_to_dump.extend(node_store.calculations)
        nodes_to_dump.extend(node_store.workflows)
        if not nodes_to_dump:
            return
        desc = f"Dumping {len(nodes_to_dump)} nodes"
        if group:
            desc += f" for group '{group.label}'"
        with get_progress_reporter()(desc=desc, total=len(nodes_to_dump)) as progress:
            for node in nodes_to_dump:
                try:
                    node_base_path = self._get_node_base_path(node, group)
                    self.dump_process(node, node_base_path)
                except Exception as e:
                    logger.error(
                        f"Failed preparing/dumping node PK={node.pk}: {e}",
                        exc_info=True,
                    )
                finally:
                    progress.update()

    def _get_node_base_path(self, node: orm.Node, group: orm.Group | None) -> Path:
        """Determine the correct base directory path for dumping a specific node."""
        # (Keep the logic from the previous step that uses group_manager.prepare_group_path
        # and considers engine.top_level_entity_type)
        group_base_path = self.group_manager.prepare_group_path(group)
        if isinstance(node, orm.CalculationNode):
            type_subdir = "calculations"
        elif isinstance(node, orm.WorkflowNode):
            type_subdir = "workflows"
        elif isinstance(node, orm.Data):
            type_subdir = "data"
        else:
            type_subdir = "unknown"

        if self.config.organize_by_groups and group:
            node_parent_path = group_base_path / type_subdir
        elif (
            self.config.organize_by_groups
            and not group
            # and self.engine.top_level_entity_type == "profile"
        ):
            node_parent_path = group_base_path / type_subdir
        elif not self.config.organize_by_groups:
            node_parent_path = self.dump_paths.absolute / type_subdir
        else:  # Fallback (e.g., top-level process dump)
            node_parent_path = self.dump_paths.absolute / type_subdir

        node_parent_path.mkdir(parents=True, exist_ok=True)
        # Generate specific node directory name (can remain static method)
        node_directory_name: Path = generate_process_default_dump_path(node)
        final_node_path = node_parent_path / node_directory_name

        return final_node_path

    def dump_process(
        self,
        process_node: orm.ProcessNode,
        target_path: Path,  # Final path for this node's content
    ):
        """
        Dumps a single ProcessNode by coordinating helper classes.
        Handles validation, logging checks, symlinking, and cleanup.
        """
        node = process_node

        # --- Validation ---
        if not node.is_sealed and not self.config.dump_unsealed:
            raise ExportValidationError(
                f"Process `{node.pk}` must be sealed before it can be dumped, or `--dump-unsealed` set to True."
            )

        # --- Logging Check & Symlinking ---
        store_key = DumpStoreKeys.from_instance(node_inst=node)
        node_store = self.dump_logger.get_store_by_name(store_key)
        existing_log_entry = node_store.get_entry(node.uuid)

        if existing_log_entry:
            # (Symlinking logic remains the same as previous version)
            # is_group_context = self.engine.top_level_entity_type in ["group", "profile"]
            if (
                self.config.symlink_calcs
                and isinstance(node, orm.CalculationNode)
                # and is_group_context
            ):
                if target_path.exists() or target_path.is_symlink():
                    logger.debug(
                        f"Path {target_path.name} exists, skipping symlink for node {node.pk}."
                    )
                    return
                try:
                    source_path = existing_log_entry.path
                    if not source_path.exists():
                        logger.warning(
                            f"Source path {source_path} for node {node.pk} does not exist. Cannot symlink."
                        )
                        return
                    os.symlink(source_path, target_path, target_is_directory=True)
                    logger.debug(f"Created symlink {target_path.name} -> {source_path}")
                    return
                except OSError as e:
                    logger.error(
                        f"Failed symlink creation for node {node.pk} at {target_path.name}: {e}"
                    )
                    return
            else:
                logger.debug(
                    f"Node {node.pk} already logged at {existing_log_entry.path}, skipping dump."
                )
                return

        # --- Prepare Node Directory ---
        node_safeguard_file = ".aiida_node_metadata.yaml"
        try:
            # Prepare the specific node directory
            prepare_dump_path(
                path_to_validate=target_path,
                dump_mode=self.config.dump_mode,
                safeguard_file=node_safeguard_file,
                top_level_caller=False,  # This specific node dir is not the absolute top level
            )
            # Ensure safeguard exists (prepare_dump_path touches it if created/overwritten)
            (target_path / node_safeguard_file).touch(exist_ok=True)

        except Exception as e:
            logger.error(
                f"Failed preparing target path {target_path.name} for node {node.pk}: {e}",
                exc_info=True,
            )
            return

        # --- Dump Node Content using Helpers ---
        try:
            # 1. Write Metadata
            self.metadata_writer.write(
                node, target_path, output_filename=node_safeguard_file
            )

            # 2. Add to logger (before potential errors in content dumping/recursion)
            node_store.add_entry(node.uuid, DumpLog(path=target_path.resolve()))
            # Note: Log needs saving later by the engine

            # 3. Dump Content / Recurse Children
            (target_path / DumpPaths.safeguard_file).touch()
            if isinstance(node, orm.CalculationNode):
                self.repo_io_dumper.dump_calculation_content(node, target_path)
            elif isinstance(node, orm.WorkflowNode):
                self.workflow_walker.dump_children(node, target_path)

            # 4. Generate README (Consider if this should only be done by the Strategy at the top level)
            # If called here, every node gets a README.
            # self.readme_generator.generate(node, target_path)

        except Exception as e:
            logger.error(
                f"Failed during content dump of node PK={node.pk} (UUID={node.uuid}): {e}",
                exc_info=True,
            )
            # Attempt cleanup
            try:
                safe_delete_dir(target_path, safeguard_file=node_safeguard_file)
                # Remove from logger if it was added
                node_store.del_entry(node.uuid)
            except Exception as cleanup_e:
                logger.error(
                    f"Failed cleanup for node {node.pk} at {target_path.name}: {cleanup_e}"
                )

    @staticmethod
    def _generate_child_node_label(
        index: int, link_triple: LinkTriple, append_pk: bool = True
    ) -> str:
        """Generate clean directory label for child nodes during recursion, using LinkType enum."""
        node = link_triple.node
        link_label = link_triple.link_label

        # Start with index if applicable
        label_parts = [f"{index:02d}"] if index > 0 else []

        # Add the cleaned label only if it's not empty
        if link_label not in (
            "CALL_CALC",
            "CALL_WORK",
            "RETURN",
            "INPUT_CALC",
            "INPUT_WORK",
            "CREATE",
            "CALL",
        ):
            label_parts.append(link_label)

        # Add process_label or process_type if different and informative
        process_label = getattr(node, "process_label", None)
        process_type = getattr(node, "process_type", None)

        added_extra_label = False
        # Add process_label if it's different from the *original* link label AND the *cleaned* one
        # And also if it's not empty
        if process_label and process_label != link_label:
            label_parts.append(process_label)
            added_extra_label = True
        elif not added_extra_label and process_type is not None:
            # Add cleaned type only if it provides new info compared to link/cleaned label
            cleaned_type = (
                process_type.split(".")[-1]
                .replace("Calculation", "")
                .replace("WorkChain", "")
            )
            if cleaned_type:
                label_parts.append(cleaned_type)

        # Add PK
        if append_pk:
            label_parts.append(str(node.pk))

        # Join non-empty parts
        node_label = "-".join(filter(None, label_parts))

        # Handle cases where label might be empty after all cleaning -> Does this ever occurr?
        if not node_label:
            node_label = f"{node.__class__.__name__}-{node.pk}"

        return node_label


###
# from __future__ import annotations

# import os
# from typing import TYPE_CHECKING

# from aiida import orm
# from aiida.common.log import AIIDA_LOGGER
# from aiida.common.progress_reporter import get_progress_reporter, set_progress_bar_tqdm
# from aiida.tools.dumping.entities.process import (
#     ProcessDumper,
#     NodeMetadataWriter,
#     NodeRepoIoDumper,
#     WorkflowWalker,
#     ReadmeGenerator,
# )
# from aiida.tools.dumping.utils.paths import (
#     DumpPaths,
#     generate_process_default_dump_path,
#     safe_delete_dir,
# )
# from aiida.tools.dumping.utils.types import DumpStoreKeys

# if TYPE_CHECKING:
#     from aiida.tools.dumping.config import DumpConfig
#     from aiida.tools.dumping.logger import DumpLogger
#     from aiida.tools.dumping.managers.group import GroupManager
#     from aiida.tools.dumping.utils.time import DumpTimes
#     from aiida.tools.dumping.utils.types import DumpNodeStore

# logger = AIIDA_LOGGER.getChild("tools.dumping.managers.node")


# class NodeManager:
#     """Handles the processing and dumping of individual nodes"""

#     def __init__(
#         self,
#         config: DumpConfig,
#         dump_paths: DumpPaths,
#         dump_logger: DumpLogger,
#         dump_times: DumpTimes,
#         group_manager: GroupManager,
#     ):
#         self.config: DumpConfig = config
#         self.dump_paths: DumpPaths = dump_paths
#         self.dump_logger: DumpLogger = dump_logger
#         self.dump_times: DumpTimes = dump_times
#         self.group_manager: GroupManager = group_manager

#         # Instantiate helper classes
#         self.metadata_writer = NodeMetadataWriter(config)
#         self.repo_io_dumper = NodeRepoIoDumper(config)
#         # Pass the bound method self.dump_process for recursion
#         self.workflow_walker = WorkflowWalker(self.dump_process)
#         self.readme_generator = ReadmeGenerator()

#     # Could unify that for `processes` in general
#     # def dump_nodes(self, node_store: DumpNodeStore, group: orm.Group | None = None):
#     #     """Dump a collection of nodes from a node store within an optional group context."""

#     #     set_progress_bar_tqdm() # Initialize progress bar style

#     #     nodes_to_dump = []
#     #     # Combine calculations and workflows for unified progress bar
#     #     nodes_to_dump.extend(node_store.calculations)
#     #     nodes_to_dump.extend(node_store.workflows)
#     #     # Add data nodes if applicable
#     #     # nodes_to_dump.extend(node_store.data)

#     #     if not nodes_to_dump:
#     #          return # Nothing to dump

#     #     desc = f'Dumping {len(nodes_to_dump)} nodes'
#     #     if group:
#     #         desc += f" for group '{group.label}'"

#     #     with get_progress_reporter()(desc=desc, total=len(nodes_to_dump)) as progress:
#     #         for node in nodes_to_dump:
#     #             try:
#     #                 self.dump_process(node, group) # Changed method name to be generic 'node'
#     #             except Exception as e:
#     #                  # Log error but continue with other nodes
#     #                  logger.error(f"Failed to dump node PK={node.pk} (UUID={node.uuid}): {e}", exc_info=True)
#     #             finally:
#     #                  progress.update() # Ensure progress bar updates even on error

#     def dump_nodes(self, node_store: DumpNodeStore, group=None):
#         """Dump a collection of nodes from a node store"""

#         set_progress_bar_tqdm()

#         for process_type in ("calculations", "workflows"):
#             processes = getattr(node_store, process_type)
#             if processes:
#                 with get_progress_reporter()(
#                     desc=f"Dumping {process_type}", total=len(processes)
#                 ) as progress:
#                     for process in processes:
#                         self.dump_process(process, group)
#                         progress.update()

#     def dump_process(self, process, group=None):
#         """Dump a single process, placing it correctly based on group context and config."""
#         node = process

#         # --- Determine the correct parent path for the node's type subdirectory ---
#         # if group and self.config.organize_by_groups:
#         if self.config.organize_by_groups:
#             # === Grouped & Organized Path ===
#             # get_group_path ensures .../groups/group_label exists
#             group_base_path = self.group_manager.prepare_group_path(group)
#             if isinstance(node, orm.CalculationNode):
#                 type_subdir = "calculations"
#             elif isinstance(node, orm.WorkflowNode):
#                 type_subdir = "workflows"
#             else:
#                 type_subdir = "unknown"
#             # Place type subdir inside the group's base path
#             node_parent_path = group_base_path / type_subdir
#         else:
#             # === Flat or Ungrouped Path ===
#             # Place type subdir directly under the main dump root
#             if isinstance(node, orm.CalculationNode):
#                 type_subdir = "calculations"
#             elif isinstance(node, orm.WorkflowNode):
#                 type_subdir = "workflows"
#             else:
#                 type_subdir = "unknown"
#             node_parent_path = self.dump_paths.absolute / type_subdir

#         # Ensure the determined parent path exists (e.g., .../groups/group/calculations OR .../calculations)
#         node_parent_path.mkdir(parents=True, exist_ok=True)

#         # --- Determine the final path for this specific node's directory ---
#         process_name = generate_process_default_dump_path(process)
#         process_path = node_parent_path / process_name

#         # --- Check Logging & Symlinking ---
#         store_key = DumpStoreKeys.from_instance(node_inst=node)
#         existing_log_entry = self.dump_logger.get_store_by_name(store_key).get_entry(
#             node.uuid
#         )

#         if existing_log_entry:
#             # Handle symlinking or skipping if already logged
#             # ... (Symlink/Skip logic from previous step - check if path exists before symlinking) ...
#             if (
#                 self.config.symlink_calcs
#                 and isinstance(node, orm.CalculationNode)
#                 and group
#             ):
#                 target_path = existing_log_entry.path
#                 link_path = process_path  # Where the link *should* be placed
#                 if link_path.exists() or link_path.is_symlink():
#                     logger.debug(
#                         f"Path {link_path} already exists, skipping symlink for node {node.pk}."
#                     )
#                     return
#                 try:
#                     os.symlink(target_path, link_path, target_is_directory=True)
#                     logger.debug(f"Created symlink {link_path} -> {target_path}")
#                     # Optionally update log with symlink info here
#                     return  # Don't proceed
#                 except OSError as e:
#                     logger.error(
#                         f"Failed symlink creation for node {node.pk} at {link_path}: {e}"
#                     )
#                     return  # Skip on error
#         #  else:
#         #       logger.debug(f"Node {node.pk} already logged at {existing_log_entry.path}, skipping dump.")
#         #       return # Skip dumping

#         # --- Dump the node ---
#         process_config = self.config.get_process_config()
#         dump_mode = self.config.dump_mode
#         try:
#             process_dumper = ProcessDumper(
#                 process_node=node,
#                 # Pass the CORRECT final path wrapped in DumpPaths
#                 dump_paths=DumpPaths.from_path(process_path),
#                 dump_logger=self.dump_logger,
#                 dump_times=self.dump_times,  # Pass times instance
#                 config=process_config,
#                 dump_mode=dump_mode,
#             )
#             process_dumper.dump(top_level_caller=False)
#             logger.debug(f"Successfully dumped node {node.pk} to {process_path}")
#         except Exception as e:
#             logger.error(
#                 f"Failed during dump of node PK={node.pk} (UUID={node.uuid}): {e}",
#                 exc_info=True,
#             )
#             # Optional cleanup
#             try:
#                 # Use metadata file as safeguard for node deletion cleanup
#                 safe_delete_dir(process_path, ".aiida_node_metadata.yaml")
#             except Exception as cleanup_e:
#                 logger.error(
#                     f"Failed to cleanup directory {process_path} after dump error: {cleanup_e}"
#                 )

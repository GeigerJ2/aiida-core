from __future__ import annotations

import os
from enum import Enum, auto
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Tuple

from aiida import orm
from aiida.common.log import AIIDA_LOGGER
from aiida.common.progress_reporter import get_progress_reporter, set_progress_bar_tqdm
from aiida.orm.utils import LinkTriple
from aiida.tools.dumping.logger import DumpLog
from aiida.tools.dumping.utils.paths import (
    DumpPaths,
    generate_process_default_dump_path,
    get_directory_stats,
    prepare_dump_path,
    safe_delete_dir,
)
from aiida.tools.dumping.utils.process_handlers import (
    NodeMetadataWriter,
    NodeRepoIoDumper,
    ReadmeGenerator,
    WorkflowWalker,
)
from aiida.tools.dumping.utils.types import DumpStoreKeys

if TYPE_CHECKING:
    from aiida.tools.dumping.config import DumpConfig
    from aiida.tools.dumping.engine import DumpEngine
    from aiida.tools.dumping.logger import DumpLogger
    from aiida.tools.dumping.managers.group import GroupManager
    from aiida.tools.dumping.utils.time import DumpTimes
    from aiida.tools.dumping.utils.types import DumpNodeStore

logger = AIIDA_LOGGER.getChild('tools.dumping.managers.node')


class NodeDumpAction(Enum):
    """Represents the action determined after checking the log."""

    SKIP = auto()
    SYMLINKED = auto()
    DUMP_PRIMARY = auto()
    DUMP_DUPLICATE = auto()
    ERROR = auto()


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
        # Pass the bound method self._dump_process_recursive_entry for recursion
        self.workflow_walker = WorkflowWalker(self._dump_process_recursive_entry)
        self.readme_generator = ReadmeGenerator()

    # --- Public Methods ---

    def dump_nodes(self, node_store: DumpNodeStore, group: orm.Group | None = None):
        """Dump a collection of nodes from a node store within an optional group context."""
        set_progress_bar_tqdm()
        nodes_to_dump = []
        nodes_to_dump.extend(node_store.calculations)
        nodes_to_dump.extend(node_store.workflows)
        if not nodes_to_dump:
            return
        desc = f'Dumping {len(nodes_to_dump)} nodes'
        if group:
            desc += f" for group '{group.label}'"
        with get_progress_reporter()(desc=desc, total=len(nodes_to_dump)) as progress:
            for node in nodes_to_dump:
                try:
                    node_base_path = self._get_node_base_path(node, group)
                    # Call the main entry point for dumping a single process
                    self.dump_process(node, node_base_path, group)
                except Exception as e:
                    logger.error(
                        f'Failed preparing/dumping node PK={node.pk}: {e}',
                        exc_info=True,
                    )
                finally:
                    progress.update()

    def dump_process(
        self,
        process_node: orm.ProcessNode,
        target_path: Path,
        group: orm.Group | None = None,
    ):
        """
        Main entry point to dump a single ProcessNode.
        Handles validation, logging checks, symlinking, duplicate dumping, and cleanup.
        """
        logger.debug(f'Starting dump process for node {process_node.pk} -> {target_path.name}')

        # 1. Validate Node
        if not self._validate_node_for_dump(process_node):
            return  # Validation failed, logged inside helper

        # 2. Check Log and Determine Action
        action, existing_log_entry = self._check_log_and_determine_action(
            process_node, target_path, group, is_child_call=False
        )

        if action == NodeDumpAction.SKIP:
            logger.debug(f'Skipping node {process_node.pk} (already logged/exists at target).')
            return
        if action == NodeDumpAction.SYMLINKED:
            logger.debug(f'Symlinked node {process_node.pk} to target {target_path.name}.')
            return
        if action == NodeDumpAction.ERROR:
            logger.error(
                f'Error during log check/symlink attempt for node {process_node.pk}. Aborting dump for this node.'
            )
            return

        # 3. Proceed with Full Dump (Primary or Duplicate)
        is_primary_dump = action == NodeDumpAction.DUMP_PRIMARY
        log_entry_to_update = None  # Will be set if dump succeeds

        try:
            # 3a. Prepare Directory
            node_safeguard_file = DumpPaths.safeguard_file
            self._prepare_node_dump_directory(target_path, node_safeguard_file)

            # 3b. Create/Update Log Entry (Before Content Dump)
            # Need the entry object for potential stat updates later
            log_entry_to_update = self._prepare_log_entry(
                process_node, target_path, existing_log_entry, is_primary_dump
            )
            if log_entry_to_update is None and not is_primary_dump:  # Error if duplicate dump has no original entry
                raise RuntimeError(
                    f'Log entry inconsistency: No existing entry found for duplicate dump of node {process_node.pk}.'
                )

            # 3c. Dump Content (Metadata, Repo, Children)
            self._dump_node_content(process_node, target_path, group, node_safeguard_file)

            # 3d. Calculate and Update Stats (on success)
            if log_entry_to_update:
                path_to_stat = existing_log_entry.path if not is_primary_dump and existing_log_entry else target_path
                self._calculate_and_update_stats(process_node.pk, path_to_stat, log_entry_to_update)
            else:
                logger.warning(f'Log entry to update was None after dumping node {process_node.pk}. Stats not updated.')

        except Exception as e:
            logger.error(
                f'Failed during content dump of node PK={process_node.pk} at {target_path}: {e}',
                exc_info=True,
            )
            # 3e. Cleanup on Failure
            self._cleanup_failed_dump(process_node, target_path, node_safeguard_file, is_primary_dump)

    # --- Private Helper Methods ---

    def _dump_process_recursive_entry(
        self,
        process_node: orm.ProcessNode,
        target_path: Path,
        group: orm.Group | None = None,
    ):
        """Entry point for recursive calls from WorkflowWalker."""
        logger.debug(f'Recursive dump call for child node {process_node.pk} -> {target_path.name}')

        # 1. Validate Node
        if not self._validate_node_for_dump(process_node):
            return

        # 2. Check Log and Determine Action (Mark as child call implicitly)
        action, existing_log_entry = self._check_log_and_determine_action(
            process_node, target_path, group, is_child_call=True
        )

        # Handle SKIP, SYMLINKED, ERROR as in the main method
        if action == NodeDumpAction.SKIP:
            return
        if action == NodeDumpAction.SYMLINKED:
            return
        if action == NodeDumpAction.ERROR:
            return

        # 3. Proceed with Full Dump (Primary or Duplicate)
        is_primary_dump = action == NodeDumpAction.DUMP_PRIMARY
        log_entry_to_update = None
        try:
            node_safeguard_file = DumpPaths.safeguard_file
            self._prepare_node_dump_directory(target_path, node_safeguard_file)

            log_entry_to_update = self._prepare_log_entry(
                process_node, target_path, existing_log_entry, is_primary_dump
            )
            if log_entry_to_update is None and not is_primary_dump:
                raise RuntimeError(
                    f'Log entry inconsistency: No existing entry for duplicate child dump of node {process_node.pk}.'
                )

            self._dump_node_content(process_node, target_path, group, node_safeguard_file)

            if log_entry_to_update:
                path_to_stat = existing_log_entry.path if not is_primary_dump and existing_log_entry else target_path
                self._calculate_and_update_stats(process_node.pk, path_to_stat, log_entry_to_update)
            else:
                logger.warning(f'Log entry was None after dumping child node {process_node.pk}. Stats not updated.')

        except Exception as e:
            logger.error(
                f'Failed during recursive dump of node PK={process_node.pk} at {target_path}: {e}',
                exc_info=True,
            )
            self._cleanup_failed_dump(process_node, target_path, node_safeguard_file, is_primary_dump)

    def _validate_node_for_dump(self, node: orm.ProcessNode) -> bool:
        """Checks if the node is valid for dumping (Original Logic)."""
        if not node.is_sealed and not self.config.dump_unsealed:
            # Original code raised ExportValidationError - keeping this behavior if desired
            # raise ExportValidationError(
            #     f'Process `{node.pk}` must be sealed before it can be dumped, or `--dump-unsealed` set to True.'
            # )
            # Alternatively, just log and return False as in previous refactor:
            logger.error(f'Process `{node.pk}` must be sealed before dumping, or use --dump-unsealed.')
            return False
        return True

    def _check_log_and_determine_action(
        self,
        node: orm.ProcessNode,
        target_path: Path,
        group: orm.Group | None,
        is_child_call: bool,
    ) -> Tuple[NodeDumpAction, Optional[DumpLog]]:
        """
        Checks the logger, handles symlinks, and determines the action (Original Logic).
        """
        store_key = DumpStoreKeys.from_instance(node)
        node_store = self.dump_logger.get_store_by_name(store_key)
        existing_log_entry = node_store.get_entry(node.uuid)

        if not existing_log_entry:
            # Original behavior: If not logged, it's a primary dump
            return NodeDumpAction.DUMP_PRIMARY, None

        # --- Node is already logged ---
        logger.debug(f'Node {node.pk} already logged at {existing_log_entry.path.name}')

        # Check symlink condition (Original Logic from provided code)
        # Symlink CalculationNodes ONLY IF configured AND in Profile/Group context AND NOT a direct workflow child.
        should_symlink = (
            self.config.symlink_calcs
            and isinstance(node, orm.CalculationNode)
            # Check for Profile/Group context dump (group is not None)
            and group is not None
            # Avoid symlink for direct workflow children (original condition)
            # and not is_child_call # Keeping this commented as per user finding
            # Symlinks only make sense if the target path is different
            and target_path.resolve() != existing_log_entry.path.resolve()
        )

        if should_symlink:
            logger.debug(f'Attempting symlink for node {node.pk} -> {target_path.name}')
            # Original code implicitly skipped if target existed, mimicking that
            if target_path.exists() or target_path.is_symlink():
                logger.debug(f'Path {target_path.name} exists, skipping symlink for node {node.pk}.')
                # Original code would just return, effectively skipping
                return NodeDumpAction.SKIP, existing_log_entry
            try:
                source_path = existing_log_entry.path
                if not source_path.exists():
                    logger.warning(f'Source path {source_path} for node {node.pk} does not exist. Cannot symlink.')
                    # Original code didn't explicitly handle this, likely resulting in OSError below.
                    # We'll mimic failing the symlink attempt.
                    return NodeDumpAction.ERROR, existing_log_entry  # Treat as error
                os.symlink(source_path, target_path, target_is_directory=True)
                logger.debug(f'Created symlink {target_path.name} -> {source_path.name}')
                # Record the symlink in the *original* log entry
                existing_log_entry.add_symlink(target_path.resolve())
                # Log needs saving later
                return NodeDumpAction.SYMLINKED, existing_log_entry
            except OSError as e:
                logger.error(f'Failed symlink creation for node {node.pk} at {target_path.name}: {e}')
                # Original code didn't explicitly handle symlink failure, it would likely proceed or error later.
                # Returning ERROR to prevent proceeding seems safest.
                return NodeDumpAction.ERROR, existing_log_entry

        # --- Symlinking not applicable or failed ---

        # Original logic check: if target path is same as original, skip
        if target_path.resolve() == existing_log_entry.path.resolve():
            logger.debug(f'Node {node.pk} already logged at the exact target path {target_path.name}, skipping.')
            return NodeDumpAction.SKIP, existing_log_entry
        else:
            # Original logic: Path is different -> dump as a full duplicate.
            logger.info(f'Node {node.pk} already logged, creating duplicate dump at {target_path.name}')
            return NodeDumpAction.DUMP_DUPLICATE, existing_log_entry

    def _prepare_node_dump_directory(self, target_path: Path, safeguard_file: str):
        # """Prepares the target directory for dumping (Original Logic)."""
        logger.debug(f'Preparing dump directory: {target_path.name}')
        try:
            # Calling the utility function as in the original code
            prepare_dump_path(
                path_to_validate=target_path,
                dump_mode=self.config.dump_mode,
                safeguard_file=safeguard_file,  # Original used DumpPaths.safeguard_file
                top_level_caller=False,
            )
            # Original code touched the safeguard file after preparation
            (target_path / safeguard_file).touch(exist_ok=True)
            logger.debug(f'Directory {target_path.name} prepared successfully.')
        except Exception as e:
            logger.error(
                f'Failed preparing target path {target_path.name}: {e}',
                exc_info=True,
            )
            raise  # Re-raise to be caught by the main dump_process try-except

    def _prepare_log_entry(
        self, node: orm.ProcessNode, target_path: Path, existing_entry: Optional[DumpLog], is_primary_dump: bool
    ) -> Optional[DumpLog]:
        """Creates or updates the log entry before dumping content (Original Logic)."""
        log_entry_to_update = None
        if is_primary_dump:
            # Original code created entry here
            new_entry = DumpLog(path=target_path.resolve())
            store_key = DumpStoreKeys.from_instance(node)
            node_store = self.dump_logger.get_store_by_name(store_key)
            node_store.add_entry(node.uuid, new_entry)
            log_entry_to_update = new_entry
            logger.debug(f'Created primary log entry for node {node.pk}')
        elif existing_entry:
            # Original code added path to duplicates list here
            existing_entry.add_duplicate(target_path.resolve())
            log_entry_to_update = existing_entry  # Will update stats on the original
            logger.debug(f'Added duplicate path {target_path.name} to log for node {node.pk}')
        # No else needed, error handled in calling function if existing_entry is None for duplicate

        return log_entry_to_update

    def _dump_node_content(
        self, node: orm.ProcessNode, target_path: Path, group: orm.Group | None, safeguard_file: str
    ):
        """Dumps the actual content (metadata, repo, children) (Original Logic)."""
        logger.debug(f'Dumping content for node {node.pk} into {target_path.name}')

        # 1. Write Metadata (Original Logic)
        self.metadata_writer.write(node, target_path)
        logger.debug(f'Metadata written for node {node.pk}')

        # 2. Ensure top-level safeguard exists (Original Logic)
        (target_path / DumpPaths.safeguard_file).touch(exist_ok=True)

        # 3. Dump Repo/IO or Recurse Children (Original Logic)
        if isinstance(node, orm.CalculationNode):
            self.repo_io_dumper.dump_calculation_content(node, target_path)
            logger.debug(f'Calculation content dumped for node {node.pk}')
        elif isinstance(node, orm.WorkflowNode):
            # WorkflowWalker calls _dump_process_recursive_entry
            # Pass group context as potentially needed by recursive calls for symlink check
            self.workflow_walker.dump_children(node, target_path)  # Must ensure walker passes group context
            logger.debug(f'Workflow children dumped for node {node.pk}')

    def _calculate_and_update_stats(self, node_pk: int, path_to_stat: Path, log_entry: DumpLog):
        """Calculates directory stats and updates the log entry (Original Logic)."""
        logger.debug(f'Calculating stats for node {node_pk} directory: {path_to_stat.name}')
        try:
            # Calling the utility as in original code
            dir_mtime, dir_size = get_directory_stats(path_to_stat)
            log_entry.dir_mtime = dir_mtime
            log_entry.dir_size = dir_size
            logger.debug(f'Updated stats for node {node_pk}: mtime={dir_mtime}, size={dir_size} bytes')
        except Exception as e:
            # Original code didn't explicitly catch errors here, but added logging is good
            logger.warning(f'Could not calculate/update stats for node {node_pk} at {path_to_stat}: {e}')

    def _cleanup_failed_dump(
        self, node: orm.ProcessNode, target_path: Path, safeguard_file: str, is_primary_dump: bool
    ):
        """Cleans up directory and potentially log entry on failure (Original Logic)."""
        logger.warning(f'Attempting cleanup for failed dump of node {node.pk} at {target_path.name}')
        try:
            # Calling the utility as in original code
            # safe_delete_dir(target_path, safeguard_file=safeguard_file)
            logger.info(f'Cleaned up directory {target_path.name} for failed node {node.pk}')

            # Original code removed from logger ONLY if it was the primary dump attempt
            if is_primary_dump:
                store_key = DumpStoreKeys.from_instance(node)
                node_store = self.dump_logger.get_store_by_name(store_key)
                if node_store.del_entry(node.uuid):
                    logger.info(f'Removed log entry for failed primary dump of node {node.pk}')
                else:
                    logger.warning(f'Could not find log entry to remove for failed primary dump of node {node.pk}')

        except Exception as cleanup_e:
            logger.error(f'Failed during cleanup for node {node.pk} at {target_path.name}: {cleanup_e}', exc_info=True)

    # --- Path Calculation (Original Logic) ---
    def _get_node_base_path(self, node: orm.Node, group: orm.Group | None) -> Path:
        """Determine the correct base directory path for dumping a specific node."""
        # group_base_path = self.group_manager.prepare_group_path(group)
        group_base_path = self.group_manager.get_group_path(group)

        if isinstance(node, orm.CalculationNode):
            type_subdir = 'calculations'
        elif isinstance(node, orm.WorkflowNode):
            type_subdir = 'workflows'
        elif isinstance(node, orm.Data):
            type_subdir = 'data'
        else:
            type_subdir = 'unknown'

        if self.config.organize_by_groups:
            # If organizing by groups, place inside the type subdir within the group path
            node_parent_path = group_base_path / type_subdir
        else:
            # Flat structure: place inside the type subdir directly under the main dump path
            node_parent_path = self.dump_paths.absolute / type_subdir

        node_parent_path.mkdir(parents=True, exist_ok=True)

        # Generate the specific node directory name
        node_directory_name: Path = self._generate_node_directory_name(node)
        final_node_path = node_parent_path / node_directory_name

        logger.debug(f'Determined final path for node {node.pk}: {final_node_path}')
        return final_node_path

    # --- Static Helpers (Original Logic) ---
    @staticmethod
    def _generate_node_directory_name(node: orm.ProcessNode, append_pk: bool = True) -> Path:
        """Generates the directory name for a specific node."""
        # Calling the utility function as in the original code
        return generate_process_default_dump_path(node, append_pk=append_pk)

    @staticmethod
    def _generate_child_node_label(index: int, link_triple: LinkTriple, append_pk: bool = True) -> str:
        """Generate clean directory label for child nodes during recursion (Original Logic)."""
        # IMPORTANT: Keeping the exact logic from the originally provided file
        node = link_triple.node
        link_label = link_triple.link_label

        # Generate directories with naming scheme akin to `verdi process status`
        label_list = [f'{index:02d}', link_label]

        try:
            process_label = node.process_label
            if process_label is not None and process_label != link_label:
                label_list += [process_label]

        except AttributeError:
            process_type = node.process_type
            if process_type is not None and process_type != link_label:
                label_list += [process_type]

        if append_pk:
            label_list += [str(node.pk)]

        node_label = '-'.join(label_list)
        # `CALL-` as part of the link labels also for MultiplyAddWorkChain -> Seems general enough, so remove
        node_label = node_label.replace('CALL-', '')
        # Original code had this replacement
        return node_label.replace('None-', '')


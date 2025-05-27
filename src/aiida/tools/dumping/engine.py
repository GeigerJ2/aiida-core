"""Dump engine with full integration of existing complex logic."""

from __future__ import annotations

from functools import cached_property
from pathlib import Path
from typing import Union

from aiida import orm
from aiida.common import AIIDA_LOGGER
from aiida.manage.configuration.profile import Profile
from aiida.tools.dumping.config import DumpConfig, DumpMode
from aiida.tools.dumping.content import ContentGenerator
from aiida.tools.dumping.detect import DumpChangeDetector
from aiida.tools.dumping.dumper import NodeDumper
from aiida.tools.dumping.executors import DeletionExecutor
from aiida.tools.dumping.executors.simple import GroupProcessor, ProfileProcessor
from aiida.tools.dumping.filesystem import FileSystemManager
from aiida.tools.dumping.mapping import GroupNodeMapping
from aiida.tools.dumping.paths import PathResolver
from aiida.tools.dumping.planner import DumpPlanner
from aiida.tools.dumping.tracking import DumpTracker
from aiida.tools.dumping.utils import DumpChanges, DumpPaths, DumpTimes, ProcessingQueue

logger = AIIDA_LOGGER.getChild('tools.dumping.engine')


class DumpEngine:
    """Engine that orchestrates the dump process with full existing logic integration."""

    def __init__(
        self,
        dump_target_entity: Union[orm.ProcessNode, orm.Group, Profile],
        base_output_path: Path,
        config: DumpConfig | None = None,
    ):
        """Engine constructor that initializes all entities needed for dumping."""

        self.config: DumpConfig = config or DumpConfig()
        self.dump_target_entity = dump_target_entity
        self.base_path = base_output_path.resolve()

        # Initialize traditional dump paths (still needed for some components)
        self.dump_paths = DumpPaths(
            base_output_path=self.base_path,
            config=self.config,
            dump_target_entity=dump_target_entity,
        )

        # Prepare directory and load tracker (existing logic)
        self.fs_manager = FileSystemManager(self.config)
        self.fs_manager.prepare_directory(path=self.base_path)

        self.dump_tracker = DumpTracker.load(self.dump_paths)
        self.dump_times = DumpTimes.from_last_log_time(self.dump_tracker._last_dump_time_str)
        # Initialize new architecture components
        self.path_resolver = PathResolver(self.config, self.base_path)
        self.content_generator = ContentGenerator(self.config)
        self.planner = DumpPlanner(self.config, self.dump_tracker)

        # Initialize change detector (existing logic)
        self.detector = DumpChangeDetector(
            dump_tracker=self.dump_tracker, dump_paths=self.dump_paths, config=self.config, dump_times=self.dump_times
        )

        # Initialize main node dumper
        self.node_dumper = NodeDumper(
            self.planner, self.fs_manager, self.content_generator, self.path_resolver, self.dump_tracker
        )

        # Initialize processors
        self.group_processor = GroupProcessor(self.node_dumper, self.fs_manager, self.path_resolver)
        self.profile_processor = ProfileProcessor(self.group_processor)

    @cached_property
    def current_mapping(self) -> GroupNodeMapping:
        """Build and cache the current group-node mapping from the database."""
        return GroupNodeMapping.build_from_db()

    def _log_dump_start(self) -> None:
        """Log the start of a dump operation."""
        dump_start_report = ''
        if isinstance(self.dump_target_entity, orm.ProcessNode):
            dump_start_report = f'process node (PK: {self.dump_target_entity.pk})'
        elif isinstance(self.dump_target_entity, orm.Group):
            dump_start_report = f'group `{self.dump_target_entity.label}` (PK: {self.dump_target_entity.pk})'
        elif isinstance(self.dump_target_entity, Profile):
            dump_start_report = f'profile `{self.dump_target_entity.name}`'

        msg = f'Starting dump of {dump_start_report} in {self.config.dump_mode.name.lower()} mode.'
        if self.config.dump_mode != DumpMode.DRY_RUN:
            logger.report(msg)

    def dump(self) -> None:
        """Selects and executes the appropriate dump strategy."""
        self._log_dump_start()

        # Call appropriate helper method
        if isinstance(self.dump_target_entity, orm.ProcessNode):
            self._dump_process()
        elif isinstance(self.dump_target_entity, orm.Group):
            self._dump_group()
        elif isinstance(self.dump_target_entity, Profile):
            self._dump_profile()

        # Save final dump log (existing logic)
        if isinstance(self.dump_target_entity, (orm.Group, Profile)):
            current_mapping = self.current_mapping
        else:
            current_mapping = None

        logger.report(f'Saving final dump log to file `{DumpPaths.TRACKING_LOG_FILE_NAME}`.')
        self.dump_tracker.save(current_dump_time=self.dump_times.current, group_node_mapping=current_mapping)

    def _dump_process(self) -> None:
        """Dump a single ProcessNode using new architecture."""
        assert isinstance(self.dump_target_entity, orm.ProcessNode)

        # Use new node dumper
        self.node_dumper.dump_node(self.dump_target_entity, self.base_path)

        # Generate README (existing logic)
        self._generate_readme(self.dump_target_entity, self.base_path)

    def _dump_group(self) -> None:
        """Dump a group using existing detection logic + new architecture."""
        assert isinstance(self.dump_target_entity, orm.Group)

        # Use existing change detection logic
        node_changes = self.detector._detect_node_changes(group=self.dump_target_entity)
        group_changes = self.detector._detect_group_changes(
            previous_mapping=self.dump_tracker.group_node_mapping,
            current_mapping=self.current_mapping,
            specific_group_uuid=self.dump_target_entity.uuid,
        )
        all_changes = DumpChanges(nodes=node_changes, groups=group_changes)

        if self.config.dump_mode == DumpMode.DRY_RUN:
            print(all_changes.to_table())
            return

        # Handle deletions (existing logic)
        if self.config.delete_missing:
            deletion_manager = DeletionExecutor(
                config=self.config,
                dump_paths=self.dump_paths,
                dump_tracker=self.dump_tracker,
                dump_changes=all_changes,
                previous_mapping=self.dump_tracker.group_node_mapping,
            )
            deletion_manager._handle_deleted_entities()

        # Process group using new architecture but with detected changes
        nodes = self._convert_processing_queue_to_node_collections(node_changes.new_or_modified)
        if not nodes.is_empty():
            self.group_processor.process_group(self.dump_target_entity, nodes)

        # Handle group lifecycle changes (existing logic integration)
        self._handle_group_lifecycle_changes(group_changes)

    def _dump_profile(self) -> None:
        """Dump a profile using existing detection logic + new architecture."""
        assert isinstance(self.dump_target_entity, Profile)

        if not self.config.all_entries and not self.config.filters_set:
            self.dump_paths.safe_delete_directory(path=self.dump_paths.base_output_path)
            return

        # Use existing change detection logic
        node_changes = self.detector._detect_node_changes()
        group_changes = self.detector._detect_group_changes(
            previous_mapping=self.dump_tracker.group_node_mapping, current_mapping=self.current_mapping
        )
        all_changes = DumpChanges(nodes=node_changes, groups=group_changes)

        if all_changes.is_empty():
            logger.report('No changes detected since last dump and not dumping ungrouped. Nothing to do.')
            return

        if self.config.dump_mode == DumpMode.DRY_RUN:
            print(all_changes.to_table())
            return

        # Handle deletions (existing logic)
        if self.config.delete_missing:
            deletion_manager = DeletionExecutor(
                config=self.config,
                dump_paths=self.dump_paths,
                dump_tracker=self.dump_tracker,
                dump_changes=all_changes,
                previous_mapping=self.dump_tracker.group_node_mapping,
            )
            deletion_manager._handle_deleted_entities()

        # Handle group lifecycle changes (existing logic)
        self._handle_group_lifecycle_changes(group_changes)

        # Process groups using new architecture
        groups_and_nodes = self._determine_groups_and_nodes_to_process(node_changes)
        self.profile_processor.process_profile(groups_and_nodes)

        # Process ungrouped nodes (existing logic integration)
        if self.config.also_ungrouped:
            self._process_ungrouped_nodes()

    def _determine_groups_and_nodes_to_process(self, node_changes) -> list[tuple[orm.Group, ProcessingQueue]]:
        """Determine which groups to process using existing logic."""
        groups_to_process = []

        if self.config.all_entries:
            qb = orm.QueryBuilder().append(orm.Group)
            all_groups = qb.all(flat=True)
        elif self.config.groups:
            group_identifiers = self.config.groups
            if all(isinstance(identifier, orm.Group) for identifier in group_identifiers):
                all_groups = group_identifiers
            else:
                try:
                    all_groups = [orm.load_group(identifier=str(gid)) for gid in group_identifiers]
                except Exception as e:
                    logger.error(f'Error loading specified group: {e}. Aborting group processing.')
                    return []
        else:
            all_groups = []

        # For each group, determine what nodes need processing
        for group in all_groups:
            nodes = self._get_nodes_for_group_from_changes(group, node_changes)
            if not nodes.is_empty():
                groups_to_process.append((group, nodes))

        return groups_to_process

    def _get_nodes_for_group_from_changes(self, group: orm.Group, node_changes) -> ProcessingQueue:
        """Get nodes for a specific group from detected changes."""
        group_node_uuids = {node.uuid for node in group.nodes}

        # Filter detected changes to only include nodes in this group
        calc_nodes = [n for n in node_changes.new_or_modified.calculations if n.uuid in group_node_uuids]
        workflow_nodes = [n for n in node_changes.new_or_modified.workflows if n.uuid in group_node_uuids]

        return ProcessingQueue(calc_nodes, workflow_nodes)

    def _handle_group_lifecycle_changes(self, group_changes):
        """Handle group lifecycle changes using existing logic."""
        if not (group_changes.modified or group_changes.renamed or group_changes.node_membership):
            return

        logger.report('Processing group changes...')

        # Handle deleted groups
        if group_changes.deleted:
            group_labels = [group_info.label for group_info in group_changes.deleted]
            logger.report(f'Detected {len(group_changes.deleted)} deleted groups.')

        # Handle new groups
        if group_changes.new:
            group_labels = [group_info.label for group_info in group_changes.new]
            logger.report(f'Processing {len(group_changes.new)} new groups: {group_labels}')

        # Handle renamed groups (existing logic)
        if self.config.relabel_groups and group_changes.renamed:
            logger.report(f'Processing {len(group_changes.renamed)} renamed groups...')
            for rename_info in group_changes.renamed:
                self._handle_group_rename(rename_info)

        # Handle modified groups (membership changes)
        if group_changes.modified:
            group_labels = [group_info.label for group_info in group_changes.modified]
            logger.report(f'Processing {len(group_changes.modified)} modified groups: {group_labels}')
            for mod_info in group_changes.modified:
                self._handle_group_membership_change(mod_info)

    def _handle_group_rename(self, rename_info):
        """Handle group rename using existing logic."""
        old_path = rename_info.old_path
        new_path = rename_info.new_path

        if old_path.exists():
            try:
                new_path.parent.mkdir(parents=True, exist_ok=True)
                import os

                os.rename(old_path, new_path)
                logger.info(f"Renamed directory '{old_path}' to '{new_path}'")
            except OSError as e:
                logger.error(f'Failed to rename directory for group {rename_info.uuid}: {e}')
                return

        # Update tracker paths
        self.dump_tracker.update_paths(old_base_path=old_path, new_base_path=new_path)

    def _handle_group_membership_change(self, mod_info):
        """Handle group membership changes."""
        group = orm.load_group(uuid=mod_info.uuid)
        group_path = self.path_resolver.get_group_path(group)

        # Handle added nodes
        for node_uuid in mod_info.nodes_added:
            try:
                node = orm.load_node(uuid=node_uuid)
                if isinstance(node, orm.ProcessNode):
                    node_path = self.path_resolver.get_node_path(node, group_path)
                    self.node_dumper.dump_node(node, node_path)
            except Exception:
                continue

        # Handle removed nodes (existing logic would be complex to integrate)
        # For now, rely on deletion handling in DeletionExecutor

    def _process_ungrouped_nodes(self) -> None:
        """Process ungrouped nodes using existing logic."""
        if not self.config.also_ungrouped:
            return

        # Use existing detector logic
        ungrouped_nodes = self.detector.get_ungrouped_nodes()
        nodes_to_dump = ProcessingQueue()
        ungrouped_path = self.path_resolver.get_ungrouped_path()

        # Check against existing representations (simplified version)
        for node in ungrouped_nodes.calculations:
            if not self._has_ungrouped_representation(node, ungrouped_path):
                nodes_to_dump.calculations.append(node)

        for node in ungrouped_nodes.workflows:
            if not self._has_ungrouped_representation(node, ungrouped_path):
                nodes_to_dump.workflows.append(node)

        if not nodes_to_dump.is_empty():
            logger.report(f'Dumping {len(nodes_to_dump)} nodes under ungrouped path...')
            self.fs_manager.prepare_directory(ungrouped_path)

            for node in nodes_to_dump.all_process_nodes():
                node_path = self.path_resolver.get_node_path(node, ungrouped_path)
                self.node_dumper.dump_node(node, node_path)

    def _has_ungrouped_representation(self, node: orm.ProcessNode, ungrouped_path: Path) -> bool:
        """Check if node already has representation under ungrouped path."""
        dump_record = self.dump_tracker.get_entry(node.uuid)
        if not dump_record:
            return False

        try:
            # Check primary path
            if dump_record.path.exists() and dump_record.path.resolve().is_relative_to(ungrouped_path.resolve()):
                return True

            # Check symlinks and duplicates
            for path in dump_record.symlinks + dump_record.duplicates:
                if path.exists() and path.resolve().is_relative_to(ungrouped_path.resolve()):
                    return True
        except (OSError, ValueError):
            pass

        return False

    def _generate_readme(self, process_node: orm.ProcessNode, output_path: Path) -> None:
        """Generate README using existing logic."""
        import textwrap

        from aiida.cmdline.utils.ascii_vis import format_call_graph
        from aiida.cmdline.utils.common import (
            get_calcjob_report,
            get_process_function_report,
            get_workchain_report,
        )

        pk = process_node.pk
        readme_content = textwrap.dedent(f"""\
            # AiiDA Process Dump: {process_node.process_label or process_node.process_type} <{pk}>

            This directory contains files related to the AiiDA process node {pk}.
            - **UUID:** {process_node.uuid}
            - **Type:** {process_node.node_type}
            """)

        readme_content += f'\n## Process Status\n\n```\n{format_call_graph(process_node)}\n```\n'

        if isinstance(process_node, orm.CalcJobNode):
            report = get_calcjob_report(process_node)
        elif isinstance(process_node, orm.WorkChainNode):
            report = get_workchain_report(node=process_node, levelname='REPORT', indent_size=2, max_depth=None)
        elif isinstance(process_node, (orm.CalcFunctionNode, orm.WorkFunctionNode)):
            report = get_process_function_report(process_node)
        else:
            report = 'N/A'

        readme_content += f'\n## Process Report\n\n```\n{report}\n```\n'

        (output_path / 'README.md').write_text(readme_content, encoding='utf-8')

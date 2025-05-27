"""Main node dumping orchestrator."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from aiida import orm
from aiida.common import LinkType
from aiida.tools.dumping.core import DumpAction
from aiida.tools.dumping.tracking import DumpRecord

if TYPE_CHECKING:
    from aiida.tools.dumping.content import ContentGenerator
    from aiida.tools.dumping.filesystem import FileSystemManager
    from aiida.tools.dumping.paths import PathResolver
    from aiida.tools.dumping.planner import DumpPlanner
    from aiida.tools.dumping.tracking import DumpTracker


class NodeDumper:
    """Orchestrates node dumping operations."""

    def __init__(
        self,
        planner: 'DumpPlanner',
        fs_manager: 'FileSystemManager',
        content_generator: 'ContentGenerator',
        path_resolver: 'PathResolver',
        tracker: 'DumpTracker',
    ):
        self.planner = planner
        self.fs_manager = fs_manager
        self.content_generator = content_generator
        self.path_resolver = path_resolver
        self.tracker = tracker

    def dump_node(self, node: orm.ProcessNode, target_path: Path) -> None:
        """Dump a single node."""
        plan = self.planner.plan_node_dump(node, target_path)

        if plan.action == DumpAction.SKIP:
            return

        elif plan.action == DumpAction.DUMP_PRIMARY:
            self._execute_primary_dump(node, plan)

        elif plan.action == DumpAction.UPDATE:
            self._execute_update(node, plan)

        elif plan.action == DumpAction.SYMLINK:
            self._execute_symlink(node, plan)

        elif plan.action == DumpAction.DUMP_DUPLICATE:
            self._execute_duplicate_dump(node, plan)

    def _execute_primary_dump(self, node: orm.ProcessNode, plan) -> None:
        """Execute primary dump."""
        self.fs_manager.prepare_directory(plan.target_path, is_leaf_node_dir=True)

        # Create tracker record
        record = DumpRecord(path=plan.target_path.resolve())
        self.tracker.registries[plan.registry_name].add_entry(node.uuid, record)

        # Generate content
        self.content_generator.generate_all_content(node, plan.target_path)

        # Handle workflow children
        if isinstance(node, orm.WorkflowNode):
            self._dump_workflow_children(node, plan.target_path)

        # Update stats
        record.update_stats_from_path(plan.target_path)

    def _execute_update(self, node: orm.ProcessNode, plan) -> None:
        """Execute update dump."""
        self.fs_manager.delete_directory(plan.target_path)
        self.fs_manager.prepare_directory(plan.target_path, is_leaf_node_dir=True)

        # Generate content
        self.content_generator.generate_all_content(node, plan.target_path)

        # Handle workflow children
        if isinstance(node, orm.WorkflowNode):
            self._dump_workflow_children(node, plan.target_path)

        # Update stats
        plan.existing_record.update_stats_from_path(plan.target_path)

    def _execute_symlink(self, node: orm.ProcessNode, plan) -> None:
        """Execute symlink creation."""
        self.fs_manager.create_symlink(plan.existing_record.path, plan.target_path)
        plan.existing_record.add_symlink(plan.target_path.resolve())

    def _execute_duplicate_dump(self, node: orm.ProcessNode, plan) -> None:
        """Execute duplicate dump."""
        self.fs_manager.prepare_directory(plan.target_path, is_leaf_node_dir=True)

        # Add to duplicates
        plan.existing_record.add_duplicate(plan.target_path.resolve())

        # Generate content
        self.content_generator.generate_all_content(node, plan.target_path)

        # Handle workflow children
        if isinstance(node, orm.WorkflowNode):
            self._dump_workflow_children(node, plan.target_path)

    def _dump_workflow_children(self, workflow: orm.WorkflowNode, output_path: Path) -> None:
        """Dump children of a workflow."""
        called_links = workflow.base.links.get_outgoing(link_type=(LinkType.CALL_CALC, LinkType.CALL_WORK)).all()
        called_links = sorted(called_links, key=lambda link_triple: link_triple.node.ctime)

        for index, link_triple in enumerate(called_links, start=1):
            child_node = link_triple.node
            child_label = self._generate_child_label(index, link_triple)
            child_path = output_path / child_label

            if isinstance(child_node, orm.ProcessNode):
                self.dump_node(child_node, child_path)

    def _generate_child_label(self, index: int, link_triple) -> str:
        """Generate label for child node."""
        node = link_triple.node
        link_label = link_triple.link_label

        label_parts = [f'{index:02d}', link_label]

        try:
            if hasattr(node, 'process_label') and node.process_label and node.process_label != link_label:
                label_parts.append(node.process_label)
        except AttributeError:
            if hasattr(node, 'process_type') and node.process_type and node.process_type != link_label:
                label_parts.append(node.process_type)

        label_parts.append(str(node.pk))

        node_label = '-'.join(label_parts)
        node_label = node_label.replace('CALL-', '')
        return node_label.replace('None-', '')

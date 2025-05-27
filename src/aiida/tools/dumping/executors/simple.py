"""Simplified executors using the new architecture."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aiida import orm
from aiida.tools.dumping.utils import ProcessingQueue

if TYPE_CHECKING:
    from aiida.tools.dumping.dumper import NodeDumper
    from aiida.tools.dumping.filesystem import FileSystemManager
    from aiida.tools.dumping.paths import PathResolver


class GroupProcessor:
    """Simple group processor."""

    def __init__(self, node_dumper: 'NodeDumper', fs_manager: 'FileSystemManager', path_resolver: 'PathResolver'):
        self.node_dumper = node_dumper
        self.fs_manager = fs_manager
        self.path_resolver = path_resolver

    def process_group(self, group: orm.Group, nodes: ProcessingQueue) -> None:
        """Process nodes for a group."""
        group_path = self.path_resolver.get_group_path(group)
        self.fs_manager.prepare_directory(group_path, is_leaf_node_dir=False)

        for node in nodes.calculations:
            node_path = self.path_resolver.get_node_path(node, group_path)
            self.node_dumper.dump_node(node, node_path)

        for node in nodes.workflows:
            node_path = self.path_resolver.get_node_path(node, group_path)
            self.node_dumper.dump_node(node, node_path)


class ProfileProcessor:
    """Simple profile processor."""

    def __init__(self, group_processor: GroupProcessor):
        self.group_processor = group_processor

    def process_profile(self, groups_and_nodes: dict[orm.Group, ProcessingQueue]) -> None:
        """Process profile by processing each group."""
        for group, nodes in groups_and_nodes.items():
            if not nodes.is_empty():
                self.group_processor.process_group(group, nodes)

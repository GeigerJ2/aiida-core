"""Path resolution for dumps."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from aiida import orm

if TYPE_CHECKING:
    from aiida.tools.dumping.config import DumpConfig


class PathResolver:
    """Handles path resolution for dumps."""

    def __init__(self, config: 'DumpConfig', base_path: Path):
        self.config = config
        self.base_path = base_path

    def get_group_path(self, group: orm.Group) -> Path:
        """Get path for a group."""
        if not self.config.organize_by_groups:
            return self.base_path
        return self.base_path / 'groups' / group.label

    def get_node_path(self, node: orm.ProcessNode, parent_path: Path) -> Path:
        """Get path for a node within a parent directory."""
        type_dir = 'calculations' if isinstance(node, orm.CalculationNode) else 'workflows'
        node_name = self._get_node_directory_name(node)
        return parent_path / type_dir / node_name

    def get_ungrouped_path(self) -> Path:
        """Get path for ungrouped nodes."""
        if self.config.also_ungrouped and self.config.organize_by_groups:
            return self.base_path / 'ungrouped'
        return self.base_path

    def _get_node_directory_name(self, node: orm.ProcessNode) -> str:
        """Generate directory name for a node."""
        parts = []

        if node.label:
            parts.append(node.label)
        elif node.process_label:
            parts.append(node.process_label)
        elif node.process_type:
            parts.append(node.process_type)

        parts.append(str(node.pk))
        return '-'.join(parts)

"""Business logic for determining dump actions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aiida import orm
from aiida.common import LinkType, timezone
from aiida.tools.dumping.core import DumpAction, NodeDumpPlan

if TYPE_CHECKING:
    from pathlib import Path

    from aiida.tools.dumping.config import DumpConfig
    from aiida.tools.dumping.tracking import DumpRecord, DumpTracker


class DumpPlanner:
    """Determines what actions to take for dumps."""

    def __init__(self, config: 'DumpConfig', tracker: 'DumpTracker'):
        self.config = config
        self.tracker = tracker

    def plan_node_dump(self, node: orm.ProcessNode, target_path: 'Path') -> NodeDumpPlan:
        """Determine action for dumping a node."""
        registry_name = self._get_registry_name(node)
        existing_record = self.tracker.get_entry(node.uuid)

        if not existing_record:
            return NodeDumpPlan(action=DumpAction.DUMP_PRIMARY, target_path=target_path, registry_name=registry_name)

        resolved_target = target_path.resolve()
        resolved_logged = existing_record.path.resolve()

        # Same path - check if update needed
        if resolved_target == resolved_logged:
            if self._needs_update(node, existing_record):
                return NodeDumpPlan(
                    action=DumpAction.UPDATE,
                    target_path=target_path,
                    registry_name=registry_name,
                    existing_record=existing_record,
                )
            else:
                return NodeDumpPlan(
                    action=DumpAction.SKIP,
                    target_path=target_path,
                    registry_name=registry_name,
                    existing_record=existing_record,
                )

        # Different path - determine symlink vs duplicate
        is_calc = isinstance(node, orm.CalculationNode)
        is_sub_process = len(node.base.links.get_incoming(link_type=(LinkType.CALL_CALC, LinkType.CALL_WORK)).all()) > 0

        if self.config.symlink_calcs and is_calc:
            action = DumpAction.SYMLINK
        elif is_calc and is_sub_process and not self.config.only_top_level_calcs:
            action = DumpAction.DUMP_DUPLICATE
        else:
            action = DumpAction.DUMP_DUPLICATE

        return NodeDumpPlan(
            action=action, target_path=target_path, registry_name=registry_name, existing_record=existing_record
        )

    def _needs_update(self, node: orm.ProcessNode, record: 'DumpRecord') -> bool:
        """Check if node needs updating."""
        if record.dir_mtime is None:
            return True

        node_mtime = node.mtime.astimezone(timezone.utc)
        logged_mtime = record.dir_mtime.astimezone(timezone.utc)
        return node_mtime > logged_mtime

    def _get_registry_name(self, node: orm.ProcessNode) -> str:
        """Get registry name for node type."""
        if isinstance(node, orm.CalculationNode):
            return 'calculations'
        elif isinstance(node, orm.WorkflowNode):
            return 'workflows'
        else:
            raise ValueError(f'Unknown node type: {type(node)}')

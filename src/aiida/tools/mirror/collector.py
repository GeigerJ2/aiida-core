###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################
"""Class to collect nodes for mirror feature."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, ClassVar, Dict, Type

from aiida import orm
from aiida.common.log import AIIDA_LOGGER
from aiida.tools.mirror.config import NodeCollectorConfig, NodeMirrorGroupScope, MirrorTimes
from aiida.tools.mirror.logger import MirrorLogger
from aiida.tools.mirror.utils import NodeMirrorKeyMapper

logger = AIIDA_LOGGER.getChild('tools.mirror.collector')

# TODO: Limit to only sealed nodes


__all__ = ('MirrorNodeContainer', 'MirrorNodeCollector')


@dataclass
class MirrorNodeContainer:
    calculations: list['orm.CalculationNode'] = field(default_factory=list)
    workflows: list['orm.WorkflowNode'] = field(default_factory=list)
    data: list['orm.Data'] = field(default_factory=list)

    @property
    def should_mirror_processes(self) -> bool:
        return len(self.calculations) > 0 or len(self.workflows) > 0

    @property
    def should_mirror_data(self) -> bool:
        return len(self.data) > 0

    def __len__(self) -> int:
        return len(self.calculations) + len(self.workflows) + len(self.data)

    def num_processes(self) -> int:
        return len(self.calculations) + len(self.workflows)

    def add_nodes(self, node_type: Type, nodes: list) -> None:
        attr = NodeMirrorKeyMapper.get_key_from_class(node_type)
        setattr(self, attr, nodes)

    def is_empty(self) -> bool:
        return len(self) == 0


class MirrorNodeCollector:
    def __init__(
        self,
        mirror_logger: MirrorLogger,
        mirror_times: MirrorTimes,
        config: NodeCollectorConfig | None = None,
    ):
        self.mirror_logger = mirror_logger
        self.mirror_times = mirror_times
        self.config = config or NodeCollectorConfig()

    def collect_to_mirror(self, group: orm.Group | None = None, filters: dict | None = None) -> MirrorNodeContainer:
        msg = 'Collecting nodes from the database. For the first mirror, this can take a while.'
        logger.report(msg)

        container = MirrorNodeContainer()

        if self.config.get_processes:
            # Get workflow nodes
            workflows = self.get_nodes(
                orm.WorkflowNode, group=group, top_level_only=self.config.only_top_level_workflows, filters=filters
            )
            container.workflows = workflows

            # Get calculation nodes
            calculations = self.get_nodes(
                orm.CalculationNode, group=group, top_level_only=self.config.only_top_level_calcs, filters=filters
            )

            # If not using top-level-only filter, add descendant calculations from workflows
            if not self.config.only_top_level_calcs and workflows:
                descendant_calcs = self._get_workflow_descendants(workflows)
                # Combine and remove duplicates
                calculations = list(set(calculations + descendant_calcs))

            container.calculations = calculations

        if self.config.get_data:
            msg = 'Mirroring of data nodes not implemented yet.'
            raise NotImplementedError(msg)

            # # Get data nodes
            # try:
            #     data_nodes = self._get_nodes('data', group=group, scope=self.config.group_scope, filters=filters)

            #     container.data = data_nodes
            # except NotImplementedError:
            #     # Keep the existing behavior
            #     msg = 'Mirroring of data nodes not yet implemented.'
            #     raise NotImplementedError(msg)

        self.mirror_container = container

        return container

    def collect_to_delete(
        self,
        mirror_logger: MirrorLogger,
        group: orm.Group | None = None,
    ) -> MirrorNodeContainer:
        # for orm_class in (orm.CalculationNode, orm.WorkflowNode):  # orm.Data
        #     store = getattr(self.mirror_logger, NodeMirrorKeyMapper.get_key_from_class(orm_class=orm_class))

        # TODO: Currently, the

        # profile_container = self.mirror_container or self.collect_to_mirror()

        # NOTE: Wouldn't have to create the empty one here, if the argument wasn't required
        empty_mirror_logger = MirrorLogger(mirror_paths=mirror_logger.mirror_paths)
        to_mirror_container = self.collect_to_mirror(empty_mirror_logger)

        # import ipdb; ipdb.set_trace()

        logged_container = MirrorNodeContainer(
            calculations=[orm.load_node(n) for n in mirror_logger.calculations.entries.keys()],
            workflows=[orm.load_node(n) for n in mirror_logger.workflows.entries.keys()],
            data=[orm.load_node(n) for n in mirror_logger.data.entries.keys()],
        )

        to_delete_container = MirrorNodeContainer(
            calculations=[n for n in logged_container.calculations if n not in to_mirror_container.calculations],
            workflows=[n for n in logged_container.workflows if n not in to_mirror_container.workflows],
            data=[n for n in logged_container.data if n not in to_mirror_container.data],
        )

        return to_delete_container

        # if self.config.include_processes:
        #     calculations = orm.QueryBuilder().append(orm.CalculationNode).all(flat=True)
        #     workflows = orm.QueryBuilder().append(orm.WorkflowNode).all(flat=True)
        #     profile_container.calculations = calculations
        #     profile_container.workflows = workflows

        #     logger_container.calculations = list(mirror_logger.calculations.entries.keys())
        #     logger_container.workflows = list(mirror_logger.workflows.entries.keys())

        # if self.config.include_data:
        #     data = orm.QueryBuilder().append(orm.WorkflowNode).all(flat=True)
        #     profile_container.data = data

        #     logger_container.data = list(mirror_logger.data.entries.keys())

        # import ipdb

        # ipdb.set_trace()

    def _resolve_filters(self, orm_class: orm.CalculationNode | orm.WorkflowNode | orm.Data) -> Dict[str, Any]:
        filters = {}
        orm_key = NodeMirrorKeyMapper.get_key_from_class(orm_class=orm_class)

        # This might be too annoying to log always, and raising here would require manually setting
        # `filter-by-last-mirror-time` to False for the first mirror
        if self.config.filter_by_last_mirror_time and not self.mirror_times.last:
            msg = 'Cannot filter by last mirror time if no last mirror time available. Will not filter nodes by time.'
            logger.debug(msg)

        # Filter by modification time if requested
        elif self.config.filter_by_last_mirror_time and self.mirror_times.last:
            filters['mtime'] = {'>=': self.mirror_times.last.astimezone()}

        # Filter out already logged nodes if mirror_logger is available
        # NOTE: Move this outside and make it depend on the passing of the store???
        # if self.mirror_logger and hasattr(self.mirror_logger, orm_key):
        store = getattr(self.mirror_logger, orm_key)
        if len(store) > 0:
            filters['uuid'] = {'!in': list(store.entries.keys())}

        return filters

    def get_nodes(
        self, orm_type: orm.Node, group: 'orm.Group' = None, top_level_only: bool = False, filters: dict | None = None
    ) -> list['orm.Node']:
        # Basic filters for the query
        if not filters:
            filters = self._resolve_filters(orm_type)

        # Build query based on scope
        if self.config.group_scope == NodeMirrorGroupScope.IN_GROUP:
            if group is None:
                raise ValueError('Group must be provided when scope is IN_GROUP')
            nodes = self._query_group_nodes(orm_type, group, filters)

            # Extend "group" nodes to descendants
            if not self.config.only_top_level_calcs:
                descendant_nodes = []
                for node in nodes:
                    if isinstance(node, orm.WorkflowNode):
                        descendant_nodes.extend(
                            [n for n in node.called_descendants if isinstance(n, orm.CalculationNode)]
                        )
                # import ipdb; ipdb.set_trace()
                nodes += descendant_nodes

            # Extend "group" nodes to descendants
            if not self.config.only_top_level_workflows:
                descendant_nodes = []
                for node in nodes:
                    if isinstance(node, orm.ProcessNode):
                        descendant_nodes.extend([n for n in node.called_descendants if isinstance(n, orm.WorkflowNode)])
                # import ipdb; ipdb.set_trace()
                nodes += descendant_nodes

        elif self.config.group_scope == NodeMirrorGroupScope.ANY:
            nodes = self._query_all_nodes(orm_type, filters)

        elif self.config.group_scope == NodeMirrorGroupScope.NO_GROUP:
            nodes = self._query_no_group_nodes(orm_type, filters)

        else:
            raise ValueError('Unknown scope: ')

        # Apply top-level filtering if requested
        if top_level_only:
            nodes = [node for node in nodes if node.caller is None]

        return nodes

    def _query_group_nodes(
        self, orm_type: orm.Node, group: 'orm.Group', filters: Dict[str, Any] = {}
    ) -> list['orm.Node']:
        qb = orm.QueryBuilder()
        qb.append(orm.Group, filters={'id': group.id}, tag='group')
        qb.append(orm_type, filters=filters, with_group='group', tag='node')
        return qb.all(flat=True)

    def _query_all_nodes(self, orm_type: orm.Node, filters: Dict[str, Any]) -> list['orm.Node']:
        qb = orm.QueryBuilder()
        qb.append(orm_type, filters=filters, tag='node')
        return qb.all(flat=True)

    def _query_no_group_nodes(self, orm_type: orm.Node, filters: Dict[str, Any]) -> list['orm.Node']:
        # First get all nodes
        all_nodes = self._query_all_nodes(orm_type, filters)

        # Then get all nodes that are in groups
        qb = orm.QueryBuilder()
        qb.append(orm.Group, tag='group')
        qb.append(orm_type, with_group='group', tag='node')
        grouped_nodes = qb.all(flat=True)

        # Also include descendant nodes of process nodes
        descendant_nodes = []
        for node in grouped_nodes:
            if isinstance(node, orm.ProcessNode):
                descendant_nodes.extend(node.called_descendants)

        # Combine and convert to a set for efficient membership checking
        all_grouped_nodes = set(grouped_nodes + descendant_nodes)

        # Return only nodes that are not in any group
        return [node for node in all_nodes if node not in all_grouped_nodes]

    def _get_workflow_descendants(self, workflows: list['orm.WorkflowNode']) -> list[orm.Node]:
        descendants = []
        for workflow in workflows:
            for node in workflow.called_descendants:
                if isinstance(node, orm.CalculationNode):
                    descendants.append(node)
        return descendants

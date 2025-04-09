###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################
"""Class to collect nodes for mirror feature."""

from __future__ import annotations

from typing import Any, Dict

from aiida import orm
from aiida.common.log import AIIDA_LOGGER
from aiida.tools.mirror.config import (
    MirrorCollectorConfig,
    MirrorStoreKeys,
    NodeMirrorGroupScope,
)
from aiida.tools.mirror.logger import MirrorLogger
from aiida.tools.mirror.store import MirrorNodeStore
from aiida.tools.mirror.utils import QbMirrorEntityType

logger = AIIDA_LOGGER.getChild('tools.mirror.collector')

# TODO: Limit to only sealed nodes. This option is currently accessible for `verdi process mirror`, but it is not a
# generally exposed option


__all__ = ('MirrorCollector',)


class MirrorCollector:
    def __init__(
        self,
        mirror_logger: MirrorLogger,
        config: MirrorCollectorConfig | None = None,
    ):
        self.mirror_logger = mirror_logger
        self.config = config or MirrorCollectorConfig()

    def collect_to_mirror(self, group: orm.Group | None = None, filters: dict | None = None) -> MirrorNodeStore:
        if group:
            msg = f'Collecting nodes from the database for group `{group.label}`.'
        else:
            msg = 'Collecting ungrouped nodes from the database.'

        logger.report(msg)

        mirror_times = self.mirror_logger.mirror_times
        if mirror_times.last is None:
            msg = 'For the first mirror, this can take a while.'
            logger.report(msg)

        node_store = MirrorNodeStore()

        if self.config.get_processes:
            # Get workflow nodes
            workflows = self.get_nodes(
                orm.WorkflowNode,
                group=group,
                top_level_only=self.config.only_top_level_workflows,
                filters=filters,
            )
            node_store.workflows = workflows

            # Get calculation nodes
            calculations = self.get_nodes(
                orm.CalculationNode,
                group=group,
                top_level_only=self.config.only_top_level_calcs,
                filters=filters,
            )

            # If not using top-level-only filter, add descendant calculations from workflows
            if not workflows and self.config.only_top_level_calcs:
                descendant_calcs = self._get_workflow_descendant_calcs(workflows)
                # Combine and remove duplicates
                calculations = list(set(calculations + descendant_calcs))

            node_store.calculations = calculations

        if self.config.get_data:
            msg = 'Mirroring of data nodes not implemented yet.'
            raise NotImplementedError(msg)

        # import ipdb; ipdb.set_trace()

        return node_store

    def collect_to_delete(self) -> MirrorNodeStore:
        """ """
        delete_node_container = MirrorNodeStore()

        for orm_type in (orm.CalculationNode, orm.WorkflowNode, orm.Data, orm.Group):
            store_name = MirrorStoreKeys.from_class(orm_class=orm_type)
            mirror_store = getattr(self.mirror_logger, store_name)
            mirrored_uuids = set(mirror_store.entries.keys())
            qb = orm.QueryBuilder()
            # if group:
            #     qb.append(orm.Group, filters={'id': group.id}, tag='group')
            #     qb.append(orm_type, project=['uuid'], with_group='group')
            # else:
            qb.append(orm_type, project=['uuid'])

            db_uuids = set(qb.all(flat=True))
            # Ensure that the nodes were _actually_ already mirrored in the past
            db_uuids = set([db_uuid for db_uuid in db_uuids if db_uuid in mirrored_uuids])
            to_delete_uuids = mirrored_uuids - db_uuids
            setattr(delete_node_container, store_name, to_delete_uuids)

        return delete_node_container

    def _resolve_filters(self, orm_class: QbMirrorEntityType) -> Dict[str, Any]:
        filters: Dict[str, Any] = {}
        orm_key = MirrorStoreKeys.from_class(orm_class=orm_class)

        # Initialize mtime filter as a dictionary
        mtime_filter: Dict[str, Any] = {}

        # Add current mirror time as upper bound
        mtime_filter['<='] = self.mirror_logger.mirror_times.current.astimezone()

        # This might be too annoying to log always, and raising here would require manually setting
        # `filter-by-last-mirror-time` to False for the first mirror
        if self.config.filter_by_last_mirror_time and not self.mirror_logger.mirror_times.last:
            msg = 'Cannot filter by last mirror time if no last mirror time available. Will not filter nodes by time.'
            logger.debug(msg)

        # Add last mirror time as lower bound if available and configured
        elif self.config.filter_by_last_mirror_time and self.mirror_logger.mirror_times.last:
            mtime_filter['>='] = self.mirror_logger.mirror_times.last.astimezone()

        # Add the mtime filter to the main filters dictionary
        filters['mtime'] = mtime_filter

        # Filter out already logged nodes if mirror_logger is available
        store = getattr(self.mirror_logger, orm_key)
        if len(store) > 0:
            filters['uuid'] = {'!in': list(store.entries.keys())}

        return filters

    # def _resolve_filters(self, orm_class: QbMirrorEntityType) -> Dict[str, Any]:

    #     filters = {}
    #     orm_key = MirrorStoreKeys.from_class(orm_class=orm_class)

    #     # Only nodes with an `mtime` up to the current mirror time are selected.
    #     # This is to avoid unpredictable behavior on multiple runs of the command.
    #     # The current mirror time thus serves as a cutoff for the node selection
    #     filters['mtime'] = {'<=': self.mirror_logger.mirror_times.current.astimezone()}

    #     # This might be too annoying to log always, and raising here would require manually setting
    #     # `filter-by-last-mirror-time` to False for the first mirror
    #     if self.config.filter_by_last_mirror_time and not self.mirror_logger.mirror_times.last:
    #         msg = 'Cannot filter by last mirror time if no last mirror time available. Will not filter nodes by time.'
    #         logger.debug(msg)

    #     # Filter by last_mirror time
    #     elif self.config.filter_by_last_mirror_time and self.mirror_logger.mirror_times.last:
    #         filters['mtime'] = {'>=': self.mirror_logger.mirror_times.last.astimezone()}

    #     # Filter out already logged nodes if mirror_logger is available
    #     # NOTE: Move this outside and make it depend on the passing of the store???
    #     # if self.mirror_logger and hasattr(self.mirror_logger, orm_key):
    #     store = getattr(self.mirror_logger, orm_key)
    #     if len(store) > 0:
    #         filters['uuid'] = {'!in': list(store.entries.keys())}

    #     return filters

    def get_nodes(
        self,
        orm_type: QbMirrorEntityType,
        group: orm.Group | None = None,
        top_level_only: bool = False,
        filters: dict | None = None,
    ) -> list[Any]:
        # Basic filters for the query

        if not filters:
            filters = self._resolve_filters(orm_type)

        if self.config.group_scope not in (
            NodeMirrorGroupScope.IN_GROUP,
            NodeMirrorGroupScope.ANY,
            NodeMirrorGroupScope.NO_GROUP,
        ):
            msg = f'Unknown scope: {self.config.group_scope}'
            raise ValueError(msg)

        # Build query based on scope
        if self.config.group_scope == NodeMirrorGroupScope.IN_GROUP:
            if group is None:
                msg = 'Group must be provided when scope is IN_GROUP'
                raise ValueError(msg)

            nodes: list[Any] = self._query_group_nodes(orm_type, group, filters)

            # Extend "group" nodes to descendants
            if not self.config.only_top_level_calcs:
                descendant_calcs: list[orm.CalculationNode] = []
                for node in nodes:
                    if isinstance(node, orm.WorkflowNode):
                        descendant_calcs.extend(
                            [n for n in node.called_descendants if isinstance(n, orm.CalculationNode)]
                        )
                nodes += descendant_calcs

            # Extend "group" nodes to descendants
            if not self.config.only_top_level_workflows:
                descendant_wfs: list[orm.WorkflowNode] = []
                for node in nodes:
                    if isinstance(node, orm.ProcessNode):
                        descendant_wfs.extend([n for n in node.called_descendants if isinstance(n, orm.WorkflowNode)])
                nodes += descendant_wfs

        elif self.config.group_scope == NodeMirrorGroupScope.ANY:
            nodes = self._query_all_nodes(orm_type, filters)

        elif self.config.group_scope == NodeMirrorGroupScope.NO_GROUP:
            nodes = self._query_no_group_nodes(orm_type, filters)

        # Apply top-level filtering if requested
        if top_level_only:
            nodes = [node for node in nodes if node.caller is None]

        return nodes

    def _query_group_nodes(
        self, orm_class: QbMirrorEntityType, group: orm.Group, filters: Dict[str, Any] = {}
    ) -> list[Any]:
        qb = orm.QueryBuilder()
        qb.append(orm.Group, filters={'id': group.id}, tag='group')
        qb.append(orm_class, filters=filters, with_group='group', tag='node')
        return qb.all(flat=True)

    def _query_all_nodes(self, orm_class: QbMirrorEntityType, filters: Dict[str, Any]) -> list[Any]:
        qb = orm.QueryBuilder()
        qb.append(orm_class, filters=filters, tag='node')
        return qb.all(flat=True)

    def _query_no_group_nodes(self, orm_class: QbMirrorEntityType, filters: Dict[str, Any]) -> list[Any]:
        # First get all nodes
        all_nodes = self._query_all_nodes(orm_class, filters)

        # Then get all nodes that are in groups
        qb = orm.QueryBuilder()
        qb.append(orm.Group, tag='group')
        qb.append(orm_class, with_group='group', tag='node')
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

    # NOTE: Should this method be specific to sub-calculations, or should it also include workflows??
    def _get_workflow_descendant_calcs(self, workflows: list[orm.WorkflowNode]) -> list[orm.CalculationNode]:
        descendants: list[orm.CalculationNode] = []
        for workflow in workflows:
            for node in workflow.called_descendants:
                if isinstance(node, orm.CalculationNode):
                    descendants.append(node)
        return descendants

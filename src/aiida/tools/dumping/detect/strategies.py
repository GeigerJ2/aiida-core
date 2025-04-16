###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################
"""Class to collect nodes for dump feature."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aiida import orm
from aiida.common.log import AIIDA_LOGGER
from aiida.tools.dumping.utils.types import DumpStoreKeys

if TYPE_CHECKING:
    from aiida.tools.dumping.config import DumpConfig
    from aiida.tools.dumping.logger import DumpLogger, DumpLogStore
    from aiida.tools.dumping.utils.time import DumpTimes

logger = AIIDA_LOGGER.getChild('tools.dumping.detect.strategies')

__all__ = (
    'AnyNodeQueryStrategy',
    'GroupNodeQueryStrategy',
    'NodeQueryStrategy',
    'UngroupedNodeQueryStrategy',
)

if TYPE_CHECKING:
    pass


class NodeQueryStrategy:
    """Base strategy for querying nodes"""

    def __init__(self, dump_logger: DumpLogger, config: DumpConfig):
        self.dump_logger = dump_logger
        self.config = config

    def get_nodes(self, orm_type, dump_times: DumpTimes, filters=None):
        """Abstract method to be implemented by concrete strategies"""
        raise NotImplementedError

    def resolve_filters(
        self,
        orm_type,
        dump_times: DumpTimes,
        include_time_filter=True,
        include_uuid_filter=True,
    ):
        """Create query filters based on configuration"""
        filters = {}

        # Add time filters if requested
        if include_time_filter:
            mtime_filter = {}
            mtime_filter['<='] = dump_times.current.astimezone()

            if self.config.filter_by_last_dump_time and dump_times.last is not None:
                mtime_filter['>='] = dump_times.last.astimezone()

            filters['mtime'] = mtime_filter

        # Add UUID filter to exclude already logged nodes
        if include_uuid_filter:
            store_key = DumpStoreKeys.from_class(orm_class=orm_type)
            store: DumpLogStore = self.dump_logger.get_store_by_name(name=store_key)

            if store and len(store.entries) > 0:
                filters['uuid'] = {'!in': list(store.entries.keys())}

        return filters


class GroupNodeQueryStrategy(NodeQueryStrategy):
    """Strategy for querying nodes in a specific group"""

    def __init__(self, dump_logger: DumpLogger, config: DumpConfig, group):
        super().__init__(dump_logger, config)
        self.group = group

    def get_nodes(self, orm_type, dump_times: DumpTimes, filters=None):
        """Get nodes of specified type within this group"""
        # Check if this is a new group
        is_new_group = self.group.uuid not in self.dump_logger.groups.entries

        # Determine appropriate filters
        if filters is None:
            if is_new_group:
                # For new groups, don't filter by time or UUID to get all nodes
                resolved_filters = {}
            else:
                resolved_filters = self.resolve_filters(
                    orm_type,
                    dump_times=dump_times,
                    include_time_filter=self.config.filter_by_last_dump_time,
                    include_uuid_filter=True,
                )

        # Query the nodes
        qb = orm.QueryBuilder()
        qb.append(orm.Group, filters={'uuid': self.group.uuid}, tag='group')
        qb.append(orm_type, filters=resolved_filters, with_group='group', tag='node')

        try:
            # Returns all matching nodes found explicitly in this group
            results = qb.all(flat=True)
            logger.debug(f"GroupNodeStrategy query returned {len(results)} nodes for group '{self.group.label}'.")
            return results
        except Exception as e:
            logger.error(f"Query failed for group '{self.group.label}', type {orm_type.__name__}: {e}")
            return []


class AnyNodeQueryStrategy(NodeQueryStrategy):
    """Strategy for querying all nodes regardless of group membership"""

    def get_nodes(self, orm_type, dump_times: DumpTimes, filters=None) -> list[orm.Node]:
        """Get all nodes of specified type, applying top-level filter if needed."""
        logger.debug(f'AnyNodeStrategy: Querying all nodes of type {orm_type.__name__}')
        if filters is None:
            # Get base filters (time, UUID)
            resolved_filters = self.resolve_filters(orm_type, dump_times=dump_times)
        else:
            # Allow passing external filters if needed, though typically None is used
            resolved_filters = filters

        qb = orm.QueryBuilder()
        qb.append(orm_type, filters=resolved_filters, tag='node')

        try:
            results: list[orm.Node] = qb.all(flat=True)
            logger.debug(f'AnyNodeStrategy initial query returned {len(results)} nodes.')

            # --- Apply top-level filter AFTER query, ONLY if configured ---
            if orm_type == orm.CalculationNode and self.config.only_top_level_calcs:
                # Keep calculations that have no caller or whose caller is not a WorkflowNode
                filtered_results = [
                    calc
                    for calc in results
                    if getattr(calc, 'caller', None) is None
                    or not isinstance(getattr(calc, 'caller', None), orm.WorkflowNode)
                ]
                logger.debug(
                    f'AnyNodeStrategy applied top-level filter, returning {len(filtered_results)} calculation nodes.'
                )
                return filtered_results
            elif orm_type == orm.WorkflowNode and self.config.only_top_level_workflows:
                # Keep workflows that have no caller
                filtered_results = [wf for wf in results if getattr(wf, 'caller', None) is None]
                logger.debug(
                    f'AnyNodeStrategy applied top-level filter, returning {len(filtered_results)} workflow nodes.'
                )
                return filtered_results
            else:
                # No top-level filter needed for this type or config is False
                return results

        except Exception as e:
            logger.error(f'Query failed for all nodes of type {orm_type.__name__}: {e}', exc_info=True)
            return []


class UngroupedNodeQueryStrategy(NodeQueryStrategy):
    """Strategy for querying nodes that don't belong to any group"""


def get_nodes(self, orm_type, dump_times: DumpTimes, filters=None) -> list[orm.Node]:
    """Get nodes that don't belong to any group, applying top-level filter if needed."""
    logger.debug(f'UngroupedNodeStrategy: Querying ungrouped nodes of type {orm_type.__name__}')
    if filters is None:
        # Get base filters (time, UUID)
        resolved_filters = self.resolve_filters(orm_type, dump_times)
    else:
        resolved_filters = filters

    try:
        # --- Query directly for ungrouped nodes ---
        qb = orm.QueryBuilder()
        # Subquery to get UUIDs of all nodes of this type that ARE in ANY group
        qb_in_group = orm.QueryBuilder()
        qb_in_group.append(orm.Group, tag='g')
        qb_in_group.append(orm_type, with_group='g', project='uuid', tag='n_in_g')
        grouped_node_uuids = qb_in_group.all(flat=True)

        # Add exclusion filter for grouped nodes
        current_exclusions = set()
        # Combine with existing UUID exclusion filter if present
        if 'uuid' in resolved_filters and isinstance(resolved_filters.get('uuid'), dict):
            current_exclusions.update(resolved_filters['uuid'].get('!in', []))
        if grouped_node_uuids:
            current_exclusions.update(grouped_node_uuids)

        # Update the filter only if there are exclusions
        if current_exclusions:
            resolved_filters['uuid'] = {'!in': list(current_exclusions)}
            logger.debug(f'UngroupedNodeStrategy: Excluding {len(current_exclusions)} logged or grouped nodes.')
        # If uuid filter existed but is now empty, remove it
        elif 'uuid' in resolved_filters and not current_exclusions:
            del resolved_filters['uuid']

        # Main query for nodes matching filters (which now includes exclusion of grouped nodes)
        qb.append(orm_type, filters=resolved_filters, tag='node')
        results: list[orm.Node] = qb.all(flat=True)
        logger.debug(f'UngroupedNodeStrategy initial query returned {len(results)} nodes.')

        # --- Apply top-level filter AFTER query, ONLY if configured ---
        if orm_type == orm.CalculationNode and self.config.only_top_level_calcs:
            # Keep calculations that have no caller or whose caller is not a WorkflowNode
            filtered_results = [
                calc
                for calc in results
                if getattr(calc, 'caller', None) is None
                or not isinstance(getattr(calc, 'caller', None), orm.WorkflowNode)
            ]
            logger.debug(
                f'UngroupedNodeStrategy applied top-level filter, returning {len(filtered_results)} calculation nodes.'
            )
            return filtered_results
        elif orm_type == orm.WorkflowNode and self.config.only_top_level_workflows:
            # Keep workflows that have no caller
            filtered_results = [wf for wf in results if getattr(wf, 'caller', None) is None]
            logger.debug(
                f'UngroupedNodeStrategy applied top-level filter, returning {len(filtered_results)} workflow nodes.'
            )
            return filtered_results
        else:
            # No top-level filter needed for this type or config is False
            return results

    except Exception as e:
        logger.error(f'Query failed for ungrouped nodes of type {orm_type.__name__}: {e}', exc_info=True)
        return []

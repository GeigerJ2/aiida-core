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

logger = AIIDA_LOGGER.getChild("tools.dumping.detect.query")

__all__ = (
    "NodeQueryStrategy",
    "GroupNodeQueryStrategy",
    "UngroupedNodeQueryStrategy",
    "AnyNodeQueryStrategy",
)

if TYPE_CHECKING:
    pass


class NodeQueryStrategy:
    """Base strategy for querying nodes"""

    def __init__(self, dump_logger, config):
        self.dump_logger = dump_logger
        self.config = config

    def get_nodes(self, orm_type, filters=None):
        """Abstract method to be implemented by concrete strategies"""
        raise NotImplementedError

    def resolve_filters(
        self, orm_type, include_time_filter=True, include_uuid_filter=True
    ):
        """Create query filters based on configuration"""
        filters = {}

        # Add time filters if requested
        if include_time_filter:
            mtime_filter = {}
            mtime_filter["<="] = self.dump_logger.dump_times.current.astimezone()

            if (
                self.config.filter_by_last_dump_time
                and self.dump_logger.dump_times.last is not None
            ):
                mtime_filter[">="] = self.dump_logger.dump_times.last.astimezone()

            filters["mtime"] = mtime_filter

        # Add UUID filter to exclude already logged nodes
        if include_uuid_filter:
            store_key = DumpStoreKeys.from_class(orm_class=orm_type)
            store = getattr(self.dump_logger, store_key, None)

            if store and len(store.entries) > 0:
                filters["uuid"] = {"!in": list(store.entries.keys())}

        return filters


class GroupNodeQueryStrategy(NodeQueryStrategy):
    """Strategy for querying nodes in a specific group"""

    def __init__(self, dump_logger, config, group):
        super().__init__(dump_logger, config)
        self.group = group

    def get_nodes(self, orm_type, filters=None):
        """Get nodes of specified type within this group"""
        # Check if this is a new group
        is_new_group = self.group.uuid not in self.dump_logger.groups.entries

        # Determine appropriate filters
        if filters is None:
            if is_new_group:
                # For new groups, don't filter by time or UUID to get all nodes
                filters = {}
            else:
                filters = self.resolve_filters(orm_type)

        # Query the nodes
        qb = orm.QueryBuilder()
        qb.append(orm.Group, filters={"id": self.group.pk}, tag="group")
        qb.append(orm_type, filters=filters, with_group="group", tag="node")
        return qb.all(flat=True)


class AnyNodeQueryStrategy(NodeQueryStrategy):
    """Strategy for querying all nodes regardless of group membership"""

    def get_nodes(self, orm_type, filters=None):
        """Get all nodes of specified type"""
        if filters is None:
            filters = self.resolve_filters(orm_type)

        qb = orm.QueryBuilder()
        qb.append(orm_type, filters=filters, tag="node")
        return qb.all(flat=True)


class UngroupedNodeQueryStrategy(NodeQueryStrategy):
    """Strategy for querying nodes that don't belong to any group"""

    def get_nodes(self, orm_type, filters=None):
        """Get nodes that don't belong to any group"""
        if filters is None:
            filters = self.resolve_filters(orm_type)

        # First get all nodes
        qb = orm.QueryBuilder()
        qb.append(orm_type, filters=filters, tag="node")
        all_nodes = qb.all(flat=True)

        # Then get all nodes that are in groups
        qb = orm.QueryBuilder()
        qb.append(orm.Group, tag="group")
        qb.append(orm_type, with_group="group", tag="node")
        grouped_nodes = set(qb.all(flat=True))

        # Return only nodes that are not in any group
        return [node for node in all_nodes if node not in grouped_nodes]

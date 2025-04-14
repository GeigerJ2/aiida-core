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

from dataclasses import dataclass, field
from typing import Any

from aiida.common.log import AIIDA_LOGGER
from aiida.tools.dumping.storage.keys import DumpStoreKeys
from aiida.tools.dumping.utils.types import StoreNameType

logger = AIIDA_LOGGER.getChild('tools.dumping.collector')

# TODO: Limit to only sealed nodes
# NOTE: Not sure if this is even necessary, or I can just use lists?

__all__ = ('DumpNodeStore',)


@dataclass
class DumpNodeStore:
    """Store for nodes to be dumped.

    This class follows a similar structure to DumpLogger, making it easier
    to convert between the two.
    """

    calculations: list = field(default_factory=list)
    workflows: list = field(default_factory=list)
    data: list = field(default_factory=list)
    groups: list = field(default_factory=list)

    @property
    def stores(self) -> dict:
        """Retrieve the current state of the container as a dataclass."""
        return {
            DumpStoreKeys.CALCULATIONS.value: self.calculations,
            DumpStoreKeys.WORKFLOWS.value: self.workflows,
            DumpStoreKeys.DATA.value: self.data,
            DumpStoreKeys.GROUPS.value: self.groups,
        }

    @property
    def should_dump_processes(self) -> bool:
        return len(self.calculations) > 0 or len(self.workflows) > 0

    @property
    def should_dump_data(self) -> bool:
        return len(self.data) > 0

    def __len__(self) -> int:
        return len(self.calculations) + len(self.workflows) + len(self.data) + len(self.groups)

    def num_processes(self) -> int:
        return len(self.calculations) + len(self.workflows)

    def add_nodes(self, nodes: list, node_type: Any | None = None) -> None:
        """Add nodes to the appropriate store based on node_type.

        Args:
            node_type: The type of nodes to add (can be a class or a string identifier)
            nodes: List of nodes to add
        """
        if node_type:
            attr = DumpStoreKeys.from_class(node_type)
        elif len(nodes) > 0:
            attr = DumpStoreKeys.from_instance(nodes[0])
        else:
            raise ValueError

        store: list = getattr(self, attr)
        store.extend(nodes)

    def is_empty(self) -> bool:
        return len(self) == 0

    def get_store_by_name(self, name: StoreNameType) -> list:
        """Get the appropriate store based on node_type.

        Args:
            node_type: The type of nodes (can be a class or a string identifier)

        Returns:
            The corresponding store list
        """

        store_names = list(self.stores.keys())
        if name not in store_names:
            msg = f'Wrong key <{name}> selected. Choose one of {store_names}.'
            raise ValueError(msg)

        return getattr(self.stores, name)

    def get_store_by_type(self, node_type: Any) -> list:
        """Get the appropriate store based on node_type.

        Args:
            node_type: The type of nodes (can be a class or a string identifier)

        Returns:
            The corresponding store list
        """

        attr = DumpStoreKeys.from_class(node_type)
        return getattr(self, attr)

    # def get_store_by_instance(self, node_instance: Any) -> list: ...

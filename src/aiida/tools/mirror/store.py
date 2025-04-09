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

from dataclasses import dataclass, field
from typing import Any

from aiida.common.log import AIIDA_LOGGER
from aiida.tools.mirror.config import MirrorStoreKeys

logger = AIIDA_LOGGER.getChild('tools.mirror.collector')

# TODO: Limit to only sealed nodes
# NOTE: Not sure if this is even necessary, or I can just use lists?

__all__ = ('MirrorNodeStore',)


@dataclass
class MirrorNodeStore:
    """Store for nodes to be mirrored.

    This class follows a similar structure to MirrorLogger, making it easier
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
            'calculations': self.calculations,
            'workflows': self.workflows,
            'data': self.data,
            'groups': self.groups,
        }

    @property
    def should_mirror_processes(self) -> bool:
        return len(self.calculations) > 0 or len(self.workflows) > 0

    @property
    def should_mirror_data(self) -> bool:
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
            attr = MirrorStoreKeys.from_class(node_type)
        elif len(nodes) > 0:
            attr = MirrorStoreKeys.from_instance(nodes[0])
        else:
            raise ValueError

        store: list = getattr(self, attr)
        store.extend(nodes)

    def is_empty(self) -> bool:
        return len(self) == 0

    def get_store_by_type(self, node_type: Any) -> list:
        """Get the appropriate store based on node_type.

        Args:
            node_type: The type of nodes (can be a class or a string identifier)

        Returns:
            The corresponding store list
        """

        attr = MirrorStoreKeys.from_class(node_type)
        return getattr(self, attr)

    def get_store_by_key(self, node_type: Any) -> list:
        """Get the appropriate store based on node_type.

        Args:
            node_type: The type of nodes (can be a class or a string identifier)

        Returns:
            The corresponding store list
        """

        attr = MirrorStoreKeys.from_class(node_type)
        return getattr(self, attr)

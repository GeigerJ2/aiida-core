###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################
"""Class to collect nodes for mirror feature."""

from collections.abc import Collection
from dataclasses import dataclass, field
from typing import Any

from aiida.common.log import AIIDA_LOGGER
from aiida.tools.mirror.utils import NodeMirrorKeyMapper

logger = AIIDA_LOGGER.getChild('tools.mirror.collector')

# TODO: Limit to only sealed nodes

__all__ = ('MirrorNodeContainer',)


@dataclass
class NodeStore:
    """A store for Node entries, similar to MirrorLogStore but for orm nodes."""

    entries: list = field(default_factory=list)

    def add_entry(self, entry: Any) -> None:
        """Add a single entry to the container."""
        self.entries.append(entry)

    def add_entries(self, entries: list) -> None:
        """Add a collection of entries to the container."""
        self.entries.extend(entries)

    def del_entry(self, entry: Any) -> bool:
        """Remove a single entry."""
        if entry in self.entries:
            self.entries.remove(entry)
            return True
        return False

    def del_entries(self, entries: Collection) -> None:
        """Remove a collection of entries."""
        self.entries = [e for e in self.entries if e not in entries]

    def __len__(self) -> int:
        """Return the number of entries in the container."""
        return len(self.entries)

    def __iter__(self):
        """Iterate over all entries."""
        return iter(self.entries)


@dataclass
class NodeStoreCollection:
    """Represents the entire collection, with calculations, workflows, and data."""

    calculations: NodeStore = field(default_factory=NodeStore)
    workflows: NodeStore = field(default_factory=NodeStore)
    data: NodeStore = field(default_factory=NodeStore)
    groups: NodeStore = field(default_factory=NodeStore)


@dataclass
class MirrorNodeContainer:
    """Container for nodes to be mirrored.

    This class follows a similar structure to MirrorLogger, making it easier
    to convert between the two.
    """

    calculations: NodeStore = field(default_factory=NodeStore)
    workflows: NodeStore = field(default_factory=NodeStore)
    data: NodeStore = field(default_factory=NodeStore)
    groups: NodeStore = field(default_factory=NodeStore)

    @property
    def stores(self) -> NodeStoreCollection:
        """Retrieve the current state of the container as a dataclass."""
        return NodeStoreCollection(
            calculations=self.calculations,
            workflows=self.workflows,
            data=self.data,
            groups=self.groups,
        )

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
            attr = NodeMirrorKeyMapper.get_key_from_class(node_type)
        elif len(nodes) > 0:
            attr = NodeMirrorKeyMapper.get_key_from_instance(nodes[0])
        else:
            raise ValueError

        store = getattr(self, attr)
        store.add_entries(nodes)

    def is_empty(self) -> bool:
        return len(self) == 0

    def get_store_by_type(self, node_type: Any) -> NodeStore:
        """Get the appropriate store based on node_type.

        Args:
            node_type: The type of nodes (can be a class or a string identifier)

        Returns:
            The corresponding NodeStore
        """

        attr = NodeMirrorKeyMapper.get_key_from_class(node_type)
        return getattr(self, attr)

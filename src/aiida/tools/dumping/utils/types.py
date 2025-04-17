from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Literal, Set, Type

from aiida import orm

DumpEntityType = orm.CalculationNode | orm.WorkflowNode | orm.Data
QbDumpEntityType = Type[orm.CalculationNode] | Type[orm.WorkflowNode] | Type[orm.Data]
StoreNameType = Literal["calculations", "workflows", "groups", "data"]


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
        return (
            len(self.calculations)
            + len(self.workflows)
            + len(self.data)
            + len(self.groups)
        )

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
            msg = f"Wrong key <{name}> selected. Choose one of {store_names}."
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


@dataclass
class DeletedEntityStore:
    calculations: Set[str] = field(default_factory=set)
    workflows: Set[str] = field(default_factory=set)
    data: Set[str] = field(default_factory=set)
    groups: Set[str] = field(default_factory=set)

    def __len__(self) -> int:
        return (
            len(self.calculations)
            + len(self.workflows)
            + len(self.data)
            + len(self.groups)
        )


# --- Supporting Dataclasses for Group Changes ---
@dataclass
class GroupInfo:
    """Information about a group (typically for new or deleted groups)."""

    uuid: str
    node_count: int = 0
    # label: str | None = None # Optional: If label is needed/fetched


@dataclass
class GroupModificationInfo:
    """Information about modifications to an existing group's membership."""

    uuid: str
    label: str
    nodes_added: List[str] = field(default_factory=list)
    nodes_removed: List[str] = field(default_factory=list)


@dataclass
class NodeMembershipChange:
    """Details how a specific node's group membership changed."""

    added_to: List[str] = field(default_factory=list)
    removed_from: List[str] = field(default_factory=list)


# --- Main Dataclasses for Change Representation ---
@dataclass
class GroupChanges:
    """Holds all changes related to group lifecycle and membership."""

    deleted: List[GroupInfo] = field(default_factory=list)
    new: List[GroupInfo] = field(default_factory=list)
    modified: List[GroupModificationInfo] = field(default_factory=list)
    node_membership: Dict[str, NodeMembershipChange] = field(default_factory=dict)


@dataclass
class NodeChanges:
    """Holds changes related to individual nodes (Calc, Work, Data)."""

    # Nodes detected as new or modified enough to require dumping/redumping
    new_or_modified: DumpNodeStore = field(default_factory=DumpNodeStore)
    # UUIDs of *nodes* detected as deleted from the database
    # Note: We separate deleted nodes from deleted groups based on Option 1.
    # If you need deleted group UUIDs elsewhere (like DeletionManager),
    # they are available in GroupChangeInfo.deleted[...].uuid
    deleted: Set[str] = field(default_factory=set)


# TODO: Also write those to disk??
@dataclass
class DumpChanges:
    """Represents all detected changes for a dump cycle (Recommended Structure)."""

    nodes: NodeChanges = field(default_factory=NodeChanges)
    groups: GroupChanges = field(default_factory=GroupChanges)


class DumpStoreKeys(str, Enum):
    CALCULATIONS = "calculations"
    WORKFLOWS = "workflows"
    GROUPS = "groups"
    DATA = "data"

    @classmethod
    def from_instance(cls, node_inst: orm.Node | orm.Group) -> StoreNameType:
        if isinstance(node_inst, orm.CalculationNode):
            return cls.CALCULATIONS.value
        elif isinstance(node_inst, orm.WorkflowNode):
            return cls.WORKFLOWS.value
        elif isinstance(node_inst, orm.Data):
            return cls.DATA.value
        elif isinstance(node_inst, orm.Group):
            return cls.GROUPS.value
        else:
            msg = f"Dumping not implemented yet for node type: {type(node_inst)}"
            raise NotImplementedError(msg)

    @classmethod
    def from_class(cls, orm_class: Type) -> StoreNameType:
        if issubclass(orm_class, orm.CalculationNode):
            return cls.CALCULATIONS.value
        elif issubclass(orm_class, orm.WorkflowNode):
            return cls.WORKFLOWS.value
        elif issubclass(orm_class, orm.Data):
            return cls.DATA.value
        elif issubclass(orm_class, orm.Group):
            return cls.GROUPS.value
        else:
            msg = f"Dumping not implemented yet for node type: {orm_class}"
            raise NotImplementedError(msg)

    @classmethod
    def to_class(cls, key: "DumpStoreKeys") -> Type:
        mapping = {
            cls.CALCULATIONS: orm.CalculationNode,
            cls.WORKFLOWS: orm.WorkflowNode,
            cls.DATA: orm.Data,
            cls.GROUPS: orm.Group,
        }
        if key in mapping:
            return mapping[key]
        else:
            msg = f"No node type mapping exists for key: {key}"
            raise ValueError(msg)

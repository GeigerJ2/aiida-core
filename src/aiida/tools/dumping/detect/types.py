from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set

from aiida.tools.dumping.storage.store import DumpNodeStore, DeletedEntityStore


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
    nodes_added: List[str] = field(default_factory=list)
    nodes_removed: List[str] = field(default_factory=list)

@dataclass
class NodeMembershipChange:
    """Details how a specific node's group membership changed."""
    added_to: List[str] = field(default_factory=list)
    removed_from: List[str] = field(default_factory=list)

# --- Main Dataclasses for Change Representation ---
@dataclass
class GroupChangeInfo:
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

@dataclass
class DumpChanges:
    """Represents all detected changes for a dump cycle (Recommended Structure)."""
    nodes: NodeChanges = field(default_factory=NodeChanges)
    groups: GroupChangeInfo = field(default_factory=GroupChangeInfo)
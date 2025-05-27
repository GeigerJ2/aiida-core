"""Core interfaces and models for the dumping functionality."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Optional

from aiida.tools.dumping.tracking import DumpRecord


class DumpAction(Enum):
    SKIP = auto()
    SYMLINK = auto()
    DUMP_PRIMARY = auto()
    DUMP_DUPLICATE = auto()
    UPDATE = auto()


@dataclass
class NodeDumpPlan:
    """Plan for dumping a single node."""

    action: DumpAction
    target_path: Path
    registry_name: str
    existing_record: Optional['DumpRecord'] = None



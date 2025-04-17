from __future__ import annotations

from typing import TYPE_CHECKING

from aiida.tools.dumping.logger import DumpLogger

if TYPE_CHECKING:
    from aiida.tools.dumping.engine import DumpEngine
    from aiida.tools.dumping.utils.types import DumpChanges


class DumpStrategy:
    """Base class for different dumping strategies"""

    def __init__(
        self,
        entity,
        engine: DumpEngine,
    ):
        self.entity = entity
        self.engine: DumpEngine = engine

    # Revert to original signature
    def dump(self, changes: DumpChanges, dump_logger: DumpLogger):
        """Execute the dump strategy"""
        raise NotImplementedError

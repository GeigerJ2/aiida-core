from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aiida import orm
    from aiida.tools.dumping.engine import DumpEngine

class DumpStrategy:
    """Base class for different dumping strategies"""

    def __init__(self, engine: DumpEngine, entity):
        self.engine: DumpEngine = engine
        self.entity = entity

    # Revert to original signature
    def dump(self):
        """Execute the dump strategy"""
        raise NotImplementedError


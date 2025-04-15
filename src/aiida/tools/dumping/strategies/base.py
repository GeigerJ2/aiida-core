from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from aiida import orm
    from aiida.tools.dumping.engine import DumpEngine
    from aiida.manage.configuration.profile import Profile

class DumpStrategy:
    """Base class for different dumping strategies"""

    def __init__(self, engine, entity):
        self.engine: DumpEngine = engine
        self.entity: orm.ProcessNode | orm.Group | Profile  = entity

    def dump(self):
        """Execute the dump strategy"""
        raise NotImplementedError

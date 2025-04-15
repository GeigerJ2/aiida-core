
class DumpStrategy:
    """Base class for different dumping strategies"""

    def __init__(self, engine, entity):
        self.engine = engine
        self.entity = entity

    def dump(self):
        """Execute the dump strategy"""
        raise NotImplementedError

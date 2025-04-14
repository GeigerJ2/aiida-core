import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from aiida.common import timezone

if TYPE_CHECKING:
    from aiida.tools.dumping.utils.paths import DumpPaths

# NOTE: Should this be a singleton?
@dataclass
class DumpTimes:
    _instance = None
    # _instance: 'DumpTimes' | None = None
    last: datetime | None = None
    # Fixed time set at instantiation
    _current: datetime = field(default_factory=timezone.now)
    # start: datetime | None = field(default_factory=timezone.now)
    range_start: datetime | None = None
    range_end: datetime | None = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def current(self) -> datetime:
        """
        Returns the fixed time that was set upon instantiation of the class.
        """
        return self._current

    @classmethod
    def from_file(cls, dump_paths: 'DumpPaths') -> 'DumpTimes':
        try:
            with dump_paths.log_path.open('r', encoding='utf-8') as f:
                prev_dump_data = json.load(f)
                return cls(last=datetime.fromisoformat(prev_dump_data['last_dump_time']))
        except:
            raise

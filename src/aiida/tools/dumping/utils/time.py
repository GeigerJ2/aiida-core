# dumping/utils/time.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from aiida.common import timezone

if TYPE_CHECKING:
    pass


@dataclass
class DumpTimes:
    """Holds relevant timestamps for a dump operation."""
    # Time the current dump operation started (or object was instantiated)
    current: datetime = field(default_factory=timezone.now)
    # Time the last dump operation finished (loaded from log)
    last: datetime | None = None
    # Optional time range filters (can be set externally)
    range_start: datetime | None = None
    range_end: datetime | None = None

    @classmethod
    def from_last_log_time(cls, last_log_time: str | None) -> 'DumpTimes':
        """Create DumpTimes initializing `last` from an ISO time string."""
        last = None
        if last_log_time:
            try:
                last = datetime.fromisoformat(last_log_time)
            except ValueError:
                 # Handle potential parsing errors if necessary
                 pass # Or log a warning
        return cls(last=last)


# import json
# from dataclasses import dataclass, field
# from datetime import datetime
# from typing import TYPE_CHECKING

# from aiida.common import timezone

# if TYPE_CHECKING:
#     from aiida.tools.dumping.utils.paths import DumpPaths

# @dataclass
# class DumpTimes:
#     # _instance: 'DumpTimes' | None = None
#     last: datetime | None = None
#     # Fixed time set at instantiation
#     _current: datetime = field(default_factory=timezone.now)
#     # start: datetime | None = field(default_factory=timezone.now)
#     range_start: datetime | None = None
#     range_end: datetime | None = None

#     @property
#     def current(self) -> datetime:
#         """
#         Returns the fixed time that was set upon instantiation of the class.
#         """
#         return self._current

#     @classmethod
#     def from_file(cls, dump_paths: 'DumpPaths') -> 'DumpTimes':
#         try:
#             with dump_paths.log_path.open('r', encoding='utf-8') as f:
#                 prev_dump_data = json.load(f)
#                 return cls(last=datetime.fromisoformat(prev_dump_data['last_dump_time']))
#         except:
#             raise

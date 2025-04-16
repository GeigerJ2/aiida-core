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


###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################

"""Base class for dump classes."""

from __future__ import annotations

import json

from aiida.tools.dumping.config import DumpMode, DumpPaths, DumpTimes
from aiida.tools.dumping.logger import DumpLogger


class BaseDump:
    def __init__(
        self,
        dump_mode: DumpMode | None = None,
        dump_paths: DumpPaths | None = None,
        # dump_logger: DumpLogger | None = None,
        # dump_collector_config: DumpCollectorConfig | None = None,
    ):
        self.dump_mode = dump_mode or DumpMode.INCREMENTAL
        self.dump_paths = dump_paths or DumpPaths()
        # self.dump_logger = dump_logger
        # self.dump_collector_config = dump_collector_config or DumpCollectorConfig()

    def set_dump_logger(
        self, dump_logger: DumpLogger | None = None, top_level_caller: bool = False
    ) -> DumpLogger:
        """If in loading from file fails, e.g., due to ``overwrite``, create a new instance

        :param dump_logger: Optional existing logger instance to use
        :return: The appropriate DumpLogger instance
        """

        # FIXME: Rather than having the `top_level_caller` argument everywhere, do this as part of the `dump`
        # operation of the derived classes, rather than here in the base class

        # Use provided dump_logger if one is passed in
        if dump_logger is not None:
            return dump_logger

        if self.dump_mode == DumpMode.OVERWRITE and top_level_caller:
            return DumpLogger(dump_paths=self.dump_paths, dump_times=DumpTimes())

        # Try to load from file, fall back to new instance on failure
        # NOTE: When in overwrite mode, this file will not exist, so a new instance will be created
        try:
            return DumpLogger.from_file(dump_paths=self.dump_paths)
        except (json.JSONDecodeError, OSError):
            return DumpLogger(dump_paths=self.dump_paths, dump_times=DumpTimes())

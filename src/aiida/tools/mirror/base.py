###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################

"""Base class for mirror classes."""

from __future__ import annotations

import json

from aiida.tools.mirror.config import MirrorMode, MirrorPaths, MirrorTimes
from aiida.tools.mirror.logger import MirrorLogger


class BaseMirror:
    def __init__(
        self,
        mirror_mode: MirrorMode | None = None,
        mirror_paths: MirrorPaths | None = None,
        # mirror_logger: MirrorLogger | None = None,
        # mirror_collector_config: MirrorCollectorConfig | None = None,
    ):
        self.mirror_mode = mirror_mode or MirrorMode.INCREMENTAL
        self.mirror_paths = mirror_paths or MirrorPaths()
        # self.mirror_logger = mirror_logger
        # self.mirror_collector_config = mirror_collector_config or MirrorCollectorConfig()

    def set_mirror_logger(
        self, mirror_logger: MirrorLogger | None = None, top_level_caller: bool = False
    ) -> MirrorLogger:
        """If in loading from file fails, e.g., due to ``overwrite``, create a new instance

        :param mirror_logger: Optional existing logger instance to use
        :return: The appropriate MirrorLogger instance
        """

        # FIXME: Rather than having the `top_level_caller` argument everywhere, do this as part of the `mirror`
        # operation of the derived classes, rather than here in the base class

        # Use provided mirror_logger if one is passed in
        if mirror_logger is not None:
            return mirror_logger

        if self.mirror_mode == MirrorMode.OVERWRITE and top_level_caller:
            return MirrorLogger(mirror_paths=self.mirror_paths, mirror_times=MirrorTimes())

        # Try to load from file, fall back to new instance on failure
        # NOTE: When in overwrite mode, this file will not exist, so a new instance will be created
        try:
            return MirrorLogger.from_file(mirror_paths=self.mirror_paths)
        except (json.JSONDecodeError, OSError):
            return MirrorLogger(mirror_paths=self.mirror_paths, mirror_times=MirrorTimes())

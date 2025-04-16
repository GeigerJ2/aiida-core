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

from aiida.tools.dumping.config import DumpMode
from aiida.tools.dumping.utils.paths import DumpPaths


class BaseDumper:
    def __init__(
        self,
        dump_mode: DumpMode | None = None,
        dump_paths: DumpPaths | None = None,
    ):
        self.dump_mode = dump_mode or DumpMode.INCREMENTAL
        self.dump_paths = dump_paths or DumpPaths()

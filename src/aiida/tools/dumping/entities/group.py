###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################
"""Functionality for dumping of a Collection of AiiDA ORM entities."""

from __future__ import annotations

from pathlib import Path

from aiida import orm
from aiida.common.exceptions import NotExistent
from aiida.common.log import AIIDA_LOGGER
from aiida.tools.dumping.config import DumpConfig
from aiida.tools.dumping.engine import DumpEngine
from aiida.tools.dumping.utils.paths import (
    DumpPaths,
    generate_group_default_dump_path,
)

logger = AIIDA_LOGGER.getChild('tools.dumping.entities.group')


# NOTE: `load_dump_logger` could be put in general Parent cparent class
# NOTE: Accessing via `group.nodes` might be nice, keep in mind
# NOTE: Should the `dump_logger` even be passed as an argument???
# TODO: Don't update the logger with the UUID of a symlinked calculation as keys must be unique
# TODO: Possibly add another `symlink` attribute to `DumpLog` which can hold a list of symlinks
# TODO: Ignore for now, as I would need to retrieve the list of links, append to it, and assign again
# TODO: Only allow for "pure" sequences of Calculation- or WorkflowNodes, or also mixed?
# TODO: If the latter possibly also have directory creation in the loop


class GroupDumper:
    """Dumps data in an AiiDA group."""

    def __init__(self, group, config=None, dump_paths=None):
        self.group = self._load_group(group)
        self.config = config or DumpConfig()

        if dump_paths is None:
            default_path = generate_group_default_dump_path(self.group)
            self.dump_paths = DumpPaths(parent=Path.cwd(), child=default_path)
        else:
            self.dump_paths = dump_paths

        self.engine = DumpEngine(config=self.config, dump_paths=self.dump_paths)

    @staticmethod
    def _load_group(group: orm.Group | str | None) -> orm.Group | None:
        """Validate and load the given group identifier.

        Args:
            group: The group identifier to validate. Can be an orm.Group instance,
                a string (label or UUID), or None.

        Returns:
            Instance of orm.Group if found, or None if input was None.

        Raises:
            NotExistent: If no orm.Group can be loaded for a given label or UUID.
        """
        if isinstance(group, str):
            try:
                return orm.load_group(group)
            except NotExistent:
                raise
            except Exception as exc:
                raise ValueError(f"Error loading group '{group}': {exc}")
        elif isinstance(group, orm.Group):
            return group
        else:
            return None

    def dump(self):
        """Perform the dump operation."""
        self.engine.dump(entity=self.group)

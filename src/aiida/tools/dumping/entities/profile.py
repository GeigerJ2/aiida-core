###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################

# TODO: Possibly use `batch_iter` from aiida.tools.archive.common
# TODO: Add option to just print the resulting directory tree
# No groups selected, dump data which is not part of any group
# If groups selected, however, this data should not also be dumped automatically
# TODO: Maybe populate the `processes_to_dump` property here, even though I don't really need it, as I get the
# TODO: nodes from the specified collection

"""Enhanced ProfileDumper with robust group verification and update support."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from aiida import load_profile
from aiida.common.log import AIIDA_LOGGER
from aiida.manage.configuration.profile import Profile
from aiida.tools.dumping.config import DumpConfig
from aiida.tools.dumping.engine import DumpEngine
from aiida.tools.dumping.utils import (
    DumpPaths,
    generate_profile_default_dump_path,
)

logger = AIIDA_LOGGER.getChild('tools.dumping.entities.profile')

class ProfileDumper:
    """Dumps all data in an AiiDA profile."""

    def __init__(self, profile=None, config=None, output_path=None):
        self.profile = self._load_profile(profile)
        self.config = config or DumpConfig()

        if output_path is None:
            default_path = generate_profile_default_dump_path(self.profile)
            self.dump_paths = DumpPaths(parent=Path.cwd(), child=default_path)
        else:
            self.dump_paths = DumpPaths.from_path(output_path)

        # Create the engine with the refactored components
        self.engine = DumpEngine(
            config=self.config,
            dump_paths=self.dump_paths
        )

    def _load_profile(self, profile: str | Profile | None) -> Profile:
        """Load the AiiDA profile from string or Profile object."""
        if isinstance(profile, str):
            loaded_profile = load_profile(profile=profile, allow_switch=True)
        elif isinstance(profile, Profile):
            loaded_profile = profile
        else:
            from aiida.manage import get_manager
            manager = get_manager()
            loaded_profile = cast(Profile, manager.get_profile())

        assert loaded_profile is not None
        return loaded_profile

    def dump(self):
        """Perform the dump operation."""
        # Simply delegate to the engine
        self.engine.dump()

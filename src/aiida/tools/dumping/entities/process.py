###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################
"""Functionality for dumping of ProcessNodes."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from aiida import orm
from aiida.common.exceptions import NotExistent
from aiida.common.log import AIIDA_LOGGER
from aiida.tools.dumping.config import DumpConfig
from aiida.tools.dumping.engine import DumpEngine
from aiida.tools.dumping.utils.paths import (
    DumpPaths,
    generate_process_default_dump_path,
)

if TYPE_CHECKING:
    from aiida.tools.dumping.config import DumpConfig

# TODO: See if I can always use name, or pass the dumping sub module explicitly

logger = AIIDA_LOGGER.getChild('tools.dumping.entities.process')


class ProcessDumper:
    """Facade to initiate dumping of a single ProcessNode."""

    def __init__(
        self,
        process: orm.ProcessNode | int | str,
        config: DumpConfig | None = None,
        output_path: str | Path | None = None,  # Changed from dump_paths
    ):
        """
        Initialize the ProcessDumper facade.

        :param process: The ProcessNode instance or its PK, UUID, or label.
        :param config: The DumpConfig instance. If None, a default config is used.
        :param output_path: The destination path for the dump. If None, a default is generated.
        """
        self.process = ProcessDumper._load_process_node(process)
        self.config = config or DumpConfig()

        # Resolve DumpPaths based on output_path and the node
        if output_path is None:
            default_path = generate_process_default_dump_path(process_node=self.process)
            self.dump_paths = DumpPaths(parent=Path.cwd(), child=default_path)
        else:
            self.dump_paths = DumpPaths.from_path(output_path)

        # Create the engine, passing the context
        self.engine = DumpEngine(
            config=self.config,
            dump_paths=self.dump_paths,
            # top_level_entity_type='process' # Pass context
        )

    @staticmethod
    def _load_process_node(identifier: orm.ProcessNode | int | str) -> orm.ProcessNode:
        """Load the process node from its identifier."""
        if isinstance(identifier, orm.ProcessNode):
            return identifier
        try:
            return orm.load_node(identifier=identifier)
        except NotExistent as exc:
            raise ValueError(f"Process node with identifier '{identifier}' not found.") from exc
        except Exception as exc:
            raise ValueError(f"Error loading process node '{identifier}': {exc}") from exc

    def dump(self) -> None:
        """Perform the dump operation by invoking the engine."""
        logger.info(f'Initiating dump for ProcessNode PK={self.process.pk} via DumpEngine.')
        # The engine will select the ProcessDumpStrategy
        self.engine.dump(entity=self.process)
        logger.info(f'Dump completed for ProcessNode PK={self.process.pk}.')

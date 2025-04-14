###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################
"""Utility functions for dumping features."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aiida.common.log import AIIDA_LOGGER
from aiida.tools.dumping.utils.paths import safe_delete_dir

if TYPE_CHECKING:
    from aiida.tools.dumping.storage.logger import DumpLogger


__all__ = ('delete_missing_node_dir',)

logger = AIIDA_LOGGER.getChild('tools.dumping.utils')

def delete_missing_node_dir(dump_logger: DumpLogger, to_delete_uuid: str) -> None:
    # TODO: Possibly make a delete method for the path and the log, and then call that in the loop

    current_store = dump_logger.get_store_by_uuid(uuid=to_delete_uuid)
    if not current_store:
        return

    # ! Cannot load the node via its UUID here and use the type to get the correct store, as the Node is deleted
    # ! from the DB. Should find a better solution

    path_to_delete = dump_logger.get_dump_path_by_uuid(uuid=to_delete_uuid)
    if path_to_delete is not None:
        try:
            safe_delete_dir(
                path=path_to_delete,
                safeguard_file='.aiida_node_metadata.yaml',
            )
            current_store.del_entry(uuid=to_delete_uuid)
        except:
            raise


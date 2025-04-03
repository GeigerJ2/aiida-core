###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################

"""Base class for collection mirror."""

from __future__ import annotations


from aiida import orm
from aiida.tools.mirror.base import BaseMirror
from aiida.tools.mirror.collector import MirrorNodeCollector
from aiida.tools.mirror.container import MirrorNodeContainer
from aiida.tools.mirror.config import (
    MirrorMode,
    MirrorPaths,
    MirrorTimes,
    NodeCollectorConfig,
)
from aiida.tools.mirror.logger import MirrorLogger
from aiida.tools.mirror.utils import NodeMirrorKeyMapper, safe_delete_dir
from dataclasses import fields


class BaseCollectionMirror(BaseMirror):
    def __init__(
        self,
        mirror_mode: MirrorMode | None = None,
        mirror_paths: MirrorPaths | None = None,
        mirror_times: MirrorTimes | None = None,
        mirror_logger: MirrorLogger | None = None,
        node_collector_config: NodeCollectorConfig | None = None,
    ):
        super().__init__(
            mirror_mode=mirror_mode,
            mirror_paths=mirror_paths,
            mirror_times=mirror_times,
            mirror_logger=mirror_logger,
        )

        self.node_collector_config = node_collector_config or NodeCollectorConfig()

    def get_mirror_node_container(self, group: orm.Group | None = None) -> MirrorNodeContainer:
        """
        Returns a NodeContainer by collecting nodes using the NodeDumpCollector.

        Returns:
            NodeContainer: The collected node container
        """
        node_collector = MirrorNodeCollector(
            config=self.node_collector_config,
            mirror_times=self.mirror_times,
            mirror_logger=self.mirror_logger,
        )

        return node_collector.collect_to_mirror(group=group)

    def get_delete_node_container(self) -> MirrorNodeContainer:
        """
        Returns a NodeContainer by collecting nodes using the NodeDumpCollector.

        Returns:
            NodeContainer: The collected node container
        """
        node_collector = MirrorNodeCollector(
            config=self.node_collector_config,
            mirror_times=self.mirror_times,
            mirror_logger=self.mirror_logger,
        )

        return node_collector.collect_to_delete()


    # Implement this here, as for the deletion, we don't care about the group
    def do_delete(self) -> None:
        delete_node_container = self.get_delete_node_container()
        # store_names = [field.name for field in fields(delete_node_container)]
        # NOTE: Hard-code `store_names` to
        # in descending order of the size of the entity. E.g., better to just delete the whole group at once
        # rather than deleting each node inside of it individually
        for store_name in ("groups", "workflows", "calculations", "data"):
            to_delete_uuids = getattr(delete_node_container, store_name)
            log_store = getattr(self.mirror_logger, store_name)
            # if store_name == "groups":
            #     import ipdb; ipdb.set_trace()
            for to_delete_uuid in to_delete_uuids:
                path = log_store.get_entry(to_delete_uuid).path
                mirror_paths = MirrorPaths.from_path(path)
                _ = safe_delete_dir(path=path, safeguard_file=mirror_paths.safeguard)
                self.mirror_logger.del_entry(store=log_store, uuid=to_delete_uuid)

            # if len(store) > 0:
            #     # Process the entries in the store
            #     for entry in store:
            #         # Your deletion logic here
            #         pass

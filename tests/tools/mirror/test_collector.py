# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################
"""Tests for the dumping of group data to disk."""

import pytest
from aiida.tools.mirror.collector import MirrorNodeContainer, MirrorNodeCollector
from aiida.tools.mirror.logger import MirrorLog, MirrorLogger
from aiida.tools.mirror.utils import MirrorPaths
from aiida.tools.mirror.config import NodeCollectorConfig, NodeMirrorGroupScope
from aiida import orm
from aiida.tools.graph.deletions import delete_nodes
from sqlalchemy import inspect
import copy


class TestMirrorNodeCollector:
    def test_collect_to_mirror(): ...

    # @pytest.mark.parametrize -> Parametrize different options here, e.g. `only_top_level` stuff
    @pytest.mark.usefixtures('aiida_profile_clean')
    def test_collect_to_delete(self, tmp_path):
        mirror_logger = MirrorLogger(mirror_paths=MirrorPaths.from_path(tmp_path))
        empty_mirror_logger = copy.deepcopy(mirror_logger)

        for process_type in (orm.CalculationNode, orm.WorkflowNode):
            processes = [process_type() for i in range(3)]
            _ = [n.store() for n in processes]

            store = mirror_logger.get_store_by_orm(process_type)

            mirror_logger.add_entries(
                store,
                uuids=[c.uuid for c in processes],
                entries=[MirrorLog(path=(tmp_path / f'-{proc.__class__.__name__[:4]}')) for proc in processes],
            )

        node_collector_config = NodeCollectorConfig(group_scope=NodeMirrorGroupScope.NO_GROUP)

        mirror_node_collector = MirrorNodeCollector(config=node_collector_config, mirror_logger=empty_mirror_logger)

        # mirror_container = mirror_node_collector.collect_to_mirror()

        mirror_container = mirror_node_collector.collect_to_mirror()

        delete_container = mirror_node_collector.collect_to_delete(mirror_logger=mirror_logger)

        assert (
            len(delete_container.workflows + delete_container.calculations + delete_container.data)
            == 0
        )

        del_calculation = mirror_container.calculations.pop(0)
        del_workflow = mirror_container.workflows.pop(0)

        _ = delete_nodes([_.pk for _ in (del_calculation, del_workflow)], dry_run=False)

        # delete_container = mirror_node_collector.collect_to_delete(mirror_logger=mirror_logger)


        import ipdb

        ipdb.set_trace()

        pass

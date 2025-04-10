# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################
"""Tests for the dumping of group data to disk."""

import copy

import pytest

from aiida import orm
from aiida.tools.graph.deletions import delete_nodes
from aiida.tools.mirror.collector import MirrorCollector
from aiida.tools.mirror.config import (
    MirrorCollectorConfig,
    MirrorPaths,
    MirrorTimes,
    NodeMirrorGroupScope,
)
from aiida.tools.mirror.logger import MirrorLog, MirrorLogger


class TestMirrorNodeCollector:
    def test_resolve_filters(self, tmp_path):
        ...
        # TODO: Need to add the time filter until the `current` time now
        # add_group = setup_add_group
        # multiply_add_group = setup_multiply_add_group

        # orm_class = orm.CalculationNode
        # mirror_paths = MirrorPaths.from_path(tmp_path)
        # mirror_logger = MirrorLogger(mirror_paths=mirror_paths, mirror_times=MirrorTimes())

        # # NOTE: This doesn't raise anymore
        # # with pytest.raises(ValueError):
        # #     mirror_node_collector = MirrorNodeCollector(
        # #         mirror_logger=mirror_logger, config=MirrorCollectorConfig()
        # #     )
        # #     _ = mirror_node_collector._resolve_filters(orm_class=orm_class)

        # # No filter by time applied
        # mirror_node_collector = MirrorCollector(
        #     mirror_logger=mirror_logger,
        #     config=MirrorCollectorConfig(filter_by_last_mirror_time=False),
        # )
        # filters = mirror_node_collector._resolve_filters(orm_class=orm_class)
        # assert filters == {}

        # # Filter by time applied
        # mirror_node_collector = MirrorCollector(
        #     mirror_logger=mirror_logger,
        #     config=MirrorCollectorConfig(),
        # )
        # filters = mirror_node_collector._resolve_filters(orm_class=orm.CalculationNode)
        # assert filters == {'mtime': {'>=': mirror_logger.mirror_times.last}}

        # calc = orm.CalculationNode()
        # calc.store()
        # mirror_logger.stores.calculations.add_entry(
        #     uuid=calc.uuid,
        #     entry=MirrorLog(path=tmp_path / 'calc'),
        # )

        # # WorkflowNode shouldn't appear in calculation store and filters
        # wf = orm.WorkflowNode()
        # wf.store()
        # mirror_logger.stores.workflows.add_entry(
        #     uuid=wf.uuid,
        #     entry=MirrorLog(path=tmp_path / 'wf'),
        # )

        # mirror_node_collector = MirrorCollector(
        #     mirror_logger=mirror_logger,
        #     config=MirrorCollectorConfig(filter_by_last_mirror_time=False),
        # )
        # filters = mirror_node_collector._resolve_filters(orm_class=orm.CalculationNode)
        # assert filters == {'uuid': {'!in': [calc.uuid]}}

        # mirror_node_collector = MirrorCollector(
        #     mirror_logger=mirror_logger, config=MirrorCollectorConfig()
        # )
        # filters = mirror_node_collector._resolve_filters(orm_class=orm.CalculationNode)
        # assert filters == {'mtime': {'>=': mirror_logger.mirror_times.last}, 'uuid': {'!in': [calc.uuid]}}

        # import ipdb

        # include_processes: bool = True
        # include_data: bool = False
        # filter_by_last_mirror_time: bool = True
        # only_top_level_calcs: bool = True
        # only_top_level_workflows: bool = True
        # group_scope: NodeMirrorGroupScope = NodeMirrorGroupScope.IN_GROUP

    # @pytest.mark.parametrize -> Parametrize different options here, e.g. `only_top_level` stuff

    @pytest.mark.usefixtures('aiida_profile_clean')
    def test_collect_to_delete(self, tmp_path):
        process_types = (orm.CalculationNode, orm.WorkflowNode)
        process_dict = dict.fromkeys(process_types)

        # Need to create the processes before MirrorTimes is instantiated
        # Otherwise the time restriction of nodes up to the current time filters them out
        # FIXME: This note seems wrong. investigate further
        for process_type in process_types:
            processes = [process_type() for i in range(3)]
            _ = [n.store() for n in processes]
            process_dict[process_type] = processes

        mirror_logger = MirrorLogger(mirror_paths=MirrorPaths.from_path(tmp_path), mirror_times=MirrorTimes())
        empty_mirror_logger = copy.deepcopy(mirror_logger)

        for process_type, processes in process_dict.items():
            store = mirror_logger.get_store_by_orm(process_type)

            mirror_logger.add_entries(
                store,
                uuids=[c.uuid for c in processes],
                entries=[MirrorLog(path=(tmp_path / f'{proc.__class__.__name__[:4]}')) for proc in processes],
            )

        mirror_collector_config = MirrorCollectorConfig(group_scope=NodeMirrorGroupScope.NO_GROUP)

        mirror_node_collector = MirrorCollector(config=mirror_collector_config, mirror_logger=empty_mirror_logger)

        mirror_node_store = mirror_node_collector.collect_to_mirror()

        delete_node_store = mirror_node_collector.collect_to_delete()

        assert len(delete_node_store.workflows | delete_node_store.calculations | delete_node_store.data) == 0

        del_calculation = mirror_node_store.calculations.pop(0)
        del_workflow = mirror_node_store.workflows.pop(0)

        _ = delete_nodes([_.pk for _ in (del_calculation, del_workflow)], dry_run=False)

        # delete_container = mirror_node_collector.collect_to_delete(mirror_logger=mirror_logger)

    def test_collect_to_mirror(self): ...

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
from aiida.tools.dumping.config import (
    NodeDumpGroupScope,
)
from aiida.tools.dumping.logger import DumpLog, DumpLogger
from aiida.tools.dumping.utils.time import DumpTimes
from aiida.tools.graph.deletions import delete_nodes


class TestDumpNodeCollector:
    def test_resolve_filters(self, tmp_path):
        ...
        # TODO: Need to add the time filter until the `current` time now
        # add_group = setup_add_group
        # multiply_add_group = setup_multiply_add_group

        # orm_class = orm.CalculationNode
        # dump_paths = DumpPaths.from_path(tmp_path)
        # dump_logger = DumpLogger(dump_paths=dump_paths, dump_times=DumpTimes())

        # # NOTE: This doesn't raise anymore
        # # with pytest.raises(ValueError):
        # #     dump_node_collector = DumpNodeCollector(
        # #         dump_logger=dump_logger, config=DumpCollectorConfig()
        # #     )
        # #     _ = dump_node_collector._resolve_filters(orm_class=orm_class)

        # # No filter by time applied
        # dump_node_collector = DumpCollector(
        #     dump_logger=dump_logger,
        #     config=DumpCollectorConfig(filter_by_last_dump_time=False),
        # )
        # filters = dump_node_collector._resolve_filters(orm_class=orm_class)
        # assert filters == {}

        # # Filter by time applied
        # dump_node_collector = DumpCollector(
        #     dump_logger=dump_logger,
        #     config=DumpCollectorConfig(),
        # )
        # filters = dump_node_collector._resolve_filters(orm_class=orm.CalculationNode)
        # assert filters == {'mtime': {'>=': dump_logger.dump_times.last}}

        # calc = orm.CalculationNode()
        # calc.store()
        # dump_logger.stores.calculations.add_entry(
        #     uuid=calc.uuid,
        #     entry=DumpLog(path=tmp_path / 'calc'),
        # )

        # # WorkflowNode shouldn't appear in calculation store and filters
        # wf = orm.WorkflowNode()
        # wf.store()
        # dump_logger.stores.workflows.add_entry(
        #     uuid=wf.uuid,
        #     entry=DumpLog(path=tmp_path / 'wf'),
        # )

        # dump_node_collector = DumpCollector(
        #     dump_logger=dump_logger,
        #     config=DumpCollectorConfig(filter_by_last_dump_time=False),
        # )
        # filters = dump_node_collector._resolve_filters(orm_class=orm.CalculationNode)
        # assert filters == {'uuid': {'!in': [calc.uuid]}}

        # dump_node_collector = DumpCollector(
        #     dump_logger=dump_logger, config=DumpCollectorConfig()
        # )
        # filters = dump_node_collector._resolve_filters(orm_class=orm.CalculationNode)
        # assert filters == {'mtime': {'>=': dump_logger.dump_times.last}, 'uuid': {'!in': [calc.uuid]}}

        # import ipdb

        # include_processes: bool = True
        # include_data: bool = False
        # filter_by_last_dump_time: bool = True
        # only_top_level_calcs: bool = True
        # only_top_level_workflows: bool = True
        # group_scope: NodeDumpGroupScope = NodeDumpGroupScope.IN_GROUP

    # @pytest.mark.parametrize -> Parametrize different options here, e.g. `only_top_level` stuff

    @pytest.mark.usefixtures('aiida_profile_clean')
    def test_collect_to_delete(self, tmp_path):
        process_types = (orm.CalculationNode, orm.WorkflowNode)
        process_dict = dict.fromkeys(process_types)

        # Need to create the processes before DumpTimes is instantiated
        # Otherwise the time restriction of nodes up to the current time filters them out
        # FIXME: This note seems wrong. investigate further
        for process_type in process_types:
            processes = [process_type() for i in range(3)]
            _ = [n.store() for n in processes]
            process_dict[process_type] = processes

        dump_logger = DumpLogger(dump_paths=DumpPaths.from_path(tmp_path), dump_times=DumpTimes())
        empty_dump_logger = copy.deepcopy(dump_logger)

        for process_type, processes in process_dict.items():
            store = dump_logger.get_store_by_orm(process_type)

            dump_logger.add_entries(
                store,
                uuids=[c.uuid for c in processes],
                entries=[DumpLog(path=(tmp_path / f'{proc.__class__.__name__[:4]}')) for proc in processes],
            )

        dump_collector_config = DumpDbCollectorConfig(group_scope=NodeDumpGroupScope.NO_GROUP)

        dump_node_collector = DumpDbCollector(config=dump_collector_config, dump_logger=empty_dump_logger)

        dump_node_store = dump_node_collector.collect_to_dump()

        delete_node_store = dump_node_collector.collect_to_delete()

        assert len(delete_node_store.workflows | delete_node_store.calculations | delete_node_store.data) == 0

        del_calculation = dump_node_store.calculations.pop(0)
        del_workflow = dump_node_store.workflows.pop(0)

        _ = delete_nodes([_.pk for _ in (del_calculation, del_workflow)], dry_run=False)

        # delete_container = dump_node_collector.collect_to_delete(dump_logger=dump_logger)

    def test_collect_to_dump(self): ...

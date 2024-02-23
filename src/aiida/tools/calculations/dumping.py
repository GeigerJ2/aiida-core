import pathlib
from pathlib import Path

import yaml

from aiida.common import LinkType
from aiida.orm import CalcJobNode
from aiida.orm.nodes.data import FolderData
from aiida.orm.nodes.data.singlefile import SinglefileData


def calcjob_dump(
    calcjob_node: CalcJobNode,
    output_path: pathlib.Path,
    node_inputs: bool = True,
    dump_attributes: bool = False,
    dump_extras: bool = False,
    use_prepare_for_submission: bool = False,
):

    calcjob_node.base.repository.copy_tree(output_path.resolve() / Path('raw_inputs'))
    calcjob_node.outputs.retrieved.copy_tree(output_path.resolve() / Path('raw_outputs'))

    if node_inputs is True:
        input_node_triples = calcjob_node.base.links.get_incoming(link_type=LinkType.INPUT_CALC)
        dump_types = (SinglefileData, FolderData)

        for input_node_triple in input_node_triples:
            # Select only repositories that hold objects and are of reasonable types
            if len(input_node_triple.node.base.repository.list_objects()) > 0 and isinstance(
                input_node_triple.node, dump_types
            ):
                # Create nested path from name mangling
                input_node_path = output_path / Path('node_inputs') / Path(*input_node_triple.link_label.split('__'))
                input_node_path.mkdir(parents=True, exist_ok=True)
                input_node_triple.node.base.repository.copy_tree(input_node_path)

    if use_prepare_for_submission:
        raise NotImplementedError()

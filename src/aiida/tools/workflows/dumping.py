import io
import pathlib
from pathlib import Path
from pprint import pprint
from typing import Union

import yaml

from aiida.common.folders import Folder
from aiida.common.links import LinkType
from aiida.orm import (ArrayData, CalcFunctionNode, CalcJobNode, WorkChainNode,
                       WorkFunctionNode)
from aiida.orm.nodes.data import FolderData
from aiida.orm.utils.serialize import AiiDADumper, represent_node
from aiida.tools.calculations.dumping import calcjob_dump


def recursive_dump(
    process_node: Union[WorkChainNode, CalcJobNode],
    filepath: pathlib.Path,
    node_inputs: bool = True,
    dump_attributes: bool = False,
    dump_extras: bool = False,
    use_prepare_for_submission: bool = False,
) -> None:
    called_links = process_node.base.links.get_outgoing(link_type=(LinkType.CALL_CALC, LinkType.CALL_WORK)).all()

    # Don't increment index for ProcessNodes that don't have file IO (Calc/Work-FunctionNodes), such as
    # `create_kpoints_from_distance`

    called_links = [
        called_link
        for called_link in called_links
        if not isinstance(called_link.node, (CalcFunctionNode, WorkFunctionNode))
    ]

    for index, link_triple in enumerate(sorted(called_links, key=lambda link_triple: link_triple.node.ctime), start=1):
        node = link_triple.node
        link_label = link_triple.link_label

        if link_label != 'CALL' and not link_label.startswith('iteration_'):
            label = f'{index:02d}-{link_label}-{node.process_label}'
        else:
            label = f'{index:02d}-{node.process_label}'

        node_path = filepath.resolve() / label
        node_path.mkdir(exist_ok=True, parents=True)

        # Dump node extras/attributes irrespective of type
        if dump_attributes is True:
            node_attributes = process_node.base.attributes.all
            with open(node_path / '.aiida_node_attributes.yaml', 'w') as handle:
                yaml.dump(node_attributes, handle, sort_keys=False)

        if dump_extras is True:
            node_extras = process_node.base.extras.all
            with open(node_path / '.aiida_node_extras.yaml', 'w') as handle:
                yaml.dump(node_extras, handle, sort_keys=False)

        if isinstance(node, WorkChainNode):
            recursive_dump(node, node_path, node_inputs, dump_attributes, dump_extras)

        elif isinstance(node, CalcJobNode):
            calcjob_dump(
                calcjob_node=node,
                output_path=node_path,
                node_inputs=node_inputs,
                use_prepare_for_submission=use_prepare_for_submission,
            )

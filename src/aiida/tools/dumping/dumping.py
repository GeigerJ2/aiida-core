from pathlib import Path
from typing import Type, Union

import yaml

from aiida.cmdline.utils import echo
from aiida.common import LinkType
from aiida.common.folders import Folder
from aiida.engine.daemon.execmanager import upload_calculation
from aiida.engine.utils import instantiate_process
from aiida.manage import get_manager
from aiida.orm import CalcFunctionNode, CalcJobNode, WorkChainNode, WorkFunctionNode
from aiida.orm.nodes.data import FolderData
from aiida.orm.nodes.data.singlefile import SinglefileData
from aiida.orm.nodes.process import ProcessNode
from aiida.transports.plugins.local import LocalTransport


class ProcessNodeDumper:
    """Utility class to dump selected ProcessNode properties, attributes and extras."""

    _metadata_properties = [
        'label',
        'description',
        'pk',
        'uuid',
        'ctime',
        'mtime',
        'node_type',
        'process_type',
        'is_finished_ok',
    ]

    def __init__(self, include_attributes: bool = True, include_extras: bool = True):
        self.include_attributes = include_attributes
        self.include_extras = include_extras

    def dump_yaml(
        self, node: Type[ProcessNode], output_path: Path, output_filename: str = 'aiida_node_metadata.yaml'
    ) -> None:
        node_dict = {}
        metadata_dict = {}

        # Add actual node `@property`s to dictionary
        for metadata_property in self._metadata_properties:
            metadata_dict[metadata_property] = getattr(node, metadata_property)

        node_dict['Node metadata'] = metadata_dict

        # Add node attributes
        if self.include_attributes is True:
            node_attributes = node.base.attributes.all
            node_dict['Node attributes'] = node_attributes

        # Add node extras
        if self.include_extras is True:
            node_extras = node.base.extras.all
            if node_extras:
                node_dict['Node extras'] = node_extras

        # Dump to file
        output_file = output_path / output_filename
        if not output_file.exists():
            with open(output_file, 'w') as handle:
                yaml.dump(node_dict, handle, sort_keys=False)
        else:
            echo.echo_critical('yaml file already exists.')


def _recursive_dump(
    process_node: Union[WorkChainNode, CalcJobNode],
    output_path: Path,
    no_node_inputs: bool = False,
    use_prepare_for_submission: bool = False,
    node_dumper: ProcessNodeDumper = None,
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

        output_path_new = output_path.resolve() / label
        output_path_new.mkdir(exist_ok=True, parents=True)

        # Dump node metadata as yaml
        if node_dumper is None:
            node_dumper = ProcessNodeDumper()
        node_dumper.dump_yaml(node=node, output_path=output_path_new)

        # Recursive function call for WorkChainNode
        if isinstance(node, WorkChainNode):
            _recursive_dump(
                process_node=node,
                output_path=output_path_new,
                no_node_inputs=no_node_inputs,
                use_prepare_for_submission=use_prepare_for_submission,
                node_dumper=node_dumper,
            )

        # Dump for CalcJobNode
        elif isinstance(node, CalcJobNode):
            _calcjob_dump(
                calcjob_node=node,
                output_path=output_path_new,
                no_node_inputs=no_node_inputs,
                use_prepare_for_submission=use_prepare_for_submission,
            )


def _calcjob_dump(
    calcjob_node: CalcJobNode,
    output_path: Path,
    no_node_inputs: bool = False,
    use_prepare_for_submission: bool = False,
    # node_dumper: ProcessNodeDumper = None
    # -> Actually run in `cmd_calcjob` and outside in loop in `cmd_workchain`. Necessary to actually pass here?
):
    output_path_abs = output_path.resolve()

    if use_prepare_for_submission is True:
        echo.echo_warning('`use_prepare_for_submission` not fully implemented yet. Files likely missing.')
        try:
            builder_restart = calcjob_node.get_builder_restart()
            runner = get_manager().get_runner()
            calcjob_process = instantiate_process(runner, builder_restart)
            calc_info = calcjob_process.presubmit(folder=Folder(abspath=output_path_abs))
            remote_data = upload_calculation(
                node=calcjob_node,
                transport=LocalTransport(),
                calc_info=calc_info,
                folder=Folder(abspath=output_path_abs),
                inputs=calcjob_process.inputs,
                dry_run=True,
            )

        except ValueError:
            echo.echo_error(
                'ValueError when trying to get a restart-builder. Do you have the relevant aiida-plugin installed?'
            )

    else:
        calcjob_node.outputs.retrieved.copy_tree(output_path_abs / Path('raw_outputs'))
        # Outputs obtained via retrieved and should not be present when using `prepare_for_submission` as it puts the
        # calculation in a state to be submitted
        calcjob_node.base.repository.copy_tree(output_path_abs / Path('raw_inputs'))

        if no_node_inputs is False:
            input_node_triples = calcjob_node.base.links.get_incoming(link_type=LinkType.INPUT_CALC)
            dump_types = (SinglefileData, FolderData)

            for input_node_triple in input_node_triples:
                # Select only repositories that hold objects and are of reasonable types
                if len(input_node_triple.node.base.repository.list_objects()) > 0 and isinstance(
                    input_node_triple.node, dump_types
                ):
                    # Could also create nested path from name mangling
                    # output_path / Path('node_inputs') / Path(*input_node_triple.link_label.split('__'))
                    input_node_path = output_path / Path('node_inputs') / Path(input_node_triple.link_label)

                    input_node_path.mkdir(parents=True, exist_ok=True)
                    input_node_triple.node.base.repository.copy_tree(input_node_path.resolve())


# def processnode_metadata_dump(
#     node: Type[ProcessNode], output_path: Path, include_attributes: bool = False, include_extras: bool = False
# ) -> None:
#     """Dump selected `ProcessNode` properties, as well as optionally attributes and extras to a `yaml` file.

#     Args:
#         node (Type[ProcessNode]): Node of `ProcessNode` type for which the data should be dumped
#         output_path (Path): Output path where the `yaml` file will be written.
#         include_attributes (bool, optional): Dump node attributes? Defaults to False.
#         include_extras (bool, optional): Dump node extras? Defaults to False.
#     """

#     _metadata_property_list = [
#         'label',
#         'description',
#         'pk',
#         'uuid',
#         'ctime',
#         'mtime',
#         'node_type',
#         'process_type',
#         'is_finished_ok',
#     ]

#     node_dict = {}
#     metadata_dict = {}

#     for metadata_property in _metadata_property_list:
#         metadata_dict[metadata_property] = getattr(node, metadata_property)

#     node_dict['Node metadata'] = metadata_dict

#     if include_attributes is True:
#         node_attributes = node.base.attributes.all
#         node_dict['Node attributes'] = node_attributes

#     if include_extras is True:
#         node_extras = node.base.extras.all
#         if node_extras:
#             node_dict['Node extras'] = node_extras

#     with open(output_path / 'node_metadata.yaml', 'w') as handle:
#         yaml.dump(node_dict, handle, sort_keys=False)

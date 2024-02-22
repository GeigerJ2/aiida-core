import pathlib
import re
from typing import Union

from aiida.common.links import LinkType
from aiida.orm import CalcFunctionNode, CalcJobNode, WorkChainNode, WorkFunctionNode


def recursive_dump(process_node: Union[WorkChainNode, CalcJobNode], filepath: pathlib.Path) -> None:

    from pathlib import Path
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

        final_path = filepath / label
        final_path_abs = final_path.resolve()

        if isinstance(node, WorkChainNode):
            recursive_dump(node, final_path_abs)
        elif isinstance(node, CalcJobNode):
            node.base.repository.copy_tree(final_path_abs / Path("input"))
            node.outputs.retrieved.copy_tree(final_path_abs / Path("output"))


# def workchain_filedump(ctx, workchain, path, mode):
#     """Dump input/output files of calcjobs run by the given workchain."""

#     echo.echo_warning(
#         'Caution: No provenance. The retrieved input/output files are not guaranteed to be complete '
#         'for a full restart of the given workchain. Instead, this utility is intended for easy inspection '
#         'of the files that were involved in its execution. For restarting workchains, see the `get_builder_restart` '
#         'method instead.'
#     )

#     path_node_list = _recursive_get_node_path(workchain)
#     paths = [_[0] for _ in path_node_list]
#     paths = _number_path_elements(path_list=paths, parent_path=path)
#     nodes = [_[1] for _ in path_node_list]

#     if not Path(path).is_dir():
#         # ctx.invoke(_workchain_maketree, workchain=workchain, path=path)
#         _workchain_maketree(numbered_paths=paths)

#     mode_functions = {
#         'input': [calcjob_inputdump],
#         'output': [calcjob_outputdump],
#         'all': [calcjob_inputdump, calcjob_outputdump],
#     }

#     if mode not in mode_functions:
#         raise KeyError(f'Provided mode not available, must be one of: {"/".join(mode_functions.keys())}.')

#     for calcjob_node_path, calcjob_node in zip(paths, nodes):
#         for func in mode_functions[mode]:
#             ctx.invoke(func, calcjob=calcjob_node, path=calcjob_node_path)

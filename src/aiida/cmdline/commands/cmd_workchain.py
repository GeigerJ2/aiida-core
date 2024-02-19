###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################
"""`verdi workchain` commands."""

import re
from pathlib import Path
from typing import List, Optional, Tuple

import click

from aiida import orm
from aiida.cmdline.commands.cmd_calcjob import calcjob_inputdump, calcjob_outputdump
from aiida.cmdline.commands.cmd_verdi import verdi
from aiida.cmdline.params import arguments
from aiida.cmdline.params.types import WorkflowParamType
from aiida.cmdline.utils import echo
from aiida.common import LinkType
from aiida.engine.processes.calcjobs.calcjob import CalcJob
from aiida.engine.processes.workchains.workchain import WorkChainNode
from aiida.orm import ProcessNode
from aiida.orm.nodes.process.calculation.calcjob import CalcJobNode

# TODO I have several other cli functions that are useful for
# my own work, but somehow it's not easy to merge them
# here, e.g.,
#   My original version supports gotocomputer for
#   workchain, calcjob, RemoteData, or RemoteStashFolderData,
#   this is convenient for user, but since we are now in
#   the workchain namespace, we shouldn't add support for
#   RemoteData and RemoteStashFolderData here, but I hope
#   we can put it somewhere and ideally the cli command should
#   be easy to remember.
#   https://github.com/aiidateam/aiida-wannier90-workflows/blob/2e8c912fa1f5fcbbbbb0478e116c8f73c2ffd048/src/aiida_wannier90_workflows/cli/node.py#L274-L277

# TODO same as above, the other cli commands in the aiida-wannier90-workflows
# package support both calcjob and workchain at the same time, this is
# convenient for the user (less to remember), but here for the sake of
# conceptual cleanliness, the cli commands in aiida-core is split into
# calcjob and workchain. In addition, the implementation for calcjob and
# workchain cli commands are similar, we should try to merge them into one.


def _recursive_get_node_path(
    called: ProcessNode,
    recursion_path: Optional[Path] = Path('.'),
    path_node_list: Optional[List[Tuple[Path, ProcessNode]]] = None,
) -> List[Tuple[Path, ProcessNode]]:
    """Recursively retrieves CalcJobs of WorkChain and generates "paths".

    This function recursively traces down a WorkChain to the lowest-level
    CalcJobs and generates the corresponding "paths" based on the structure of
    the WorkChain. These are returned together with the corresponding
    CalcJobNodes as a list of tuples.
    Taken from: https://github.com/aiidateam/aiida-core/pull/6276/ and modified.

    Args:
        called (ProcessNode): Current ProcessNode, can belong to Calculation
        or WorkflowNode.
        recursion_path (Optional[Path], optional): Parent path at each recursive
        function call. Defaults to cwd.
        path_node_list (Optional[tuple], optional): List of tuples containing
        the "path" based on the workchain structure, and the actual CalcJobNode.
        Is populated during the recursive function calls.

    Returns:
        List[Tuple[Path, ProcessNode]]: Filled path_node_list.
    """
    if path_node_list is None:
        path_node_list = []

    links = called.base.links.get_outgoing(link_type=(LinkType.CALL_CALC, LinkType.CALL_WORK)).all()
    links.sort(key=lambda x: x.node.ctime)

    for link in links:
        link_label = link.link_label
        called = link.node

        process_label = called.process_label.replace('WorkChain', 'WC').replace('Calculation', 'Calc')

        if 'iteration_' in link_label:
            link_label = link_label.replace('iteration_', '')
            path_label = f'{link_label}-{process_label}'
        else:
            path_label = link_label

        save_path = recursion_path / path_label

        if isinstance(called, WorkChainNode):
            _recursive_get_node_path(called, recursion_path=save_path, path_node_list=path_node_list)

        elif isinstance(called, CalcJobNode):
            path_node_list.append((save_path, called))

    return path_node_list


def _number_path_elements(path_list: List[Path], parent_path: Path) -> List[Path]:
    # Could make this function iterate through all path parts to create the
    # actual numbering hierarchy, if that is needed. Right now, all numbers
    # below the top-level are directoly taken from the `iteration_`
    # care of by AiiDA via `iteration`

    # TODO: Turn this into general function to take care of numbering with
    # variable depth
    """Utility to add numbering of the steps of the WorkChain.

    Returns:
        List: Updated list of PosixPaths with the relative numbering of each
        step added.
    """
    main_counter = 0
    top_label = ''
    modified_paths = []

    for posix_path in path_list:
        current_label = posix_path.parts[0]
        if current_label != top_label:
            main_counter += 1
            top_label = current_label

        path_parts = posix_path.parts
        if not re.match(r'^0\d', current_label):
            numbered_parent = f'{main_counter:02d}-{path_parts[0]}'
            modified_path_parts = [parent_path, numbered_parent, *path_parts[1:]]
        else:
            modified_path_parts = [parent_path, *path_parts]

        modified_path = Path(*modified_path_parts)
        modified_paths.append(modified_path)
    return modified_paths


def _workchain_maketree(numbered_paths: Tuple[Path]):
    """Generate directory tree from a tuple of appropriately labeled and
    numbered relative `CalcJobNode` "paths".

    Args:
        numbered_paths (Tuple[Path]): Labeled and numbered relative
        `CalcJobNode` "paths", which were obtained from the structure of a workchain.

    """
    # TODO: Eventually provide this as cli function to only generate the
    # directory tree, without dumping the files. This could be done
    # by giving the WorkChainNode as argument, but would then require calling
    # the recursive function `_get_path_node_tuples` again, as well as adding
    # the numbering, so would lead to code repetition. Not sure how to avoid
    # that, for now.

    for numbered_path in numbered_paths:
        numbered_path.mkdir(parents=True)


@verdi.group('workchain')
def verdi_workchain():
    """Inspect and manage workchains."""


@verdi_workchain.command('filedump')
@arguments.WORKFLOW('workchain', type=WorkflowParamType(sub_classes=('aiida.node:process.workflow.workchain',)))
@click.option(
    '--path',
    '-p',
    type=click.Path(),
    default='.',
    show_default=True,
    help='The parent directory to save the data of the workchain.',
)
@click.option(
    '--mode',
    '-m',
    type=str,
    default='all',
    show_default=True,
    help='Which files to dump? Options: input/output/all.',
)
@click.pass_context
def workchain_filedump(ctx, workchain, path, mode):
    """Dump input/output files of calcjobs run by the given workchain."""

    echo.echo_warning(
        'Caution: No provenance. The retrieved input/output files are not guaranteed to be complete '
        'for a full restart of the given workchain. Instead, this utility is intended for easy inspection '
        'of the files that were involved in its execution. For restarting workchains, see the `get_builder_restart` '
        'method instead.'
    )

    path_node_list = _recursive_get_node_path(workchain)
    paths = [_[0] for _ in path_node_list]
    paths = _number_path_elements(path_list=paths, parent_path=path)
    nodes = [_[1] for _ in path_node_list]

    if not Path(path).is_dir():
        # ctx.invoke(_workchain_maketree, workchain=workchain, path=path)
        _workchain_maketree(numbered_paths=paths)

    mode_functions = {
        'input': [calcjob_inputdump],
        'output': [calcjob_outputdump],
        'all': [calcjob_inputdump, calcjob_outputdump],
    }

    if mode not in mode_functions:
        raise KeyError(f'Provided mode not available, must be one of: {"/".join(mode_functions.keys())}.')

    for calcjob_node_path, calcjob_node in zip(paths, nodes):
        for func in mode_functions[mode]:
            ctx.invoke(func, calcjob=calcjob_node, path=calcjob_node_path)

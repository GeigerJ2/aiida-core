###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################
"""`verdi workchain` commands."""

import pathlib
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
from aiida.orm import Bool, ProcessNode
from aiida.orm.nodes.process.calculation.calcjob import CalcJobNode
from aiida.sphinxext import workchain
from aiida.tools.workflows.dumping import recursive_dump

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


@verdi.group('workchain')
def verdi_workchain():
    """Inspect and manage workchains."""


@verdi_workchain.command('dump')
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
    '--user-prepare-for-submission',
    '-m',
    type=Bool,
    default=False,
    show_default=True,
    help='Use the prepare ',
)
# @click.pass_context
def workchain_dump(workchain, path) -> None:

    import pathlib

    # Set reasonable default path when path argument is omitted
    if path == '.':
        path = f'wc-{workchain.pk}'
    output_directory = pathlib.Path(path)

    try:
        pathlib.Path(output_directory).mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        echo.echo_critical(f'Invalid value for "OUTPUT_DIRECTORY": Path "{output_directory}" exists.')

    recursive_dump(process_node=workchain, filepath=output_directory)

###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################
"""Tests for the mirroring of process data to disk."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from aiida.tools.mirror.config import MirrorMode, MirrorPaths, ProcessMirrorConfig
from aiida.tools.mirror.process import ProcessMirror

from .utils import compare_tree

# TODO: Use `compare_tree` function here, as well
# NOTE: Currently, `_mirror_workflow` requires a ProcessNode argument, but so does the `ProcessMirror` constructor.
# Only problems with the recursive nature of the function. Fix eventually.

# Non-AiiDA variables
filename = 'file.txt'
filecontent = 'a'
inputs_relpath = Path('inputs')
outputs_relpath = Path('outputs')
node_inputs_relpath = Path('node_inputs')
node_outputs_relpath = Path('node_outputs')
default_mirror_paths = [inputs_relpath, outputs_relpath, node_inputs_relpath, node_outputs_relpath]
custom_mirror_paths = [f'{path}_' for path in default_mirror_paths]

# Define variables used for constructing the nodes used to test the mirroring
singlefiledata_linklabel = 'singlefile'
folderdata_linklabel = 'folderdata'
folderdata_relpath = Path('relative_path')
folderdata_test_path = folderdata_linklabel / folderdata_relpath
arraydata_linklabel = 'arraydata'
node_metadata_file = '.aiida_node_metadata.yaml'


# Only test top-level actions, like path and README creation
# Other things tested via `_mirror_workflow` and `_mirror_calculation`
@pytest.mark.usefixtures('aiida_profile_clean')
def test_mirror(generate_calculation_node_io, generate_workchain_node_io, tmp_path):
    from aiida.tools.archive.exceptions import ExportValidationError

    tree_ = {
        'wc-mirror-test-io': [
            '.aiida_mirror_log.json',
            '.aiida_mirror_safeguard',
            '.aiida_node_metadata.yaml',
            {
                '01-sub_workflow-8': [
                    '.aiida_node_metadata.yaml',
                    {
                        '01-calculation-9': [
                            '.aiida_node_metadata.yaml',
                            {'inputs': ['file.txt']},
                            {
                                'node_inputs': [
                                    {'arraydata': ['default.npy']},
                                    {'folderdata': [{'relative_path': ['file.txt']}]},
                                    {'singlefile': ['file.txt']},
                                ]
                            },
                        ]
                    },
                    {
                        '02-calculation-10': [
                            '.aiida_node_metadata.yaml',
                            {'inputs': ['file.txt']},
                            {
                                'node_inputs': [
                                    {'arraydata': ['default.npy']},
                                    {'folderdata': [{'relative_path': ['file.txt']}]},
                                    {'singlefile': ['file.txt']},
                                ]
                            },
                        ]
                    },
                ]
            },
        ]
    }

    sub_path = Path('wc-mirror-test-io')
    mirror_parent_path = tmp_path / sub_path
    mirror_paths = MirrorPaths.from_path(mirror_parent_path)
    # Don't attach outputs, as it would require storing the calculation_node and then it cannot be used in the workchain
    cj_nodes = [generate_calculation_node_io(attach_outputs=False), generate_calculation_node_io(attach_outputs=False)]
    wc_node = generate_workchain_node_io(cj_nodes=cj_nodes)
    process_mirror_inst = ProcessMirror(process_node=wc_node, mirror_paths=mirror_paths)

    # Raises if ProcessNode not sealed
    with pytest.raises(ExportValidationError):
        _ = process_mirror_inst.mirror()

    wc_node.seal()
    process_mirror_inst.mirror_mode = MirrorMode.OVERWRITE
    _ = process_mirror_inst.mirror()

    compare_tree(expected=tree_, base_path=tmp_path)
    assert mirror_parent_path.is_dir()


@pytest.mark.usefixtures('aiida_profile_clean')
def test_mirror_workflow(generate_calculation_node_io, generate_workchain_node_io, tmp_path):
    # Need to generate parent path for mirroring,
    # as I don't want the sub-workchains to be mirrored directly into `tmp_path`
    mirror_parent_path = tmp_path / 'wc-workflow_mirror-test-io'
    # Don't attach outputs, as it would require storing the calculation_node and then it cannot be used in the workchain
    cj_nodes = [generate_calculation_node_io(attach_outputs=False), generate_calculation_node_io(attach_outputs=False)]
    wc_node = generate_workchain_node_io(cj_nodes=cj_nodes)
    process_mirror_inst = ProcessMirror(process_node=wc_node, mirror_paths=MirrorPaths.from_path(mirror_parent_path))
    process_mirror_inst._mirror_workflow(workflow_node=wc_node, output_path=mirror_parent_path)

    base_path = Path('01-sub_workflow-8/01-calculation-9')
    input_path = base_path / 'inputs/file.txt'
    singlefiledata_path = base_path / 'node_inputs/singlefile/file.txt'
    folderdata_path = base_path / 'node_inputs/folderdata/relative_path/file.txt'
    arraydata_path = base_path / 'node_inputs/arraydata/default.npy'
    node_metadata_paths = [
        node_metadata_file,
        f'01-sub_workflow-8/{node_metadata_file}',
        f'{base_path}/{node_metadata_file}',
        f'01-sub_workflow-8/02-calculation-10/{node_metadata_file}',
    ]

    expected_files = [input_path, singlefiledata_path, folderdata_path, arraydata_path, *node_metadata_paths]
    expected_files = [mirror_parent_path / expected_file for expected_file in expected_files]

    assert all([expected_file.is_file() for expected_file in expected_files])

    # Flat mirroring
    mirror_parent_path = tmp_path / 'wc-mirror-test-io-flat'
    process_mirror_config = ProcessMirrorConfig(flat=True)
    process_mirror_inst = ProcessMirror(config=process_mirror_config, process_node=wc_node)
    process_mirror_inst._mirror_workflow(workflow_node=wc_node, output_path=mirror_parent_path)

    input_path = base_path / 'file.txt'
    arraydata_path = base_path / 'default.npy'
    folderdata_path = base_path / 'relative_path/file.txt'
    node_metadata_paths = [
        node_metadata_file,
        f'01-sub_workflow-8/{node_metadata_file}',
        f'{base_path}/{node_metadata_file}',
        f'01-sub_workflow-8/02-calculation-10/{node_metadata_file}',
    ]

    expected_files = [input_path, folderdata_path, arraydata_path, *node_metadata_paths]
    expected_files = [mirror_parent_path / expected_file for expected_file in expected_files]

    assert all([expected_file.is_file() for expected_file in expected_files])


@pytest.mark.usefixtures('aiida_profile_clean')
def test_mirror_multiply_add(tmp_path, generate_workchain_multiply_add):
    mirror_parent_path = tmp_path / 'wc-mirror-test-multiply-add'
    mirror_paths = MirrorPaths.from_path(mirror_parent_path)
    wc_node = generate_workchain_multiply_add()
    process_mirror_inst = ProcessMirror(mirror_paths=mirror_paths, process_node=wc_node)
    process_mirror_inst.mirror()

    arithmetic_add_path = mirror_parent_path / '02-ArithmeticAddCalculation-8'
    multiply_path = mirror_parent_path / '01-multiply-6'

    input_files = [
        '_aiidasubmit.sh',
        'aiida.in',
        '.aiida/job_tmpl.json',
        '.aiida/calcinfo.json',
    ]
    output_files = ['_scheduler-stderr.txt', '_scheduler-stdout.txt', 'aiida.out']

    input_files = [arithmetic_add_path / inputs_relpath / input_file for input_file in input_files]
    input_files += [multiply_path / inputs_relpath / 'source_file']
    output_files = [arithmetic_add_path / outputs_relpath / output_file for output_file in output_files]

    # No node_inputs contained in MultiplyAddWorkChain
    assert all([input_file.is_file() for input_file in input_files])
    assert all([output_file.is_file() for output_file in output_files])

    # Flat mirroring
    mirror_parent_path = tmp_path / 'wc-mirror-test-multiply-add-flat'
    mirror_paths_flat = MirrorPaths.from_path(mirror_parent_path)
    process_mirror_config = ProcessMirrorConfig(flat=True)
    process_mirror_inst = ProcessMirror(
        mirror_paths=mirror_paths_flat, config=process_mirror_config, process_node=wc_node
    )
    process_mirror_inst.mirror()

    multiply_file = mirror_parent_path / '01-multiply-6' / 'source_file'
    arithmetic_add_files = [
        '_aiidasubmit.sh',
        'aiida.in',
        '.aiida/job_tmpl.json',
        '.aiida/calcinfo.json',
        '_scheduler-stderr.txt',
        '_scheduler-stdout.txt',
        'aiida.out',
    ]
    arithmetic_add_files = [
        mirror_parent_path / '02-ArithmeticAddCalculation-8' / arithmetic_add_file
        for arithmetic_add_file in arithmetic_add_files
    ]

    assert multiply_file.is_file()
    assert all([expected_file.is_file() for expected_file in arithmetic_add_files])


# Tests for mirror_calculation method
@pytest.mark.usefixtures('aiida_profile_clean')
def test_mirror_calculation_node(tmp_path, generate_calculation_node_io):
    # Checking the actual content should be handled by `test_copy_tree`

    # Normal mirroring -> node_inputs and not flat; no paths provided
    mirror_parent_path = tmp_path / 'cj-mirror-test-io'
    mirror_paths = MirrorPaths.from_path(mirror_parent_path)
    process_mirror_config = ProcessMirrorConfig(include_outputs=True)
    calculation_node = generate_calculation_node_io()
    process_mirror_inst = ProcessMirror(
        mirror_paths=mirror_paths, config=process_mirror_config, process_node=calculation_node
    )
    process_mirror_inst._mirror_calculation(calculation_node=calculation_node, output_path=mirror_parent_path)

    assert (mirror_parent_path / inputs_relpath / filename).is_file()
    assert (mirror_parent_path / node_inputs_relpath / singlefiledata_linklabel / filename).is_file()
    assert (mirror_parent_path / node_inputs_relpath / folderdata_test_path / filename).is_file()
    assert (mirror_parent_path / node_inputs_relpath / arraydata_linklabel / 'default.npy').is_file()

    assert (mirror_parent_path / node_outputs_relpath / singlefiledata_linklabel / filename).is_file()
    assert (mirror_parent_path / node_outputs_relpath / folderdata_test_path / filename).is_file()

    # Check contents once
    with open(mirror_parent_path / inputs_relpath / filename, 'r') as handle:
        assert handle.read() == filecontent
    with open(mirror_parent_path / node_inputs_relpath / singlefiledata_linklabel / filename) as handle:
        assert handle.read() == filecontent
    with open(mirror_parent_path / node_inputs_relpath / folderdata_test_path / filename) as handle:
        assert handle.read() == filecontent
    with open(mirror_parent_path / node_outputs_relpath / singlefiledata_linklabel / filename) as handle:
        assert handle.read() == filecontent
    with open(mirror_parent_path / node_outputs_relpath / folderdata_test_path / filename) as handle:
        assert handle.read() == filecontent


@pytest.mark.usefixtures('aiida_profile_clean')
def test_mirror_calculation_flat(tmp_path, generate_calculation_node_io):
    # Flat mirroring -> no paths provided -> Default paths should not be existent.
    # Internal FolderData structure retained.
    mirror_parent_path = tmp_path / 'cj-mirror-test-custom'
    mirror_paths = MirrorPaths.from_path(mirror_parent_path)
    process_mirror_config = ProcessMirrorConfig(flat=True)
    calculation_node = generate_calculation_node_io()
    process_mirror_inst = ProcessMirror(
        mirror_paths=mirror_paths, process_node=calculation_node, config=process_mirror_config
    )
    process_mirror_inst._mirror_calculation(calculation_node=calculation_node, output_path=mirror_parent_path)

    # Here, the same file will be written by inputs and node_outputs and node_inputs
    # So it should only be present once in the parent mirror directory
    assert not (mirror_parent_path / inputs_relpath).is_dir()
    assert not (mirror_parent_path / node_inputs_relpath).is_dir()
    assert not (mirror_parent_path / outputs_relpath).is_dir()
    assert (mirror_parent_path / filename).is_file()
    assert (mirror_parent_path / 'default.npy').is_file()
    assert (mirror_parent_path / folderdata_relpath / filename).is_file()


# Here, in principle, test only non-default arguments, as defaults tested above
@pytest.mark.usefixtures('aiida_profile_clean')
def test_mirror_calculation_overwr_incr(tmp_path, generate_calculation_node_io):
    """Tests the Processmirror_inst for the overwrite and incremental option."""
    mirror_parent_path = tmp_path / 'cj-mirror-test-overwrite'
    mirror_paths = MirrorPaths.from_path(mirror_parent_path)
    # base_mirror_config = MirrorMode(overwrite=False, incremental=False)
    calculation_node = generate_calculation_node_io()
    calculation_node.seal()
    process_mirror_inst = ProcessMirror(mirror_paths=mirror_paths, process_node=calculation_node)
    # Create safeguard file to mock existing mirror directory
    mirror_parent_path.mkdir()
    # we create safeguard file so the mirroring works
    (mirror_parent_path / '.aiida_mirror_safeguard').touch()
    # With overwrite option true no error is raised and the mirroring can run through.
    process_mirror_inst = ProcessMirror(
        mirror_mode=MirrorMode.OVERWRITE, mirror_paths=mirror_paths, process_node=calculation_node
    )
    process_mirror_inst._mirror_calculation(calculation_node=calculation_node, output_path=mirror_parent_path)
    assert (mirror_parent_path / inputs_relpath / filename).is_file()

    shutil.rmtree(mirror_parent_path)

    # Incremental also does work
    mirror_parent_path.mkdir()
    (mirror_parent_path / '.aiida_mirror_safeguard').touch()
    process_mirror_inst = ProcessMirror(mirror_paths=mirror_paths, process_node=calculation_node)
    process_mirror_inst._mirror_calculation(calculation_node=calculation_node, output_path=mirror_parent_path)
    assert (mirror_parent_path / inputs_relpath / filename).is_file()


# With both inputs and outputs being mirrored is the standard test case above, so only test without inputs here
@pytest.mark.usefixtures('aiida_profile_clean')
def test_mirror_calculation_no_inputs(tmp_path, generate_calculation_node_io):
    mirror_parent_path = tmp_path / 'cj-mirror-test-noinputs'
    mirror_paths = MirrorPaths.from_path(mirror_parent_path)
    config = ProcessMirrorConfig(include_inputs=False)
    calculation_node = generate_calculation_node_io()
    process_mirror_inst = ProcessMirror(config=config, mirror_paths=mirror_paths, process_node=calculation_node)
    process_mirror_inst._mirror_calculation(calculation_node=calculation_node, output_path=mirror_parent_path)
    assert not (mirror_parent_path / node_inputs_relpath).is_dir()


@pytest.mark.usefixtures('aiida_profile_clean')
def test_mirror_calculation_add(tmp_path, generate_calculation_node_add):
    mirror_parent_path = tmp_path / 'cj-mirror-test-add'
    mirror_paths = MirrorPaths.from_path(mirror_parent_path)

    calculation_node_add = generate_calculation_node_add()
    process_mirror_inst = ProcessMirror(mirror_paths=mirror_paths, process_node=calculation_node_add)
    process_mirror_inst._mirror_calculation(calculation_node=calculation_node_add, output_path=mirror_parent_path)

    input_files = ['_aiidasubmit.sh', 'aiida.in', '.aiida/job_tmpl.json', '.aiida/calcinfo.json']
    output_files = ['_scheduler-stderr.txt', '_scheduler-stdout.txt', 'aiida.out']
    input_files = [mirror_parent_path / inputs_relpath / input_file for input_file in input_files]
    output_files = [mirror_parent_path / outputs_relpath / output_file for output_file in output_files]

    assert all([input_file.is_file() for input_file in input_files])
    assert all([output_file.is_file() for output_file in output_files])


def test_generate_calculation_io_mapping():
    calculation_io_mapping = ProcessMirror._generate_calculation_io_mapping()
    assert calculation_io_mapping.repository == 'inputs'
    assert calculation_io_mapping.retrieved == 'outputs'
    assert calculation_io_mapping.inputs == 'node_inputs'
    assert calculation_io_mapping.outputs == 'node_outputs'

    calculation_io_mapping = ProcessMirror._generate_calculation_io_mapping(io_mirror_paths=custom_mirror_paths)
    assert calculation_io_mapping.repository == 'inputs_'
    assert calculation_io_mapping.retrieved == 'outputs_'
    assert calculation_io_mapping.inputs == 'node_inputs_'
    assert calculation_io_mapping.outputs == 'node_outputs_'


@pytest.mark.usefixtures('aiida_profile_clean')
def test_generate_child_node_label(
    generate_workchain_multiply_add, generate_calculation_node_io, generate_workchain_node_io
):
    # Check with manually constructed, more complex workchain
    cj_node = generate_calculation_node_io(attach_outputs=False)
    wc_node = generate_workchain_node_io(cj_nodes=[cj_node])
    wc_output_triples = wc_node.base.links.get_outgoing().all()
    sub_wc_node = wc_output_triples[0].node

    output_triples = wc_output_triples + sub_wc_node.base.links.get_outgoing().all()
    # Sort by mtime here, not ctime, as I'm actually creating the CalculationNode first.
    output_triples = sorted(output_triples, key=lambda link_triple: link_triple.node.mtime)

    output_paths = sorted(
        [
            ProcessMirror._generate_child_node_label(index, output_node)
            for index, output_node in enumerate(output_triples)
        ]
    )
    assert output_paths == ['00-sub_workflow-5', '01-calculation-6']

    # Check with multiply_add workchain node
    multiply_add_node = generate_workchain_multiply_add()
    output_triples = multiply_add_node.base.links.get_outgoing().all()
    # Sort by ctime here, not mtime, as I'm generating the WorkChain normally
    output_triples = sorted(output_triples, key=lambda link_triple: link_triple.node.ctime)
    output_paths = sorted(
        [ProcessMirror._generate_child_node_label(_, output_node) for _, output_node in enumerate(output_triples)]
    )
    print(output_paths)
    assert output_paths == ['00-multiply-12', '01-ArithmeticAddCalculation-14', '02-result-17']


def test_write_node_yaml(generate_calculation_node_io, tmp_path, generate_workchain_multiply_add):
    sub_path = 'add'
    cj_node = generate_calculation_node_io(attach_outputs=False)
    process_mirror_inst = ProcessMirror(process_node=cj_node, mirror_paths=MirrorPaths(parent=tmp_path, child=sub_path))
    process_mirror_inst._write_node_yaml(process_node=cj_node, output_path=tmp_path)

    assert (tmp_path / node_metadata_file).is_file()

    # Test with multiply_add
    sub_path = 'multiply-add'
    wc_node = generate_workchain_multiply_add()
    mirror_paths = MirrorPaths(parent=tmp_path, child=sub_path)
    process_mirror_inst = ProcessMirror(process_node=wc_node, mirror_paths=mirror_paths)
    process_mirror_inst._write_node_yaml(process_node=wc_node, output_path=tmp_path)

    assert (tmp_path / node_metadata_file).is_file()

    # Open the mirrored YAML file and read its contents
    with open(tmp_path / node_metadata_file, 'r') as mirrored_file:
        contents = mirrored_file.read()

    # Check if contents as expected
    assert 'Node data:' in contents
    assert 'User data:' in contents
    # Computer is None for the locally run MultiplyAdd
    assert 'Computer data:' not in contents
    assert 'Node attributes:' in contents
    assert 'Node extras:' in contents

    config = ProcessMirrorConfig(include_attributes=False, include_extras=False)
    process_mirror_inst = ProcessMirror(process_node=wc_node, mirror_paths=mirror_paths, config=config)

    (tmp_path / node_metadata_file).unlink()
    process_mirror_inst._write_node_yaml(process_node=wc_node, output_path=tmp_path)

    # Open the mirrored YAML file and read its contents
    with open(tmp_path / node_metadata_file, 'r') as mirrored_file:
        contents = mirrored_file.read()

    # Check if contents as expected -> No attributes and extras
    assert 'Node data:' in contents
    assert 'User data:' in contents
    # Computer is None for the locally run MultiplyAdd
    assert 'Computer data:' not in contents
    assert 'Node attributes:' not in contents
    assert 'Node extras:' not in contents


def test_generate_parent_readme(tmp_path, generate_workchain_multiply_add):
    wc_node = generate_workchain_multiply_add()
    sub_path = 'readme'
    process_mirror_inst = ProcessMirror(mirror_paths=MirrorPaths(parent=tmp_path, child=sub_path), process_node=wc_node)

    (tmp_path / sub_path).mkdir(parents=True, exist_ok=True)
    process_mirror_inst._generate_readme()

    assert (tmp_path / sub_path / 'README.md').is_file()

    with open(tmp_path / sub_path / 'README.md', 'r') as mirrored_file:
        contents = mirrored_file.read()

    assert 'This directory contains' in contents
    assert '`MultiplyAddWorkChain' in contents
    assert 'ArithmeticAddCalculation' in contents
    # Check for outputs of `verdi process status/report/show`
    assert 'Finished [0] [3:result]' in contents
    assert 'Property     Value' in contents
    assert 'There are 1 log messages for this calculation' in contents

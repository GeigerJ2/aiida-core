###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################
"""Tests for the dumping of profile data to disk."""

import pytest

from aiida.tools.dumping.config import DumpConfig
from aiida.tools.dumping import GroupDumper
from aiida.tools.dumping.utils.tree import compare_tree

# TODO: Also verify the log updates

profile_dump_label = 'profile-dump'
add_group_label = 'add-group'
multiply_add_group_label = 'multiply-add-group'

tree_profile_group_add = {
        '.aiida_dump_log.json',
        '.aiida_dump_safeguard',
        {
            'groups': [
                {
                    add_group_label: [
                        '.aiida_dump_safeguard',
                        {
                            'calculations': [
                                {
                                    'ArithmeticAddCalculation-4': [
                                        '.aiida_dump_safeguard',
                                        '.aiida_node_metadata.yaml',
                                        {
                                            'inputs': [
                                                '_aiidasubmit.sh',
                                                'aiida.in',
                                                {
                                                    '.aiida': [
                                                        'calcinfo.json',
                                                        'job_tmpl.json',
                                                    ]
                                                },
                                            ]
                                        },
                                        {'node_inputs': []},
                                        {
                                            'outputs': [
                                                '_scheduler-stderr.txt',
                                                '_scheduler-stdout.txt',
                                                'aiida.out',
                                            ]
                                        },
                                    ]
                                }
                            ]
                        },
                    ]
                }
            ]
        },
}

tree_profile_group_multiply_add = {
    profile_dump_label: [
        '.aiida_dump_log.json',
        '.aiida_dump_safeguard',
        {
            'groups': [
                {
                    multiply_add_group_label: [
                        '.aiida_dump_safeguard',
                        {
                            'workflows': [
                                {
                                    'MultiplyAddWorkChain-5': [
                                        '.aiida_dump_safeguard',
                                        '.aiida_node_metadata.yaml',
                                        {
                                            '01-multiply-6': [
                                                '.aiida_node_metadata.yaml',
                                                '.aiida_dump_safeguard',
                                                {'inputs': ['source_file']},
                                                {'node_inputs': []},
                                            ]
                                        },
                                        {
                                            '02-ArithmeticAddCalculation-8': [
                                                '.aiida_node_metadata.yaml',
                                                '.aiida_dump_safeguard',
                                                {
                                                    'inputs': [
                                                        '_aiidasubmit.sh',
                                                        'aiida.in',
                                                        {
                                                            '.aiida': [
                                                                'calcinfo.json',
                                                                'job_tmpl.json',
                                                            ]
                                                        },
                                                    ]
                                                },
                                                {'node_inputs': []},
                                                {
                                                    'outputs': [
                                                        '_scheduler-stderr.txt',
                                                        '_scheduler-stdout.txt',
                                                        'aiida.out',
                                                    ]
                                                },
                                            ]
                                        },
                                    ]
                                }
                            ]
                        },
                    ]
                }
            ]
        },
    ]
}

tree_profile_groups_add_multiply_add = {
    profile_dump_label: [
        '.aiida_dump_log.json',
        '.aiida_dump_safeguard',
        {
            'groups': [
                {
                    add_group_label: [
                        '.aiida_dump_safeguard',
                        {
                            'calculations': [
                                {
                                    'ArithmeticAddCalculation-4': [
                                        '.aiida_dump_safeguard',
                                        '.aiida_node_metadata.yaml',
                                        {
                                            'inputs': [
                                                '_aiidasubmit.sh',
                                                'aiida.in',
                                                {
                                                    '.aiida': [
                                                        'calcinfo.json',
                                                        'job_tmpl.json',
                                                    ]
                                                },
                                            ]
                                        },
                                        {'node_inputs': []},
                                        {
                                            'outputs': [
                                                '_scheduler-stderr.txt',
                                                '_scheduler-stdout.txt',
                                                'aiida.out',
                                            ]
                                        },
                                    ]
                                }
                            ]
                        },
                    ]
                },
                {
                    multiply_add_group_label: [
                        '.aiida_dump_safeguard',
                        {
                            'workflows': [
                                {
                                    'MultiplyAddWorkChain-12': [
                                        '.aiida_dump_safeguard',
                                        '.aiida_node_metadata.yaml',
                                        {
                                            '01-multiply-13': [
                                                '.aiida_node_metadata.yaml',
                                                '.aiida_dump_safeguard',
                                                {'inputs': ['source_file']},
                                                {'node_inputs': []},
                                            ]
                                        },
                                        {
                                            '02-ArithmeticAddCalculation-15': [
                                                '.aiida_node_metadata.yaml',
                                                '.aiida_dump_safeguard',
                                                {
                                                    'inputs': [
                                                        '_aiidasubmit.sh',
                                                        'aiida.in',
                                                        {
                                                            '.aiida': [
                                                                'calcinfo.json',
                                                                'job_tmpl.json',
                                                            ]
                                                        },
                                                    ]
                                                },
                                                {'node_inputs': []},
                                                {
                                                    'outputs': [
                                                        '_scheduler-stderr.txt',
                                                        '_scheduler-stdout.txt',
                                                        'aiida.out',
                                                    ]
                                                },
                                            ]
                                        },
                                    ]
                                }
                            ]
                        },
                    ]
                },
            ]
        },
    ]
}

tree_profile_groups_multiply_add_add = {
    profile_dump_label: [
        '.aiida_dump_log.json',
        '.aiida_dump_safeguard',
        {
            'groups': [
                {
                    add_group_label: [
                        '.aiida_dump_safeguard',
                        {
                            'calculations': [
                                {
                                    'ArithmeticAddCalculation-4': [
                                        '.aiida_dump_safeguard',
                                        '.aiida_node_metadata.yaml',
                                        {
                                            'inputs': [
                                                '_aiidasubmit.sh',
                                                'aiida.in',
                                                {
                                                    '.aiida': [
                                                        'calcinfo.json',
                                                        'job_tmpl.json',
                                                    ]
                                                },
                                            ]
                                        },
                                        {'node_inputs': []},
                                        {
                                            'outputs': [
                                                '_scheduler-stderr.txt',
                                                '_scheduler-stdout.txt',
                                                'aiida.out',
                                            ]
                                        },
                                    ]
                                }
                            ]
                        },
                    ]
                },
                {
                    multiply_add_group_label: [
                        '.aiida_dump_safeguard',
                        {
                            'workflows': [
                                {
                                    'MultiplyAddWorkChain-12': [
                                        '.aiida_dump_safeguard',
                                        '.aiida_node_metadata.yaml',
                                        {
                                            '01-multiply-13': [
                                                '.aiida_node_metadata.yaml',
                                                '.aiida_dump_safeguard',
                                                {'inputs': ['source_file']},
                                                {'node_inputs': []},
                                            ]
                                        },
                                        {
                                            '02-ArithmeticAddCalculation-15': [
                                                '.aiida_node_metadata.yaml',
                                                '.aiida_dump_safeguard',
                                                {
                                                    'inputs': [
                                                        '_aiidasubmit.sh',
                                                        'aiida.in',
                                                        {
                                                            '.aiida': [
                                                                'calcinfo.json',
                                                                'job_tmpl.json',
                                                            ]
                                                        },
                                                    ]
                                                },
                                                {'node_inputs': []},
                                                {
                                                    'outputs': [
                                                        '_scheduler-stderr.txt',
                                                        '_scheduler-stdout.txt',
                                                        'aiida.out',
                                                    ]
                                                },
                                            ]
                                        },
                                    ]
                                }
                            ]
                        },
                    ]
                },
            ]
        },
    ]
}

tree_profile_no_organize_by_groups = {
    profile_dump_label: [
        '.aiida_dump_log.json',
        '.aiida_dump_safeguard',
        {
            'calculations': [
                {
                    'ArithmeticAddCalculation-4': [
                        '.aiida_dump_safeguard',
                        '.aiida_node_metadata.yaml',
                        {
                            'inputs': [
                                '_aiidasubmit.sh',
                                'aiida.in',
                                {'.aiida': ['calcinfo.json', 'job_tmpl.json']},
                            ]
                        },
                        {'node_inputs': []},
                        {
                            'outputs': [
                                '_scheduler-stderr.txt',
                                '_scheduler-stdout.txt',
                                'aiida.out',
                            ]
                        },
                    ]
                }
            ]
        },
        {
            'workflows': [
                {
                    'MultiplyAddWorkChain-12': [
                        '.aiida_dump_safeguard',
                        '.aiida_node_metadata.yaml',
                        {
                            '01-multiply-13': [
                                '.aiida_node_metadata.yaml',
                                '.aiida_dump_safeguard',
                                {'inputs': ['source_file']},
                                {'node_inputs': []},
                            ]
                        },
                        {
                            '02-ArithmeticAddCalculation-15': [
                                '.aiida_node_metadata.yaml',
                                '.aiida_dump_safeguard',
                                {
                                    'inputs': [
                                        '_aiidasubmit.sh',
                                        'aiida.in',
                                        {'.aiida': ['calcinfo.json', 'job_tmpl.json']},
                                    ]
                                },
                                {'node_inputs': []},
                                {
                                    'outputs': [
                                        '_scheduler-stderr.txt',
                                        '_scheduler-stdout.txt',
                                        'aiida.out',
                                    ]
                                },
                            ]
                        },
                    ]
                }
            ]
        },
    ]
}

tree_profile_also_ungrouped = {
    profile_dump_label: [
        '.aiida_dump_log.json',
        '.aiida_dump_safeguard',
        {
            'groups': [
                {
                    add_group_label: [
                        '.aiida_dump_safeguard',
                        {
                            'calculations': [
                                {
                                    'ArithmeticAddCalculation-4': [
                                        '.aiida_dump_safeguard',
                                        '.aiida_node_metadata.yaml',
                                        {
                                            'inputs': [
                                                '_aiidasubmit.sh',
                                                'aiida.in',
                                                {
                                                    '.aiida': [
                                                        'calcinfo.json',
                                                        'job_tmpl.json',
                                                    ]
                                                },
                                            ]
                                        },
                                        {'node_inputs': []},
                                        {
                                            'outputs': [
                                                '_scheduler-stderr.txt',
                                                '_scheduler-stdout.txt',
                                                'aiida.out',
                                            ]
                                        },
                                    ]
                                }
                            ]
                        },
                    ]
                },
                {
                    multiply_add_group_label: [
                        '.aiida_dump_safeguard',
                        {
                            'workflows': [
                                {
                                    'MultiplyAddWorkChain-12': [
                                        '.aiida_dump_safeguard',
                                        '.aiida_node_metadata.yaml',
                                        {
                                            '01-multiply-13': [
                                                '.aiida_node_metadata.yaml',
                                                '.aiida_dump_safeguard',
                                                {'inputs': ['source_file']},
                                                {'node_inputs': []},
                                            ]
                                        },
                                        {
                                            '02-ArithmeticAddCalculation-15': [
                                                '.aiida_node_metadata.yaml',
                                                '.aiida_dump_safeguard',
                                                {
                                                    'inputs': [
                                                        '_aiidasubmit.sh',
                                                        'aiida.in',
                                                        {
                                                            '.aiida': [
                                                                'calcinfo.json',
                                                                'job_tmpl.json',
                                                            ]
                                                        },
                                                    ]
                                                },
                                                {'node_inputs': []},
                                                {
                                                    'outputs': [
                                                        '_scheduler-stderr.txt',
                                                        '_scheduler-stdout.txt',
                                                        'aiida.out',
                                                    ]
                                                },
                                            ]
                                        },
                                    ]
                                }
                            ]
                        },
                    ]
                },
            ]
        },
        {
            'ungrouped': [
                # TODO: Question?
                '.aiida_dump_safeguard',
                {
                    'calculations': [
                        {
                            'ArithmeticAddCalculation-22': [
                                '.aiida_dump_safeguard',
                                '.aiida_node_metadata.yaml',
                                {
                                    'inputs': [
                                        '_aiidasubmit.sh',
                                        'aiida.in',
                                        {
                                            '.aiida': [
                                                'calcinfo.json',
                                                'job_tmpl.json',
                                            ]
                                        },
                                    ]
                                },
                                {'node_inputs': []},
                                {
                                    'outputs': [
                                        '_scheduler-stderr.txt',
                                        '_scheduler-stdout.txt',
                                        'aiida.out',
                                    ]
                                },
                            ]
                        }
                    ]
                },
                {
                    'workflows': [
                        {
                            'MultiplyAddWorkChain-30': [
                                '.aiida_dump_safeguard',
                                '.aiida_node_metadata.yaml',
                                {
                                    '01-multiply-31': [
                                        '.aiida_node_metadata.yaml',
                                        '.aiida_dump_safeguard',
                                        {'inputs': ['source_file']},
                                        {'node_inputs': []},
                                    ]
                                },
                                {
                                    '02-ArithmeticAddCalculation-33': [
                                        '.aiida_node_metadata.yaml',
                                        '.aiida_dump_safeguard',
                                        {
                                            'inputs': [
                                                '_aiidasubmit.sh',
                                                'aiida.in',
                                                {
                                                    '.aiida': [
                                                        'calcinfo.json',
                                                        'job_tmpl.json',
                                                    ]
                                                },
                                            ]
                                        },
                                        {'node_inputs': []},
                                        {
                                            'outputs': [
                                                '_scheduler-stderr.txt',
                                                '_scheduler-stdout.txt',
                                                'aiida.out',
                                            ]
                                        },
                                    ]
                                },
                            ]
                        }
                    ]
                },
            ]
        },
    ]
}

tree_profile_no_only_top_level_calcs = {
    'profile-dump': [
        '.aiida_dump_log.json',
        '.aiida_dump_safeguard',
        {
            'groups': [
                {
                    add_group_label: [
                        '.aiida_dump_safeguard',
                        {
                            'calculations': [
                                {
                                    'ArithmeticAddCalculation-4': [
                                        '.aiida_dump_safeguard',
                                        '.aiida_node_metadata.yaml',
                                        {
                                            'inputs': [
                                                '_aiidasubmit.sh',
                                                'aiida.in',
                                                {
                                                    '.aiida': [
                                                        'calcinfo.json',
                                                        'job_tmpl.json',
                                                    ]
                                                },
                                            ]
                                        },
                                        {'node_inputs': []},
                                        {
                                            'outputs': [
                                                '_scheduler-stderr.txt',
                                                '_scheduler-stdout.txt',
                                                'aiida.out',
                                            ]
                                        },
                                    ]
                                }
                            ]
                        },
                    ]
                },
                {
                    multiply_add_group_label: [
                        '.aiida_dump_safeguard',
                        {
                            'calculations': [
                                {
                                    'ArithmeticAddCalculation-15': [
                                        '.aiida_dump_safeguard',
                                        '.aiida_node_metadata.yaml',
                                        {
                                            'inputs': [
                                                '_aiidasubmit.sh',
                                                'aiida.in',
                                                {
                                                    '.aiida': [
                                                        'calcinfo.json',
                                                        'job_tmpl.json',
                                                    ]
                                                },
                                            ]
                                        },
                                        {'node_inputs': []},
                                        {
                                            'outputs': [
                                                '_scheduler-stderr.txt',
                                                '_scheduler-stdout.txt',
                                                'aiida.out',
                                            ]
                                        },
                                    ]
                                },
                                {
                                    'multiply-13': [
                                        '.aiida_dump_safeguard',
                                        '.aiida_node_metadata.yaml',
                                        {'inputs': ['source_file']},
                                        {'node_inputs': []},
                                    ]
                                },
                            ]
                        },
                        {
                            'workflows': [
                                {
                                    'MultiplyAddWorkChain-12': [
                                        '.aiida_dump_safeguard',
                                        '.aiida_node_metadata.yaml',
                                        {
                                            '01-multiply-13': [
                                                '.aiida_dump_safeguard',
                                                '.aiida_node_metadata.yaml',
                                                {'inputs': ['source_file']},
                                                {'node_inputs': []},
                                            ]
                                        },
                                        {
                                            '02-ArithmeticAddCalculation-15': [
                                                '.aiida_dump_safeguard',
                                                '.aiida_node_metadata.yaml',
                                                {
                                                    'inputs': [
                                                        '_aiidasubmit.sh',
                                                        'aiida.in',
                                                        {
                                                            '.aiida': [
                                                                'calcinfo.json',
                                                                'job_tmpl.json',
                                                            ]
                                                        },
                                                    ]
                                                },
                                                {'node_inputs': []},
                                                {
                                                    'outputs': [
                                                        '_scheduler-stderr.txt',
                                                        '_scheduler-stdout.txt',
                                                        'aiida.out',
                                                    ]
                                                },
                                            ]
                                        },
                                    ]
                                }
                            ]
                        },
                    ]
                },
            ]
        },
    ]
}

tree_profile_delete_missing_nodes = {
    'profile-dump': [
        '.aiida_dump_log.json',
        '.aiida_dump_safeguard',
        {
            'groups': [
                {add_group_label: ['.aiida_dump_safeguard', {'calculations': []}]},
                {
                    multiply_add_group_label: [
                        {
                            'workflows': [
                                {
                                    'MultiplyAddWorkChain-12': [
                                        '.aiida_dump_safeguard',
                                        '.aiida_node_metadata.yaml',
                                        {
                                            '01-multiply-13': [
                                                '.aiida_dump_safeguard',
                                                '.aiida_node_metadata.yaml',
                                                {'inputs': ['source_file']},
                                                {'node_inputs': []},
                                            ]
                                        },
                                        {
                                            '02-ArithmeticAddCalculation-15': [
                                                '.aiida_dump_safeguard',
                                                '.aiida_node_metadata.yaml',
                                                {
                                                    'inputs': [
                                                        '_aiidasubmit.sh',
                                                        'aiida.in',
                                                        {
                                                            '.aiida': [
                                                                'calcinfo.json',
                                                                'job_tmpl.json',
                                                            ]
                                                        },
                                                    ]
                                                },
                                                {'node_inputs': []},
                                                {
                                                    'outputs': [
                                                        '_scheduler-stderr.txt',
                                                        '_scheduler-stdout.txt',
                                                        'aiida.out',
                                                    ]
                                                },
                                            ]
                                        },
                                    ]
                                }
                            ]
                        },
                    ]
                },
            ]
        },
    ]
}

tree_profile_add_node_to_group = {
    profile_dump_label: [
        '.aiida_dump_log.json',
        '.aiida_dump_safeguard',
        {
            'groups': [
                {
                    add_group_label: [
                        '.aiida_dump_safeguard',
                        {
                            'calculations': [
                                {
                                    'ArithmeticAddCalculation-4': [
                                        '.aiida_dump_safeguard',
                                        '.aiida_node_metadata.yaml',
                                        {
                                            'inputs': [
                                                '_aiidasubmit.sh',
                                                'aiida.in',
                                                {
                                                    '.aiida': [
                                                        'calcinfo.json',
                                                        'job_tmpl.json',
                                                    ]
                                                },
                                            ]
                                        },
                                        {'node_inputs': []},
                                        {
                                            'outputs': [
                                                '_scheduler-stderr.txt',
                                                '_scheduler-stdout.txt',
                                                'aiida.out',
                                            ]
                                        },
                                    ]
                                },
                                {
                                    'ArithmeticAddCalculation-11': [
                                        '.aiida_dump_safeguard',
                                        '.aiida_node_metadata.yaml',
                                        {
                                            'inputs': [
                                                '_aiidasubmit.sh',
                                                'aiida.in',
                                                {
                                                    '.aiida': [
                                                        'calcinfo.json',
                                                        'job_tmpl.json',
                                                    ]
                                                },
                                            ]
                                        },
                                        {'node_inputs': []},
                                        {
                                            'outputs': [
                                                '_scheduler-stderr.txt',
                                                '_scheduler-stdout.txt',
                                                'aiida.out',
                                            ]
                                        },
                                    ]
                                },
                            ]
                        },
                    ]
                }
            ]
        },
    ]
}

tree_profile_group_add_copy = {
    profile_dump_label: [
        '.aiida_dump_log.json',
        '.aiida_dump_safeguard',
        {
            'groups': [
                {
                    add_group_label: [
                        '.aiida_dump_safeguard',
                        {
                            'calculations': [
                                {
                                    'ArithmeticAddCalculation-4': [
                                        '.aiida_dump_safeguard',
                                        '.aiida_node_metadata.yaml',
                                        {
                                            'inputs': [
                                                '_aiidasubmit.sh',
                                                'aiida.in',
                                                {
                                                    '.aiida': [
                                                        'calcinfo.json',
                                                        'job_tmpl.json',
                                                    ]
                                                },
                                            ]
                                        },
                                        {'node_inputs': []},
                                        {
                                            'outputs': [
                                                '_scheduler-stderr.txt',
                                                '_scheduler-stdout.txt',
                                                'aiida.out',
                                            ]
                                        },
                                    ]
                                }
                            ]
                        },
                    ]
                },
                {
                    'add-group-copy': [
                        '.aiida_dump_safeguard',
                        {
                            'calculations': [
                                {
                                    'ArithmeticAddCalculation-4': [
                                        '.aiida_dump_safeguard',
                                        '.aiida_node_metadata.yaml',
                                        {
                                            'inputs': [
                                                '_aiidasubmit.sh',
                                                'aiida.in',
                                                {
                                                    '.aiida': [
                                                        'calcinfo.json',
                                                        'job_tmpl.json',
                                                    ]
                                                },
                                            ]
                                        },
                                        {'node_inputs': []},
                                        {
                                            'outputs': [
                                                '_scheduler-stderr.txt',
                                                '_scheduler-stdout.txt',
                                                'aiida.out',
                                            ]
                                        },
                                    ]
                                }
                            ]
                        },
                    ]
                },
            ]
        },
    ]
}

tree_profile_sub_calc_group = {
    'profile-dump': [
        '.aiida_dump_log.json',
        '.aiida_dump_safeguard',
        {
            'groups': [
                {
                    'sub-calc-group': [
                        '.aiida_dump_safeguard',
                        {
                            'calculations': [
                                {
                                    'ArithmeticAddCalculation-8': [
                                        '.aiida_dump_safeguard',
                                        '.aiida_node_metadata.yaml',
                                        {
                                            'inputs': [
                                                '_aiidasubmit.sh',
                                                'aiida.in',
                                                {
                                                    '.aiida': [
                                                        'calcinfo.json',
                                                        'job_tmpl.json',
                                                    ]
                                                },
                                            ]
                                        },
                                        {'node_inputs': []},
                                        {
                                            'outputs': [
                                                '_scheduler-stderr.txt',
                                                '_scheduler-stdout.txt',
                                                'aiida.out',
                                            ]
                                        },
                                    ]
                                },
                                {
                                    'multiply-6': [
                                        '.aiida_dump_safeguard',
                                        '.aiida_node_metadata.yaml',
                                        {'inputs': ['source_file']},
                                        {'node_inputs': []},
                                    ]
                                },
                            ]
                        },
                    ]
                }
            ]
        },
    ]
}


# TODO: Test symlinking features: symlink_calcs and symlink between groups
class TestGroupDumper:
    @pytest.mark.usefixtures('aiida_profile_clean')
    def test_dump_add_group(self, tmp_path, setup_add_group):
        add_group = setup_add_group
        group_dumper = GroupDumper(output_path=tmp_path / profile_dump_label, group=add_group)
        group_dumper.dump()

        compare_tree(
            expected=tree_profile_group_add,
            base_path=tmp_path,
        )

    @pytest.mark.usefixtures('aiida_profile_clean')
    def test_dump_multiply_add_group(self, tmp_path, setup_multiply_add_group):
        setup_multiply_add_group
        group_dumper = ProfileDumper(output_path=tmp_path / profile_dump_label)
        group_dumper.dump()
        compare_tree(
            expected=tree_profile_group_multiply_add,
            base_path=tmp_path,
        )

    @pytest.mark.usefixtures('aiida_profile_clean')
    def test_dump_add_multiply_add_groups(self, tmp_path, setup_add_group, setup_multiply_add_group):
        setup_multiply_add_group
        setup_add_group
        group_dumper = ProfileDumper(output_path=tmp_path / profile_dump_label)
        group_dumper.dump()

        compare_tree(
            expected=tree_profile_groups_add_multiply_add,
            base_path=tmp_path,
        )

    @pytest.mark.usefixtures('aiida_profile_clean')
    def test_dump_multiply_add_add_groups(self, tmp_path, setup_add_group, setup_multiply_add_group):
        setup_add_group
        setup_multiply_add_group
        group_dumper = ProfileDumper(output_path=tmp_path / profile_dump_label)
        group_dumper.dump()

        compare_tree(
            expected=tree_profile_groups_multiply_add_add,
            base_path=tmp_path,
        )

    @pytest.mark.usefixtures('aiida_profile_clean')
    def test_dump_no_organize_by_groups(self, tmp_path, setup_add_group, setup_multiply_add_group):
        setup_add_group
        setup_multiply_add_group
        config = DumpConfig(organize_by_groups=False)
        group_dumper = ProfileDumper(output_path=tmp_path / profile_dump_label, config=config)
        group_dumper.dump()

        compare_tree(
            expected=tree_profile_no_organize_by_groups,
            base_path=tmp_path,
        )

    @pytest.mark.usefixtures('aiida_profile_clean')
    def test_dump_also_ungrouped(
        self,
        tmp_path,
        setup_add_group,
        setup_multiply_add_group,
        generate_calculation_node_add,
        generate_workchain_multiply_add,
    ):
        setup_add_group
        setup_multiply_add_group

        # Create additional ArithmeticAdd and MultiplyAdd nodes
        _ = generate_calculation_node_add()
        _ = generate_workchain_multiply_add()

        output_path = tmp_path / profile_dump_label

        group_dumper = ProfileDumper(
            output_path=output_path,
            config=DumpConfig(also_ungrouped=False),
        )
        group_dumper.dump()

        # Only the tree with the groups should be created
        compare_tree(
            expected=tree_profile_groups_add_multiply_add,
            base_path=tmp_path,
        )

        # Tree with extra nodes raises
        with pytest.raises(AssertionError):
            compare_tree(
                expected=tree_profile_also_ungrouped,
                base_path=tmp_path,
            )

        # Now, also dump the two additional nodes in incremental mode
        group_dumper = ProfileDumper(
            output_path=output_path,
            config=DumpConfig(also_ungrouped=True, filter_by_last_dump_time=False),
        )
        group_dumper.dump()

        # The previous tree should raise, as we now have additional directories
        with pytest.raises(AssertionError):
            compare_tree(
                expected=tree_profile_groups_add_multiply_add,
                base_path=tmp_path,
            )

        # Now compare with the actual tree
        compare_tree(
            expected=tree_profile_also_ungrouped,
            base_path=tmp_path,
        )

    @pytest.mark.usefixtures('aiida_profile_clean')
    def test_dump_add_node_to_group(self, tmp_path, setup_add_group, generate_calculation_node_add):
        add_group = setup_add_group
        add_node = generate_calculation_node_add()
        # setup_multiply_add_group

        output_path = output_path = tmp_path / profile_dump_label
        group_dumper = ProfileDumper(output_path=output_path)
        group_dumper.dump()

        # Additional add-node not dumped
        compare_tree(
            expected=tree_profile_group_add,
            base_path=tmp_path,
        )
        with pytest.raises(AssertionError):
            compare_tree(
                expected=tree_profile_add_node_to_group,
                base_path=tmp_path,
            )

        # add node to group
        add_group.add_nodes(add_node)

        group_dumper.dump()

        # Additional add-node included in the dump
        compare_tree(
            expected=tree_profile_add_node_to_group,
            base_path=tmp_path,
        )
        with pytest.raises(AssertionError):
            compare_tree(
                expected=tree_profile_group_add,
                base_path=tmp_path,
            )

    @pytest.mark.usefixtures('aiida_profile_clean')
    def test_dump_add_group_copy(
        self,
        tmp_path,
        setup_add_group,
    ):
        from aiida import orm

        add_group = setup_add_group
        dest_group, created = orm.Group.collection.get_or_create(label='add-group-copy')
        dest_group.add_nodes(list(add_group.nodes))

        output_path = output_path = tmp_path / profile_dump_label
        group_dumper = ProfileDumper(output_path=output_path)
        group_dumper.dump()

        # Duplicated group dumped
        compare_tree(
            expected=tree_profile_group_add_copy,
            base_path=tmp_path,
        )

    @pytest.mark.usefixtures('aiida_profile_clean')
    def test_dump_delete_group(self, tmp_path, setup_add_group, setup_multiply_add_group):
        # NOTE: Both, deleting only the group but not nodes, or deleting both have the same dump result
        from aiida import orm

        add_group = setup_add_group
        multiply_add_group = setup_multiply_add_group

        output_path = output_path = tmp_path / profile_dump_label
        group_dumper = ProfileDumper(output_path=output_path)
        group_dumper.dump()

        # Check that first dump is fine
        compare_tree(
            expected=tree_profile_groups_add_multiply_add,
            base_path=tmp_path,
        )
        # Delete group, but not nodes
        multiply_add_nodes = multiply_add_group.nodes
        orm.Group.collection.delete(multiply_add_group.pk)

        # TODO: Should I even need delete_missing here, or should this be the default?
        group_dumper = ProfileDumper(output_path=output_path, config=DumpConfig(delete_missing=True))

        group_dumper.dump()
        compare_tree(
            expected=tree_profile_group_add,
            base_path=tmp_path,
        )


    @pytest.mark.usefixtures('aiida_profile_clean')
    def test_dump_no_only_top_level_calcs(self, tmp_path, setup_add_group, setup_multiply_add_group):
        setup_multiply_add_group
        setup_add_group
        group_dumper = ProfileDumper(
            config=DumpConfig(only_top_level_calcs=False),
            output_path=tmp_path / profile_dump_label,
        )

        group_dumper.dump()
        compare_tree(
            expected=tree_profile_no_only_top_level_calcs,
            base_path=tmp_path,
        )

    @pytest.mark.usefixtures('aiida_profile_clean')
    def test_dump_sub_calc_group(self, tmp_path, generate_workchain_multiply_add):
        from aiida import orm

        wf_node = generate_workchain_multiply_add()
        sub_calcs = wf_node.called_descendants
        group, _ = orm.Group.collection.get_or_create(label='sub-calc-group')
        group.add_nodes(sub_calcs)

        output_path = output_path = tmp_path / profile_dump_label
        group_dumper = ProfileDumper(output_path=output_path)
        group_dumper.dump()

        # Additional add-node not dumped
        compare_tree(
            expected=tree_profile_sub_calc_group,
            base_path=tmp_path,
        )

    @pytest.mark.usefixtures("aiida_profile_clean")
    def test_dump_delete_missing_nodes(
        self,
        tmp_path,
        setup_add_group,
        setup_multiply_add_group,
    ):
        from aiida.tools.graph.deletions import delete_nodes

        add_group = setup_add_group
        setup_multiply_add_group

        output_path = tmp_path / profile_dump_label
        group_dumper = ProfileDumper(output_path=output_path)
        group_dumper.dump()

        # Full dump
        compare_tree(
            expected=tree_profile_groups_add_multiply_add,
            base_path=tmp_path,
        )
        with pytest.raises(AssertionError):
            compare_tree(
                expected=tree_profile_delete_missing_nodes,
                base_path=tmp_path,
            )

        add_node = add_group.nodes[0]

        _ = delete_nodes(pks=[add_node.pk], dry_run=False)

        group_dumper = ProfileDumper(
            output_path=output_path,
            config=DumpConfig(delete_missing=True),
        )
        group_dumper.dump()

    #     compare_tree(
    #         expected=tree_profile_delete_missing_nodes,
    #         base_path=tmp_path,
    #     )
    #     with pytest.raises(AssertionError):
    # compare_tree(
    #     expected=tree_profile_groups_add_multiply_add,
    #     base_path=tmp_path,
    # )

    # TODO: Make pass (could've just failed bc of the assert False)
    # @pytest.mark.usefixtures("aiida_profile_clean")
    # def test_dump_delete_missing_groups(
    #     self,
    #     tmp_path,
    #     setup_add_group,
    #     setup_multiply_add_group,
    # ):
    #     from aiida import orm

    #     add_group = setup_add_group
    #     setup_multiply_add_group
    #
    #     output_path = tmp_path / profile_dump_label
    #     group_dumper = ProfileDumper(output_path=output_path)
    #     group_dumper.dump()

    #     # Full dump
    #     compare_tree(
    #         expected=tree_profile_groups_add_multiply_add,
    #         base_path=tmp_path,
    #     )
    #     # with pytest.raises(AssertionError):
    #     #     compare_tree(
    #     #         expected=,
    #     #         base_path=tmp_path,
    #     #     )

    #     orm.Group.collection.delete(add_group.pk)

    #     group_dumper = ProfileDumper(
    #         output_path=output_path,
    #         config=DumpConfig(delete_missing=True),
    #     )
    #     group_dumper.dump()

    #     print(tmp_path)

    # compare_tree(
    #     expected=tree_profile_delete_missing_nodes,
    #     base_path=tmp_path,
    # )
    # with pytest.raises(AssertionError):
    #     compare_tree(
    #         expected=tree_profile_groups_add_multiply_add,
    #         base_path=tmp_path,
    #     )

    # @pytest.mark.usefixtures("aiida_profile_clean")
    # def test_dump_no_only_top_level_wfs(
    #     self, tmp_path, setup_add_group, setup_multiply_add_group
    # ):
    #     ...
    #     # TODO: We currently have no workchain in AiiDA core to test this, or at least I haven't found it

    # @pytest.mark.usefixtures("aiida_profile_clean")
    # def test_dump_no_only_top_level_calcs(
    #     self, tmp_path, setup_add_group, setup_multiply_add_group
    # ):
    #     setup_multiply_add_group
    #     setup_add_group
    #         #     group_dumper = ProfileDumper(
    #         output_path=tmp_path / profile_dump_label,
    #         config=DumpConfig(only_top_level_calcs=True),
    #     )

    #     group_dumper.dump()
    #     compare_tree(
    #         expected=tree_profile_no_only_top_level_calcs,
    #         base_path=tmp_path,
    #     )

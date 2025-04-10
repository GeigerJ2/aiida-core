###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################
"""Tests for the dumping of profile data to disk."""

import copy

import pytest

from aiida.tools.mirror.config import (
    MirrorCollectorConfig,
    MirrorPaths,
    ProfileMirrorConfig,
)
from aiida.tools.mirror.profile import ProfileMirror

from .utils import compare_tree

profile_mirror_label = 'profile-mirror'
add_group_label = 'add-group'
multiply_add_group_label = 'multiply-add-group'

tree_profile_group_add = {
    profile_mirror_label: [
        '.aiida_mirror_log.json',
        '.aiida_mirror_safeguard',
        {
            'groups': [
                {
                    add_group_label: [
                        '.aiida_mirror_safeguard',
                        {
                            'calculations': [
                                {
                                    'ArithmeticAddCalculation-4': [
                                        '.aiida_mirror_safeguard',
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
    ]
}

tree_profile_group_multiply_add = {
    profile_mirror_label: [
        '.aiida_mirror_log.json',
        '.aiida_mirror_safeguard',
        {
            'groups': [
                {
                    multiply_add_group_label: [
                        '.aiida_mirror_safeguard',
                        {
                            'workflows': [
                                {
                                    'MultiplyAddWorkChain-5': [
                                        '.aiida_mirror_safeguard',
                                        '.aiida_node_metadata.yaml',
                                        {
                                            '01-multiply-6': [
                                                '.aiida_node_metadata.yaml',
                                                '.aiida_mirror_safeguard',
                                                {'inputs': ['source_file']},
                                                {'node_inputs': []},
                                            ]
                                        },
                                        {
                                            '02-ArithmeticAddCalculation-8': [
                                                '.aiida_node_metadata.yaml',
                                                '.aiida_mirror_safeguard',
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
    profile_mirror_label: [
        '.aiida_mirror_log.json',
        '.aiida_mirror_safeguard',
        {
            'groups': [
                {
                    add_group_label: [
                        '.aiida_mirror_safeguard',
                        {
                            'calculations': [
                                {
                                    'ArithmeticAddCalculation-4': [
                                        '.aiida_mirror_safeguard',
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
                        '.aiida_mirror_safeguard',
                        {
                            'workflows': [
                                {
                                    'MultiplyAddWorkChain-12': [
                                        '.aiida_mirror_safeguard',
                                        '.aiida_node_metadata.yaml',
                                        {
                                            '01-multiply-13': [
                                                '.aiida_node_metadata.yaml',
                                                '.aiida_mirror_safeguard',
                                                {'inputs': ['source_file']},
                                                {'node_inputs': []},
                                            ]
                                        },
                                        {
                                            '02-ArithmeticAddCalculation-15': [
                                                '.aiida_node_metadata.yaml',
                                                '.aiida_mirror_safeguard',
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
    profile_mirror_label: [
        '.aiida_mirror_log.json',
        '.aiida_mirror_safeguard',
        {
            'groups': [
                {
                    add_group_label: [
                        '.aiida_mirror_safeguard',
                        {
                            'calculations': [
                                {
                                    'ArithmeticAddCalculation-4': [
                                        '.aiida_mirror_safeguard',
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
                        '.aiida_mirror_safeguard',
                        {
                            'workflows': [
                                {
                                    'MultiplyAddWorkChain-12': [
                                        '.aiida_mirror_safeguard',
                                        '.aiida_node_metadata.yaml',
                                        {
                                            '01-multiply-13': [
                                                '.aiida_node_metadata.yaml',
                                                '.aiida_mirror_safeguard',
                                                {'inputs': ['source_file']},
                                                {'node_inputs': []},
                                            ]
                                        },
                                        {
                                            '02-ArithmeticAddCalculation-15': [
                                                '.aiida_node_metadata.yaml',
                                                '.aiida_mirror_safeguard',
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
    profile_mirror_label: [
        '.aiida_mirror_log.json',
        '.aiida_mirror_safeguard',
        {
            'calculations': [
                {
                    'ArithmeticAddCalculation-4': [
                        '.aiida_mirror_safeguard',
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
                        '.aiida_mirror_safeguard',
                        '.aiida_node_metadata.yaml',
                        {
                            '01-multiply-13': [
                                '.aiida_node_metadata.yaml',
                                '.aiida_mirror_safeguard',
                                {'inputs': ['source_file']},
                                {'node_inputs': []},
                            ]
                        },
                        {
                            '02-ArithmeticAddCalculation-15': [
                                '.aiida_node_metadata.yaml',
                                '.aiida_mirror_safeguard',
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
    profile_mirror_label: [
        '.aiida_mirror_log.json',
        '.aiida_mirror_safeguard',
        {
            'groups': [
                {
                    add_group_label: [
                        '.aiida_mirror_safeguard',
                        {
                            'calculations': [
                                {
                                    'ArithmeticAddCalculation-4': [
                                        '.aiida_mirror_safeguard',
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
                        '.aiida_mirror_safeguard',
                        {
                            'workflows': [
                                {
                                    'MultiplyAddWorkChain-12': [
                                        '.aiida_mirror_safeguard',
                                        '.aiida_node_metadata.yaml',
                                        {
                                            '01-multiply-13': [
                                                '.aiida_node_metadata.yaml',
                                                '.aiida_mirror_safeguard',
                                                {'inputs': ['source_file']},
                                                {'node_inputs': []},
                                            ]
                                        },
                                        {
                                            '02-ArithmeticAddCalculation-15': [
                                                '.aiida_node_metadata.yaml',
                                                '.aiida_mirror_safeguard',
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
            'no-group': [
                '.aiida_mirror_safeguard',
                {
                    'calculations': [
                        {
                            'ArithmeticAddCalculation-22': [
                                '.aiida_mirror_safeguard',
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
                                '.aiida_mirror_safeguard',
                                '.aiida_node_metadata.yaml',
                                {
                                    '01-multiply-31': [
                                        '.aiida_node_metadata.yaml',
                                        '.aiida_mirror_safeguard',
                                        {'inputs': ['source_file']},
                                        {'node_inputs': []},
                                    ]
                                },
                                {
                                    '02-ArithmeticAddCalculation-33': [
                                        '.aiida_node_metadata.yaml',
                                        '.aiida_mirror_safeguard',
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
    'profile-mirror': [
        '.aiida_mirror_log.json',
        '.aiida_mirror_safeguard',
        {
            'groups': [
                {
                    'add-group': [
                        '.aiida_mirror_safeguard',
                        {
                            'calculations': [
                                {
                                    'ArithmeticAddCalculation-4': [
                                        '.aiida_mirror_safeguard',
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
                    'multiply-add-group': [
                        '.aiida_mirror_safeguard',
                        {
                            'calculations': [
                                {
                                    'ArithmeticAddCalculation-15': [
                                        '.aiida_mirror_safeguard',
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
                                        '.aiida_mirror_safeguard',
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
                                        '.aiida_mirror_safeguard',
                                        '.aiida_node_metadata.yaml',
                                        {
                                            '01-multiply-13': [
                                                '.aiida_mirror_safeguard',
                                                '.aiida_node_metadata.yaml',
                                                {'inputs': ['source_file']},
                                                {'node_inputs': []},
                                            ]
                                        },
                                        {
                                            '02-ArithmeticAddCalculation-15': [
                                                '.aiida_mirror_safeguard',
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
    'profile-mirror': [
        '.aiida_mirror_log.json',
        '.aiida_mirror_safeguard',
        {
            'groups': [
                {'add-group': ['.aiida_mirror_safeguard', {'calculations': []}]},
                {
                    'multiply-add-group': [
                        '.aiida_mirror_safeguard',
                        {
                            'workflows': [
                                {
                                    'MultiplyAddWorkChain-12': [
                                        '.aiida_mirror_safeguard',
                                        '.aiida_node_metadata.yaml',
                                        {
                                            '01-multiply-13': [
                                                '.aiida_mirror_safeguard',
                                                '.aiida_node_metadata.yaml',
                                                {'inputs': ['source_file']},
                                                {'node_inputs': []},
                                            ]
                                        },
                                        {
                                            '02-ArithmeticAddCalculation-15': [
                                                '.aiida_mirror_safeguard',
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


class TestProfileMirror:
    @pytest.mark.usefixtures('aiida_profile_clean')
    def test_mirror_add_group(self, tmp_path, setup_add_group):
        setup_add_group
        mirror_paths = MirrorPaths.from_path(tmp_path / profile_mirror_label)
        profile_mirror_inst = ProfileMirror(mirror_paths=mirror_paths)
        profile_mirror_inst.mirror()

        compare_tree(
            expected=tree_profile_group_add,
            base_path=tmp_path,
        )

    @pytest.mark.usefixtures('aiida_profile_clean')
    def test_mirror_multiply_add_group(self, tmp_path, setup_multiply_add_group):
        setup_multiply_add_group
        mirror_paths = MirrorPaths.from_path(tmp_path / profile_mirror_label)
        profile_mirror_inst = ProfileMirror(mirror_paths=mirror_paths)
        profile_mirror_inst.mirror()
        compare_tree(
            expected=tree_profile_group_multiply_add,
            base_path=tmp_path,
        )

    @pytest.mark.usefixtures('aiida_profile_clean')
    def test_mirror_add_multiply_add_groups(self, tmp_path, setup_add_group, setup_multiply_add_group):
        setup_multiply_add_group
        setup_add_group
        mirror_paths = MirrorPaths.from_path(tmp_path / profile_mirror_label)
        profile_mirror_inst = ProfileMirror(mirror_paths=mirror_paths)
        profile_mirror_inst.mirror()

        compare_tree(
            expected=tree_profile_groups_add_multiply_add,
            base_path=tmp_path,
        )

    @pytest.mark.usefixtures('aiida_profile_clean')
    def test_mirror_multiply_add_add_groups(self, tmp_path, setup_add_group, setup_multiply_add_group):
        setup_add_group
        setup_multiply_add_group
        mirror_paths = MirrorPaths.from_path(tmp_path / profile_mirror_label)
        profile_mirror_inst = ProfileMirror(mirror_paths=mirror_paths)
        profile_mirror_inst.mirror()

        compare_tree(
            expected=tree_profile_groups_multiply_add_add,
            base_path=tmp_path,
        )

    @pytest.mark.usefixtures('aiida_profile_clean')
    def test_mirror_no_organize_by_groups(self, tmp_path, setup_add_group, setup_multiply_add_group):
        setup_add_group
        setup_multiply_add_group
        mirror_paths = MirrorPaths.from_path(tmp_path / profile_mirror_label)
        config = ProfileMirrorConfig(organize_by_groups=False)
        profile_mirror_inst = ProfileMirror(mirror_paths=mirror_paths, config=config)
        profile_mirror_inst.mirror()

        compare_tree(
            expected=tree_profile_no_organize_by_groups,
            base_path=tmp_path,
        )

    @pytest.mark.usefixtures('aiida_profile_clean')
    def test_mirror_also_ungrouped(
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

        mirror_paths = MirrorPaths.from_path(tmp_path / profile_mirror_label)
        profile_mirror_inst = ProfileMirror(
            mirror_paths=mirror_paths,
            config=ProfileMirrorConfig(also_ungrouped=False),
        )
        profile_mirror_inst.mirror()

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

        # Now, also mirror the two additional nodes in incremental mode
        profile_mirror_inst = ProfileMirror(
            mirror_paths=mirror_paths,
            mirror_collector_config=MirrorCollectorConfig(filter_by_last_mirror_time=False),
            config=ProfileMirrorConfig(also_ungrouped=True),
        )
        profile_mirror_inst.mirror()

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
    def test_mirror_delete_missing_nodes(
        self,
        tmp_path,
        setup_add_group,
        setup_multiply_add_group,
    ):
        from aiida.tools.graph.deletions import delete_nodes

        add_group = setup_add_group
        setup_multiply_add_group

        mirror_paths = MirrorPaths.from_path(tmp_path / profile_mirror_label)
        profile_mirror_inst = ProfileMirror(mirror_paths=mirror_paths)
        profile_mirror_inst.mirror()

        # Full mirror
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

        profile_mirror_inst = ProfileMirror(
            mirror_paths=mirror_paths,
            config=ProfileMirrorConfig(delete_missing=True),
        )
        profile_mirror_inst.mirror()

        compare_tree(
            expected=tree_profile_delete_missing_nodes,
            base_path=tmp_path,
        )
        with pytest.raises(AssertionError):
            compare_tree(
                expected=tree_profile_groups_add_multiply_add,
                base_path=tmp_path,
            )

    @pytest.mark.usefixtures('aiida_profile_clean')
    def test_mirror_delete_missing_groups(
        self,
        tmp_path,
        setup_add_group,
        setup_multiply_add_group,
    ):
        from aiida import orm

        add_group = setup_add_group
        setup_multiply_add_group

        mirror_paths = MirrorPaths.from_path(tmp_path / profile_mirror_label)
        profile_mirror_inst = ProfileMirror(mirror_paths=mirror_paths)
        profile_mirror_inst.mirror()

        # Full mirror
        compare_tree(
            expected=tree_profile_groups_add_multiply_add,
            base_path=tmp_path,
        )
        # with pytest.raises(AssertionError):
        #     compare_tree(
        #         expected=,
        #         base_path=tmp_path,
        #     )

        orm.Group.collection.delete(add_group.pk)

        profile_mirror_inst = ProfileMirror(
            mirror_paths=mirror_paths,
            config=ProfileMirrorConfig(delete_missing=True),
        )
        profile_mirror_inst.mirror()
        # TODO: This deletes too much:
        # └── profile-mirror
        #     ├── .aiida_mirror_log.json
        #     ├── .aiida_mirror_safeguard
        #     └── groups
        #         └── multiply-add-group
        #             ├── .aiida_mirror_safeguard
        #             └── workflows

        print(tmp_path)

        # compare_tree(
        #     expected=tree_profile_delete_missing_nodes,
        #     base_path=tmp_path,
        # )
        # with pytest.raises(AssertionError):
        #     compare_tree(
        #         expected=tree_profile_groups_add_multiply_add,
        #         base_path=tmp_path,
        #     )

    @pytest.mark.usefixtures('aiida_profile_clean')
    def test_mirror_update_groups(
        self,
        tmp_path,
        setup_add_group,
    ):
        add_group = setup_add_group
        new_label = 'xadd-group'

        mirror_paths = MirrorPaths.from_path(tmp_path / profile_mirror_label)
        profile_mirror_inst = ProfileMirror(mirror_paths=mirror_paths)
        profile_mirror_inst.mirror()

        # Full mirror
        compare_tree(
            expected=tree_profile_group_add,
            base_path=tmp_path,
        )

        # Rename the group
        add_group.label = new_label

        config = ProfileMirrorConfig(update_groups=True)
        profile_mirror_inst = ProfileMirror(mirror_paths=mirror_paths, config=config)
        profile_mirror_inst.mirror()

        # Previous tree fails
        with pytest.raises(AssertionError):
            compare_tree(
                expected=tree_profile_group_add,
                base_path=tmp_path,
            )

        new_tree = copy.deepcopy(tree_profile_group_add)
        new_tree[profile_mirror_label][2]['groups'][0]['xadd-group'] = new_tree[profile_mirror_label][2]['groups'][
            0
        ].pop('add-group')

        compare_tree(
            expected=new_tree,
            base_path=tmp_path,
        )

        # TODO: Also verify the log update

    @pytest.mark.usefixtures('aiida_profile_clean')
    def test_mirror_no_only_top_level_calcs(self, tmp_path, setup_add_group, setup_multiply_add_group):
        setup_multiply_add_group
        setup_add_group
        mirror_paths = MirrorPaths.from_path(tmp_path / profile_mirror_label)
        mirror_collector_config = MirrorCollectorConfig(only_top_level_calcs=False)
        profile_mirror_inst = ProfileMirror(mirror_paths=mirror_paths, mirror_collector_config=mirror_collector_config)

        profile_mirror_inst.mirror()
        compare_tree(
            expected=tree_profile_no_only_top_level_calcs,
            base_path=tmp_path,
        )

    @pytest.mark.usefixtures('aiida_profile_clean')
    def test_mirror_no_only_top_level_wfs(self, tmp_path, setup_add_group, setup_multiply_add_group):
        ...
        # TODO: We currently have no workchain in AiiDA core to test this, or at least I haven't found it

    @pytest.mark.usefixtures('aiida_profile_clean')
    def test_mirror_symlink_calcs(self, tmp_path, setup_add_group, setup_multiply_add_group):
        setup_multiply_add_group
        setup_add_group
        mirror_paths = MirrorPaths.from_path(tmp_path / profile_mirror_label)
        mirror_collector_config = MirrorCollectorConfig(only_top_level_calcs=False)
        profile_mirror_inst = ProfileMirror(mirror_paths=mirror_paths, mirror_collector_config=mirror_collector_config)

        profile_mirror_inst.mirror()
        compare_tree(
            expected=tree_profile_no_only_top_level_calcs,
            base_path=tmp_path,
        )

    @pytest.mark.usefixtures('aiida_profile_clean')
    def test_mirror_symlink_wfs(self, tmp_path, setup_add_group, setup_multiply_add_group):
        ...
        # TODO: This is not implemented yet, and not sure if it's necessary

    def test_delete_missing_group_nodes_retained(self): ...

    def test_delete_missing_group_nodes_deleted(self): ...

    # @pytest.mark.usefixtures('aiida_profile_clean')
    # def test_get_groups_to_delete(self, tmp_path):
    #     # NOTE: `mirror_logger` and `profile_mirror.mirror_loger` if I construct the `profile_mirror` here and already
    #     # attach the `mirror_logger`...?
    #     mirror_paths = MirrorPaths.from_path(tmp_path)
    #     mirror_logger = MirrorLogger(mirror_paths=mirror_paths)
    #     groups = []
    #     for i in range(2):
    #         group_label = f'group-{i}'
    #         group = orm.Group(label=group_label)
    #         group.store()
    #         mirror_logger.add_entry(
    #             store=mirror_logger.stores.groups,
    #             uuid=group.uuid,
    #             entry=MirrorLog(path=tmp_path / group_label),
    #         )
    #         groups.append(group)

    #     config = ProfileMirrorConfig(delete_missing=True)
    #     profile_mirror = ProfileMirror(mirror_paths=mirror_paths, mirror_logger=mirror_logger, config=config)
    #     _ = orm.Group.collection.delete(groups[0].pk)

    #     assert profile_mirror.get_groups_to_delete() == [groups[0].uuid]

    #     _ = orm.Group.collection.delete(groups[1].pk)
    #     assert profile_mirror.get_groups_to_delete() == [group.uuid for group in groups]

    # @pytest.mark.usefixtures('aiida_profile_clean')
    # def test_del_missing_groups(tmp_path):
    #     # NOTE: `mirror_logger` and `profile_mirror.mirror_loger` if I construct the `profile_mirror` here and already
    #     # attach the `mirror_logger`...?
    #     mirror_paths = MirrorPaths.from_path(tmp_path)
    #     mirror_logger = MirrorLogger(mirror_paths=mirror_paths)
    #     mirror_times = MirrorTimes()
    #     group_store = mirror_logger.stores.groups
    #     groups = []
    #     for i in range(2):
    #         group_label = f'group-{i}'
    #         group = orm.Group(label=group_label)
    #         group.store()
    #         mirror_logger.add_entry(
    #             store=mirror_logger.stores.groups,
    #             uuid=group.uuid,
    #             entry=MirrorLog(path=tmp_path / group_label),
    #         )
    #         groups.append(group)

    #     config = ProfileMirrorConfig(delete_missing=True)
    #     profile_mirror = ProfileMirror(mirror_paths=mirror_paths, mirror_logger=mirror_logger, config=config)

    #     path_to_del = group_store.get_entry(uuid=groups[0].uuid).path

    #     _ = orm.Group.collection.delete(groups[0].pk)

    #     profile_mirror.delete_missing_groups()
    #     assert path_to_del

    #     # assert profile_mirror.get_groups_to_delete() == [groups[0].uuid]

    #     # _ = orm.Group.collection.delete(groups[1].pk)
    #     # assert profile_mirror.get_groups_to_delete() == [group.uuid for group in groups]

    #     # to_delete_uuid = ProfileMirror.get_groups_to_delete()
    #     # assert to_delete_uuid[0] == group_uuid

    #     # import ipdb

    #     # profile_mirror

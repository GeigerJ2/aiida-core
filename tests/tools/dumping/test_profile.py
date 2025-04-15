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
from aiida.tools.dumping.entities.profile import ProfileDumper
from aiida.tools.dumping.storage.logger import DumpLogger
from aiida.tools.dumping.utils.tree import compare_tree

profile_dump_label = "profile-dump"
add_group_label = "add-group"
multiply_add_group_label = "multiply-add-group"

tree_profile_group_add = {
    profile_dump_label: [
        ".aiida_dump_log.json",
        ".aiida_dump_safeguard",
        {
            "groups": [
                {
                    add_group_label: [
                        {
                            "calculations": [
                                {
                                    "ArithmeticAddCalculation-4": [
                                        ".aiida_dump_safeguard",
                                        ".aiida_node_metadata.yaml",
                                        {
                                            "inputs": [
                                                "_aiidasubmit.sh",
                                                "aiida.in",
                                                {
                                                    ".aiida": [
                                                        "calcinfo.json",
                                                        "job_tmpl.json",
                                                    ]
                                                },
                                            ]
                                        },
                                        {"node_inputs": []},
                                        {
                                            "outputs": [
                                                "_scheduler-stderr.txt",
                                                "_scheduler-stdout.txt",
                                                "aiida.out",
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
    profile_dump_label: [
        ".aiida_dump_log.json",
        ".aiida_dump_safeguard",
        {
            "groups": [
                {
                    multiply_add_group_label: [
                        {
                            "workflows": [
                                {
                                    "MultiplyAddWorkChain-5": [
                                        ".aiida_dump_safeguard",
                                        ".aiida_node_metadata.yaml",
                                        {
                                            "01-multiply-6": [
                                                ".aiida_node_metadata.yaml",
                                                ".aiida_dump_safeguard",
                                                {"inputs": ["source_file"]},
                                                {"node_inputs": []},
                                            ]
                                        },
                                        {
                                            "02-ArithmeticAddCalculation-8": [
                                                ".aiida_node_metadata.yaml",
                                                ".aiida_dump_safeguard",
                                                {
                                                    "inputs": [
                                                        "_aiidasubmit.sh",
                                                        "aiida.in",
                                                        {
                                                            ".aiida": [
                                                                "calcinfo.json",
                                                                "job_tmpl.json",
                                                            ]
                                                        },
                                                    ]
                                                },
                                                {"node_inputs": []},
                                                {
                                                    "outputs": [
                                                        "_scheduler-stderr.txt",
                                                        "_scheduler-stdout.txt",
                                                        "aiida.out",
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
        ".aiida_dump_log.json",
        ".aiida_dump_safeguard",
        {
            "groups": [
                {
                    add_group_label: [
                        {
                            "calculations": [
                                {
                                    "ArithmeticAddCalculation-4": [
                                        ".aiida_dump_safeguard",
                                        ".aiida_node_metadata.yaml",
                                        {
                                            "inputs": [
                                                "_aiidasubmit.sh",
                                                "aiida.in",
                                                {
                                                    ".aiida": [
                                                        "calcinfo.json",
                                                        "job_tmpl.json",
                                                    ]
                                                },
                                            ]
                                        },
                                        {"node_inputs": []},
                                        {
                                            "outputs": [
                                                "_scheduler-stderr.txt",
                                                "_scheduler-stdout.txt",
                                                "aiida.out",
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
                        {
                            "workflows": [
                                {
                                    "MultiplyAddWorkChain-12": [
                                        ".aiida_dump_safeguard",
                                        ".aiida_node_metadata.yaml",
                                        {
                                            "01-multiply-13": [
                                                ".aiida_node_metadata.yaml",
                                                ".aiida_dump_safeguard",
                                                {"inputs": ["source_file"]},
                                                {"node_inputs": []},
                                            ]
                                        },
                                        {
                                            "02-ArithmeticAddCalculation-15": [
                                                ".aiida_node_metadata.yaml",
                                                ".aiida_dump_safeguard",
                                                {
                                                    "inputs": [
                                                        "_aiidasubmit.sh",
                                                        "aiida.in",
                                                        {
                                                            ".aiida": [
                                                                "calcinfo.json",
                                                                "job_tmpl.json",
                                                            ]
                                                        },
                                                    ]
                                                },
                                                {"node_inputs": []},
                                                {
                                                    "outputs": [
                                                        "_scheduler-stderr.txt",
                                                        "_scheduler-stdout.txt",
                                                        "aiida.out",
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
        ".aiida_dump_log.json",
        ".aiida_dump_safeguard",
        {
            "groups": [
                {
                    add_group_label: [
                        {
                            "calculations": [
                                {
                                    "ArithmeticAddCalculation-4": [
                                        ".aiida_dump_safeguard",
                                        ".aiida_node_metadata.yaml",
                                        {
                                            "inputs": [
                                                "_aiidasubmit.sh",
                                                "aiida.in",
                                                {
                                                    ".aiida": [
                                                        "calcinfo.json",
                                                        "job_tmpl.json",
                                                    ]
                                                },
                                            ]
                                        },
                                        {"node_inputs": []},
                                        {
                                            "outputs": [
                                                "_scheduler-stderr.txt",
                                                "_scheduler-stdout.txt",
                                                "aiida.out",
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
                        {
                            "workflows": [
                                {
                                    "MultiplyAddWorkChain-12": [
                                        ".aiida_dump_safeguard",
                                        ".aiida_node_metadata.yaml",
                                        {
                                            "01-multiply-13": [
                                                ".aiida_node_metadata.yaml",
                                                ".aiida_dump_safeguard",
                                                {"inputs": ["source_file"]},
                                                {"node_inputs": []},
                                            ]
                                        },
                                        {
                                            "02-ArithmeticAddCalculation-15": [
                                                ".aiida_node_metadata.yaml",
                                                ".aiida_dump_safeguard",
                                                {
                                                    "inputs": [
                                                        "_aiidasubmit.sh",
                                                        "aiida.in",
                                                        {
                                                            ".aiida": [
                                                                "calcinfo.json",
                                                                "job_tmpl.json",
                                                            ]
                                                        },
                                                    ]
                                                },
                                                {"node_inputs": []},
                                                {
                                                    "outputs": [
                                                        "_scheduler-stderr.txt",
                                                        "_scheduler-stdout.txt",
                                                        "aiida.out",
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
        ".aiida_dump_log.json",
        ".aiida_dump_safeguard",
        {
            "calculations": [
                {
                    "ArithmeticAddCalculation-4": [
                        ".aiida_dump_safeguard",
                        ".aiida_node_metadata.yaml",
                        {
                            "inputs": [
                                "_aiidasubmit.sh",
                                "aiida.in",
                                {".aiida": ["calcinfo.json", "job_tmpl.json"]},
                            ]
                        },
                        {"node_inputs": []},
                        {
                            "outputs": [
                                "_scheduler-stderr.txt",
                                "_scheduler-stdout.txt",
                                "aiida.out",
                            ]
                        },
                    ]
                }
            ]
        },
        {
            "workflows": [
                {
                    "MultiplyAddWorkChain-12": [
                        ".aiida_dump_safeguard",
                        ".aiida_node_metadata.yaml",
                        {
                            "01-multiply-13": [
                                ".aiida_node_metadata.yaml",
                                ".aiida_dump_safeguard",
                                {"inputs": ["source_file"]},
                                {"node_inputs": []},
                            ]
                        },
                        {
                            "02-ArithmeticAddCalculation-15": [
                                ".aiida_node_metadata.yaml",
                                ".aiida_dump_safeguard",
                                {
                                    "inputs": [
                                        "_aiidasubmit.sh",
                                        "aiida.in",
                                        {".aiida": ["calcinfo.json", "job_tmpl.json"]},
                                    ]
                                },
                                {"node_inputs": []},
                                {
                                    "outputs": [
                                        "_scheduler-stderr.txt",
                                        "_scheduler-stdout.txt",
                                        "aiida.out",
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
        ".aiida_dump_log.json",
        ".aiida_dump_safeguard",
        {
            "groups": [
                {
                    add_group_label: [
                        {
                            "calculations": [
                                {
                                    "ArithmeticAddCalculation-4": [
                                        ".aiida_dump_safeguard",
                                        ".aiida_node_metadata.yaml",
                                        {
                                            "inputs": [
                                                "_aiidasubmit.sh",
                                                "aiida.in",
                                                {
                                                    ".aiida": [
                                                        "calcinfo.json",
                                                        "job_tmpl.json",
                                                    ]
                                                },
                                            ]
                                        },
                                        {"node_inputs": []},
                                        {
                                            "outputs": [
                                                "_scheduler-stderr.txt",
                                                "_scheduler-stdout.txt",
                                                "aiida.out",
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
                        {
                            "workflows": [
                                {
                                    "MultiplyAddWorkChain-12": [
                                        ".aiida_dump_safeguard",
                                        ".aiida_node_metadata.yaml",
                                        {
                                            "01-multiply-13": [
                                                ".aiida_node_metadata.yaml",
                                                ".aiida_dump_safeguard",
                                                {"inputs": ["source_file"]},
                                                {"node_inputs": []},
                                            ]
                                        },
                                        {
                                            "02-ArithmeticAddCalculation-15": [
                                                ".aiida_node_metadata.yaml",
                                                ".aiida_dump_safeguard",
                                                {
                                                    "inputs": [
                                                        "_aiidasubmit.sh",
                                                        "aiida.in",
                                                        {
                                                            ".aiida": [
                                                                "calcinfo.json",
                                                                "job_tmpl.json",
                                                            ]
                                                        },
                                                    ]
                                                },
                                                {"node_inputs": []},
                                                {
                                                    "outputs": [
                                                        "_scheduler-stderr.txt",
                                                        "_scheduler-stdout.txt",
                                                        "aiida.out",
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
            "no-group": [
                {
                    "calculations": [
                        {
                            "ArithmeticAddCalculation-22": [
                                ".aiida_dump_safeguard",
                                ".aiida_node_metadata.yaml",
                                {
                                    "inputs": [
                                        "_aiidasubmit.sh",
                                        "aiida.in",
                                        {
                                            ".aiida": [
                                                "calcinfo.json",
                                                "job_tmpl.json",
                                            ]
                                        },
                                    ]
                                },
                                {"node_inputs": []},
                                {
                                    "outputs": [
                                        "_scheduler-stderr.txt",
                                        "_scheduler-stdout.txt",
                                        "aiida.out",
                                    ]
                                },
                            ]
                        }
                    ]
                },
                {
                    "workflows": [
                        {
                            "MultiplyAddWorkChain-30": [
                                ".aiida_dump_safeguard",
                                ".aiida_node_metadata.yaml",
                                {
                                    "01-multiply-31": [
                                        ".aiida_node_metadata.yaml",
                                        ".aiida_dump_safeguard",
                                        {"inputs": ["source_file"]},
                                        {"node_inputs": []},
                                    ]
                                },
                                {
                                    "02-ArithmeticAddCalculation-33": [
                                        ".aiida_node_metadata.yaml",
                                        ".aiida_dump_safeguard",
                                        {
                                            "inputs": [
                                                "_aiidasubmit.sh",
                                                "aiida.in",
                                                {
                                                    ".aiida": [
                                                        "calcinfo.json",
                                                        "job_tmpl.json",
                                                    ]
                                                },
                                            ]
                                        },
                                        {"node_inputs": []},
                                        {
                                            "outputs": [
                                                "_scheduler-stderr.txt",
                                                "_scheduler-stdout.txt",
                                                "aiida.out",
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
    "profile-dump": [
        ".aiida_dump_log.json",
        ".aiida_dump_safeguard",
        {
            "groups": [
                {
                    "add-group": [
                        {
                            "calculations": [
                                {
                                    "ArithmeticAddCalculation-4": [
                                        ".aiida_dump_safeguard",
                                        ".aiida_node_metadata.yaml",
                                        {
                                            "inputs": [
                                                "_aiidasubmit.sh",
                                                "aiida.in",
                                                {
                                                    ".aiida": [
                                                        "calcinfo.json",
                                                        "job_tmpl.json",
                                                    ]
                                                },
                                            ]
                                        },
                                        {"node_inputs": []},
                                        {
                                            "outputs": [
                                                "_scheduler-stderr.txt",
                                                "_scheduler-stdout.txt",
                                                "aiida.out",
                                            ]
                                        },
                                    ]
                                }
                            ]
                        },
                    ]
                },
                {
                    "multiply-add-group": [
                        {
                            "calculations": [
                                {
                                    "ArithmeticAddCalculation-15": [
                                        ".aiida_dump_safeguard",
                                        ".aiida_node_metadata.yaml",
                                        {
                                            "inputs": [
                                                "_aiidasubmit.sh",
                                                "aiida.in",
                                                {
                                                    ".aiida": [
                                                        "calcinfo.json",
                                                        "job_tmpl.json",
                                                    ]
                                                },
                                            ]
                                        },
                                        {"node_inputs": []},
                                        {
                                            "outputs": [
                                                "_scheduler-stderr.txt",
                                                "_scheduler-stdout.txt",
                                                "aiida.out",
                                            ]
                                        },
                                    ]
                                },
                                {
                                    "multiply-13": [
                                        ".aiida_dump_safeguard",
                                        ".aiida_node_metadata.yaml",
                                        {"inputs": ["source_file"]},
                                        {"node_inputs": []},
                                    ]
                                },
                            ]
                        },
                        {
                            "workflows": [
                                {
                                    "MultiplyAddWorkChain-12": [
                                        ".aiida_dump_safeguard",
                                        ".aiida_node_metadata.yaml",
                                        {
                                            "01-multiply-13": [
                                                ".aiida_dump_safeguard",
                                                ".aiida_node_metadata.yaml",
                                                {"inputs": ["source_file"]},
                                                {"node_inputs": []},
                                            ]
                                        },
                                        {
                                            "02-ArithmeticAddCalculation-15": [
                                                ".aiida_dump_safeguard",
                                                ".aiida_node_metadata.yaml",
                                                {
                                                    "inputs": [
                                                        "_aiidasubmit.sh",
                                                        "aiida.in",
                                                        {
                                                            ".aiida": [
                                                                "calcinfo.json",
                                                                "job_tmpl.json",
                                                            ]
                                                        },
                                                    ]
                                                },
                                                {"node_inputs": []},
                                                {
                                                    "outputs": [
                                                        "_scheduler-stderr.txt",
                                                        "_scheduler-stdout.txt",
                                                        "aiida.out",
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
    "profile-dump": [
        ".aiida_dump_log.json",
        ".aiida_dump_safeguard",
        {
            "groups": [
                {"add-group": [{"calculations": []}]},
                {
                    "multiply-add-group": [
                        {
                            "workflows": [
                                {
                                    "MultiplyAddWorkChain-12": [
                                        ".aiida_dump_safeguard",
                                        ".aiida_node_metadata.yaml",
                                        {
                                            "01-multiply-13": [
                                                ".aiida_dump_safeguard",
                                                ".aiida_node_metadata.yaml",
                                                {"inputs": ["source_file"]},
                                                {"node_inputs": []},
                                            ]
                                        },
                                        {
                                            "02-ArithmeticAddCalculation-15": [
                                                ".aiida_dump_safeguard",
                                                ".aiida_node_metadata.yaml",
                                                {
                                                    "inputs": [
                                                        "_aiidasubmit.sh",
                                                        "aiida.in",
                                                        {
                                                            ".aiida": [
                                                                "calcinfo.json",
                                                                "job_tmpl.json",
                                                            ]
                                                        },
                                                    ]
                                                },
                                                {"node_inputs": []},
                                                {
                                                    "outputs": [
                                                        "_scheduler-stderr.txt",
                                                        "_scheduler-stdout.txt",
                                                        "aiida.out",
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
                    'add-group': [
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
                                }
                            ]
                        }
                    ]
                }
            ]
        }
    ]
}

tree_profile_group_add_copy = {
    profile_dump_label: [
        ".aiida_dump_log.json",
        ".aiida_dump_safeguard",
        {
            "groups": [
                {
                    'add-group': [
                        {
                            "calculations": [
                                {
                                    "ArithmeticAddCalculation-4": [
                                        ".aiida_dump_safeguard",
                                        ".aiida_node_metadata.yaml",
                                        {
                                            "inputs": [
                                                "_aiidasubmit.sh",
                                                "aiida.in",
                                                {
                                                    ".aiida": [
                                                        "calcinfo.json",
                                                        "job_tmpl.json",
                                                    ]
                                                },
                                            ]
                                        },
                                        {"node_inputs": []},
                                        {
                                            "outputs": [
                                                "_scheduler-stderr.txt",
                                                "_scheduler-stdout.txt",
                                                "aiida.out",
                                            ]
                                        },
                                    ]
                                }
                            ]
                        },
                    ],
                    'add-group-copy': [
                        {
                            "calculations": [
                                {
                                    "ArithmeticAddCalculation-4": [
                                        ".aiida_dump_safeguard",
                                        ".aiida_node_metadata.yaml",
                                        {
                                            "inputs": [
                                                "_aiidasubmit.sh",
                                                "aiida.in",
                                                {
                                                    ".aiida": [
                                                        "calcinfo.json",
                                                        "job_tmpl.json",
                                                    ]
                                                },
                                            ]
                                        },
                                        {"node_inputs": []},
                                        {
                                            "outputs": [
                                                "_scheduler-stderr.txt",
                                                "_scheduler-stdout.txt",
                                                "aiida.out",
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


class TestProfileDumper:
    @pytest.mark.usefixtures("aiida_profile_clean")
    def test_dump_add_group(self, tmp_path, setup_add_group):
        setup_add_group
        DumpLogger.reset_instance()
        profile_dumper = ProfileDumper(output_path=tmp_path / profile_dump_label)
        profile_dumper.dump()

        compare_tree(
            expected=tree_profile_group_add,
            base_path=tmp_path,
        )

    @pytest.mark.usefixtures("aiida_profile_clean")
    def test_dump_multiply_add_group(self, tmp_path, setup_multiply_add_group):
        setup_multiply_add_group
        DumpLogger.reset_instance()
        profile_dumper = ProfileDumper(output_path=tmp_path / profile_dump_label)
        profile_dumper.dump()
        compare_tree(
            expected=tree_profile_group_multiply_add,
            base_path=tmp_path,
        )

    @pytest.mark.usefixtures("aiida_profile_clean")
    def test_dump_add_multiply_add_groups(
        self, tmp_path, setup_add_group, setup_multiply_add_group
    ):
        setup_multiply_add_group
        setup_add_group
        DumpLogger.reset_instance()
        profile_dumper = ProfileDumper(output_path=tmp_path / profile_dump_label)
        profile_dumper.dump()

        compare_tree(
            expected=tree_profile_groups_add_multiply_add,
            base_path=tmp_path,
        )

    @pytest.mark.usefixtures("aiida_profile_clean")
    def test_dump_multiply_add_add_groups(
        self, tmp_path, setup_add_group, setup_multiply_add_group
    ):
        setup_add_group
        setup_multiply_add_group
        DumpLogger.reset_instance()
        profile_dumper = ProfileDumper(output_path=tmp_path / profile_dump_label)
        profile_dumper.dump()

        compare_tree(
            expected=tree_profile_groups_multiply_add_add,
            base_path=tmp_path,
        )

    @pytest.mark.usefixtures("aiida_profile_clean")
    def test_dump_no_organize_by_groups(
        self, tmp_path, setup_add_group, setup_multiply_add_group
    ):
        setup_add_group
        setup_multiply_add_group
        DumpLogger.reset_instance()
        config = DumpConfig(organize_by_groups=False)
        profile_dumper = ProfileDumper(
            output_path=tmp_path / profile_dump_label, config=config
        )
        profile_dumper.dump()

        compare_tree(
            expected=tree_profile_no_organize_by_groups,
            base_path=tmp_path,
        )

    @pytest.mark.usefixtures("aiida_profile_clean")
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
        DumpLogger.reset_instance()

        # Create additional ArithmeticAdd and MultiplyAdd nodes
        _ = generate_calculation_node_add()
        _ = generate_workchain_multiply_add()

        output_path = tmp_path / profile_dump_label

        profile_dumper = ProfileDumper(
            output_path=output_path,
            config=DumpConfig(also_ungrouped=False),
        )
        profile_dumper.dump()

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
        profile_dumper = ProfileDumper(
            output_path=output_path,
            config=DumpConfig(also_ungrouped=True, filter_by_last_dump_time=False),
        )
        profile_dumper.dump()

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
        DumpLogger.reset_instance()

        output_path = tmp_path / profile_dump_label
        profile_dumper = ProfileDumper(output_path=output_path)
        profile_dumper.dump()

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

        profile_dumper = ProfileDumper(
            output_path=output_path,
            config=DumpConfig(delete_missing=True),
        )
        profile_dumper.dump()

        compare_tree(
            expected=tree_profile_delete_missing_nodes,
            base_path=tmp_path,
        )
        with pytest.raises(AssertionError):
            compare_tree(
                expected=tree_profile_groups_add_multiply_add,
                base_path=tmp_path,
            )

    @pytest.mark.usefixtures("aiida_profile_clean")
    def test_dump_delete_missing_groups(
        self,
        tmp_path,
        setup_add_group,
        setup_multiply_add_group,
    ):
        from aiida import orm

        add_group = setup_add_group
        setup_multiply_add_group
        DumpLogger.reset_instance()

        output_path = tmp_path / profile_dump_label
        profile_dumper = ProfileDumper(output_path=output_path)
        profile_dumper.dump()

        # Full dump
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

        profile_dumper = ProfileDumper(
            output_path=output_path,
            config=DumpConfig(delete_missing=True),
        )
        profile_dumper.dump()

        print(tmp_path)

        assert False

        # compare_tree(
        #     expected=tree_profile_delete_missing_nodes,
        #     base_path=tmp_path,
        # )
        # with pytest.raises(AssertionError):
        #     compare_tree(
        #         expected=tree_profile_groups_add_multiply_add,
        #         base_path=tmp_path,
        #     )

    @pytest.mark.usefixtures("aiida_profile_clean")
    def test_dump_add_node_to_group(
        self,
        tmp_path,
        setup_add_group,
        generate_calculation_node_add
    ):

        add_group = setup_add_group
        add_node = generate_calculation_node_add()
        # setup_multiply_add_group

        DumpLogger.reset_instance()

        output_path = output_path=tmp_path / profile_dump_label
        profile_dumper = ProfileDumper(output_path=output_path)
        profile_dumper.dump()

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

        profile_dumper.dump()

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

    @pytest.mark.usefixtures("aiida_profile_clean")
    def test_dump_add_group_copy(
        self,
        tmp_path,
        setup_add_group,
    ):

        from aiida import orm

        add_group = setup_add_group
        dest_group, created = orm.Group.collection.get_or_create(label='add-group-copy')
        dest_group.add_nodes(list(add_group.nodes))

        DumpLogger.reset_instance()

        output_path = output_path=tmp_path / profile_dump_label
        profile_dumper = ProfileDumper(output_path=output_path)
        profile_dumper.dump()

        tree_profile_group_add_copy = {
            profile_dump_label: [
                ".aiida_dump_log.json",
                ".aiida_dump_safeguard",
                {
                    "groups": [
                        {
                            "add-group": [
                                {
                                    "calculations": [
                                        {
                                            "ArithmeticAddCalculation-4": [
                                                ".aiida_dump_safeguard",
                                                ".aiida_node_metadata.yaml",
                                                {
                                                    "inputs": [
                                                        "_aiidasubmit.sh",
                                                        "aiida.in",
                                                        {
                                                            ".aiida": [
                                                                "calcinfo.json",
                                                                "job_tmpl.json",
                                                            ]
                                                        },
                                                    ]
                                                },
                                                {"node_inputs": []},
                                                {
                                                    "outputs": [
                                                        "_scheduler-stderr.txt",
                                                        "_scheduler-stdout.txt",
                                                        "aiida.out",
                                                    ]
                                                },
                                            ]
                                        }
                                    ]
                                },
                            ],
                            "add-group-copy": [
                                {
                                    "calculations": [
                                        {
                                            "ArithmeticAddCalculation-4": [
                                                ".aiida_dump_safeguard",
                                                ".aiida_node_metadata.yaml",
                                                {
                                                    "inputs": [
                                                        "_aiidasubmit.sh",
                                                        "aiida.in",
                                                        {
                                                            ".aiida": [
                                                                "calcinfo.json",
                                                                "job_tmpl.json",
                                                            ]
                                                        },
                                                    ]
                                                },
                                                {"node_inputs": []},
                                                {
                                                    "outputs": [
                                                        "_scheduler-stderr.txt",
                                                        "_scheduler-stdout.txt",
                                                        "aiida.out",
                                                    ]
                                                },
                                            ]
                                        }
                                    ]
                                },
                            ],
                        }
                    ]
                },
            ]
        }

        # Additional add-node not dumped
        compare_tree(
            expected=tree_profile_group_add_copy,
            base_path=tmp_path,
        )

        profile_dumper.dump()

        # Duplicated group contained in the dump
        compare_tree(
            expected=tree_profile_group_add_copy,
            base_path=tmp_path,
        )
        with pytest.raises(AssertionError):
            compare_tree(
                expected=tree_profile_group_add,
                base_path=tmp_path,
            )

    # NOTE: This will be part of the GroupDumpVerifyer
    # @pytest.mark.usefixtures('aiida_profile_clean')
    # def test_dump_update_groups(
    #     self,
    #     tmp_path,
    #     setup_add_group,
    # ):
    #     add_group = setup_add_group
    #     new_label = 'xadd-group'

    #     profile_dumper = ProfileDumper(dump_paths=dump_paths)
    #     profile_dumper.dump()

    #     # Full dump
    #     compare_tree(
    #         expected=tree_profile_group_add,
    #         base_path=tmp_path,
    #     )

    #     # Rename the group
    #     add_group.label = new_label

    #     config = DumpConfig(update_groups=True)
    #     profile_dumper = ProfileDumper(dump_paths=dump_paths, config=config)
    #     profile_dumper.dump()

    #     # Previous tree fails
    #     with pytest.raises(AssertionError):
    #         compare_tree(
    #             expected=tree_profile_group_add,
    #             base_path=tmp_path,
    #         )

    #     new_tree = copy.deepcopy(tree_profile_group_add)
    #     new_tree[profile_dump_label][2]['groups'][0]['xadd-group'] = new_tree[profile_dump_label][2]['groups'][
    #         0
    #     ].pop('add-group')

    #     compare_tree(
    #         expected=new_tree,
    #         base_path=tmp_path,
    #     )

    # TODO: Also verify the log update

    @pytest.mark.usefixtures("aiida_profile_clean")
    def test_dump_no_only_top_level_calcs(
        self, tmp_path, setup_add_group, setup_multiply_add_group
    ):
        setup_multiply_add_group
        setup_add_group
        DumpLogger.reset_instance()
        profile_dumper = ProfileDumper(
            config=DumpConfig(only_top_level_calcs=False),
            output_path=tmp_path / profile_dump_label,
        )

        profile_dumper.dump()
        compare_tree(
            expected=tree_profile_no_only_top_level_calcs,
            base_path=tmp_path,
        )

    @pytest.mark.usefixtures("aiida_profile_clean")
    def test_dump_no_only_top_level_wfs(
        self, tmp_path, setup_add_group, setup_multiply_add_group
    ):
        ...
        # TODO: We currently have no workchain in AiiDA core to test this, or at least I haven't found it

    @pytest.mark.usefixtures("aiida_profile_clean")
    def test_dump_no_only_top_level_calcs(
        self, tmp_path, setup_add_group, setup_multiply_add_group
    ):
        setup_multiply_add_group
        setup_add_group
        DumpLogger.reset_instance()
        profile_dumper = ProfileDumper(
            output_path=tmp_path / profile_dump_label,
            config=DumpConfig(only_top_level_calcs=True),
        )

        profile_dumper.dump()
        compare_tree(
            expected=tree_profile_no_only_top_level_calcs,
            base_path=tmp_path,
        )

    @pytest.mark.usefixtures("aiida_profile_clean")
    def test_dump_symlink_wfs(
        self, tmp_path, setup_add_group, setup_multiply_add_group
    ):
        ...
        # TODO: This is not implemented yet, and not sure if it's necessary

    def test_delete_missing_group_nodes_retained(self): ...

    def test_delete_missing_group_nodes_deleted(self): ...

    # @pytest.mark.usefixtures('aiida_profile_clean')
    # def test_get_groups_to_delete(self, tmp_path):
    #     # NOTE: `dump_logger` and `profile_dump.dump_loger` if I construct the `profile_dump` here and already
    #     # attach the `dump_logger`...?
    #     dump_paths = DumpPaths.from_path(tmp_path)
    #     dump_logger = DumpLogger(dump_paths=dump_paths)
    #     groups = []
    #     for i in range(2):
    #         group_label = f'group-{i}'
    #         group = orm.Group(label=group_label)
    #         group.store()
    #         dump_logger.add_entry(
    #             store=dump_logger.stores.groups,
    #             uuid=group.uuid,
    #             entry=DumpLog(path=tmp_path / group_label),
    #         )
    #         groups.append(group)

    #     config = ProfileDumpConfig(delete_missing=True)
    #     profile_dump = ProfileDump(dump_paths=dump_paths, dump_logger=dump_logger, config=config)
    #     _ = orm.Group.collection.delete(groups[0].pk)

    #     assert profile_dump.get_groups_to_delete() == [groups[0].uuid]

    #     _ = orm.Group.collection.delete(groups[1].pk)
    #     assert profile_dump.get_groups_to_delete() == [group.uuid for group in groups]

    # @pytest.mark.usefixtures('aiida_profile_clean')
    # def test_del_missing_groups(tmp_path):
    #     # NOTE: `dump_logger` and `profile_dump.dump_loger` if I construct the `profile_dump` here and already
    #     # attach the `dump_logger`...?
    #     dump_paths = DumpPaths.from_path(tmp_path)
    #     dump_logger = DumpLogger(dump_paths=dump_paths)
    #     dump_times = DumpTimes()
    #     group_store = dump_logger.stores.groups
    #     groups = []
    #     for i in range(2):
    #         group_label = f'group-{i}'
    #         group = orm.Group(label=group_label)
    #         group.store()
    #         dump_logger.add_entry(
    #             store=dump_logger.stores.groups,
    #             uuid=group.uuid,
    #             entry=DumpLog(path=tmp_path / group_label),
    #         )
    #         groups.append(group)

    #     config = ProfileDumpConfig(delete_missing=True)
    #     profile_dump = ProfileDump(dump_paths=dump_paths, dump_logger=dump_logger, config=config)

    #     path_to_del = group_store.get_entry(uuid=groups[0].uuid).path

    #     _ = orm.Group.collection.delete(groups[0].pk)

    #     profile_dump.delete_missing_groups()
    #     assert path_to_del

    #     # assert profile_dump.get_groups_to_delete() == [groups[0].uuid]

    #     # _ = orm.Group.collection.delete(groups[1].pk)
    #     # assert profile_dump.get_groups_to_delete() == [group.uuid for group in groups]

    #     # to_delete_uuid = ProfileDump.get_groups_to_delete()
    #     # assert to_delete_uuid[0] == group_uuid

    #     # import ipdb

    #     # profile_dump

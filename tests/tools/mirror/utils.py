###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################

from pathlib import Path

# __all__ = ()

# tree_add_calc = {
#     "ArithmeticAddCalculation-4": [
#         ".aiida_mirror_safeguard",
#         ".aiida_node_metadata.yaml",
#         {"inputs": [
#             "_aiidasubmit.sh",
#             "aiida.in",
#             {".aiida": ["calcinfo.json", "job_tmpl.json"]},
#         ]},
#         {"node_inputs": []},
#         {"outputs": [
#             "_scheduler-stderr.txt",
#             "_scheduler-stdout.txt",
#             "aiida.out",
#         ]},
#     ],
# }

# tree_multiply_add_calc = {
#     "MultiplyAddWorkChain-5": [
#         ".aiida_mirror_safeguard",
#         ".aiida_node_metadata.yaml",
#         {"01-multiply-6": [
#             ".aiida_node_metadata.yaml",
#             {"inputs": ["source_file"]},
#             {"node_inputs": []},
#         ]},
#         {"02-ArithmeticAddCalculation-8": [
#             ".aiida_node_metadata.yaml",
#             {"inputs": [
#                 "_aiidasubmit.sh",
#                 "aiida.in",
#                 {".aiida": ["calcinfo.json", "job_tmpl.json"]},
#             ]},
#             {"node_inputs": []},
#             {"outputs": [
#                 "_scheduler-stderr.txt",
#                 "_scheduler-stdout.txt",
#                 "aiida.out",
#             ]},
#         ]},
#     ],
# }

# def compare_tree(expected: dict, base_path: Path, relative_path: Path = Path()):
#     """Recursively compares an expected directory structure with an actual path.

#     Args:
#         expected (dict): The expected directory structure.
#         base_path (Path): The root directory where the actual structure is located.
#         relative_path (Path): The relative path inside the base directory (used internally for recursion).
#     """
#     for dir_name, content_list in expected.items():
#         dir_path = base_path / relative_path / dir_name
        
#         assert dir_path.exists(), f"Path does not exist: {dir_path}"
#         assert dir_path.is_dir(), f"Path is not a directory: {dir_path}"
        
#         for item in content_list:
#             if isinstance(item, str):  # It's a file
#                 file_path = dir_path / item
#                 assert file_path.exists(), f"Missing file: {file_path}"
#                 assert file_path.is_file(), f"Expected a file: {file_path}"
#             elif isinstance(item, dict):  # It's a subdirectory
#                 # Recursively check the subdirectory
#                 compare_tree(item, base_path, relative_path / dir_name)

def compare_tree(expected: dict, base_path: Path, relative_path: Path = Path()):
    """Recursively compares an expected directory structure with an actual path.
    Verifies both that all expected elements exist and that no unexpected elements exist.

    Args:
        expected (dict): The expected directory structure.
        base_path (Path): The root directory where the actual structure is located.
        relative_path (Path): The relative path inside the base directory (used internally for recursion).
    """
    for dir_name, content_list in expected.items():
        dir_path = base_path / relative_path / dir_name
        
        assert dir_path.exists(), f"Path does not exist: {dir_path}"
        assert dir_path.is_dir(), f"Path is not a directory: {dir_path}"
        
        # Extract all expected files and subdirectories at this level
        expected_entries = set()
        expected_dirs = {}
        
        for item in content_list:
            if isinstance(item, str):  # It's a file
                expected_entries.add(item)
                file_path = dir_path / item
                assert file_path.exists(), f"Missing file: {file_path}"
                assert file_path.is_file(), f"Expected a file: {file_path}"
            elif isinstance(item, dict):  # It's a subdirectory
                # Get the subdirectory name (the first key in the dict)
                subdir_name = next(iter(item))
                expected_entries.add(subdir_name)
                expected_dirs[subdir_name] = item
                # Recursively check the subdirectory
                compare_tree(item, base_path, relative_path / dir_name)
        
        # Check for unexpected entries
        actual_entries = set(entry.name for entry in dir_path.iterdir())
        unexpected_entries = actual_entries - expected_entries
        
        assert not unexpected_entries, f"Unexpected entries found in {dir_path}: {unexpected_entries}"


def compare_tree_only_dirs(expected: dict, base_path: Path, relative_path: Path = Path()):
    """Recursively compares an expected directory structure with an actual path,
    focusing only on directories and ignoring files.

    Args:
        expected (dict): The expected directory structure.
        base_path (Path): The root directory where the actual structure is located.
        relative_path (Path): The relative path inside the base directory (used internally for recursion).
    """
    for dir_name, content_list in expected.items():
        dir_path = base_path / relative_path / dir_name
        
        assert dir_path.exists(), f"Path does not exist: {dir_path}"
        assert dir_path.is_dir(), f"Path is not a directory: {dir_path}"
        
        # Extract all expected subdirectories at this level
        expected_dirs = {}
        
        for item in content_list:
            if isinstance(item, dict):  # It's a subdirectory
                # Get the subdirectory name (the first key in the dict)
                subdir_name = next(iter(item))
                expected_dirs[subdir_name] = item
        
        # Check for unexpected directories
        actual_dirs = {entry.name: entry for entry in dir_path.iterdir() if entry.is_dir()}
        unexpected_dirs = set(actual_dirs.keys()) - set(expected_dirs.keys())
        
        assert not unexpected_dirs, f"Unexpected directories found in {dir_path}: {unexpected_dirs}"
        
        # Recursively check the expected subdirectories
        for subdir_name, subdir_content in expected_dirs.items():
            compare_directory_structure(subdir_content, base_path, relative_path / dir_name)
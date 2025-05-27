"""File system operations for dumping."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aiida.tools.dumping.config import DumpConfig


class FileSystemManager:
    """Handles all file system operations."""

    SAFEGUARD_FILE_NAME = '.aiida_dump_safeguard'

    def __init__(self, config: 'DumpConfig'):
        self.config = config

    def prepare_directory(self, path: Path, is_leaf_node_dir: bool = False) -> None:
        """Prepare directory for dumping."""
        from aiida.tools.dumping.config import DumpMode

        if self.config.dump_mode == DumpMode.DRY_RUN:
            return

        if self.config.dump_mode == DumpMode.OVERWRITE:
            if path.exists() and os.listdir(path) and not (path / self.SAFEGUARD_FILE_NAME).exists():
                if is_leaf_node_dir:
                    self.delete_directory(path)
                else:
                    raise FileNotFoundError(f'Path {path} exists, is not empty, but safeguard file missing.')

        path.mkdir(parents=True, exist_ok=True)
        (path / self.SAFEGUARD_FILE_NAME).touch(exist_ok=True)

    def delete_directory(self, path: Path) -> None:
        """Safely delete directory if it contains safeguard file."""
        from aiida.tools.dumping.config import DumpMode

        if self.config.dump_mode == DumpMode.DRY_RUN:
            return

        safeguard = path / self.SAFEGUARD_FILE_NAME
        if path.is_dir() and safeguard.is_file():
            shutil.rmtree(path)

    def create_symlink(self, source: Path, target: Path) -> None:
        """Create relative symlink."""
        if target.exists() or target.is_symlink():
            return

        if not source.exists():
            return

        target.parent.mkdir(parents=True, exist_ok=True)
        relative_src_path = os.path.relpath(source, start=target.parent)
        os.symlink(relative_src_path, target, target_is_directory=True)

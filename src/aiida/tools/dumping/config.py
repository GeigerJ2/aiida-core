###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Type

from aiida import orm
from aiida.common import timezone

__all__ = (
    'BaseCollectionDumperConfig',
    'DumpCollectorConfig',
    'DumpMode',
    'DumpPaths',
    'DumpTimes',
    'GroupDumperConfig',
    'NodeDumpGroupScope',
    'ProcessDumperConfig',
    'ProfileDumperConfig',
)


class DumpMode(Enum):
    OVERWRITE = auto()
    INCREMENTAL = auto()
    DRY_RUN = auto()


class NodeDumpGroupScope(Enum):
    IN_GROUP = auto()
    ANY = auto()
    NO_GROUP = auto()


class DumpStoreKeys(str, Enum):
    CALCULATIONS = 'calculations'
    WORKFLOWS = 'workflows'
    GROUPS = 'groups'
    DATA = 'data'

    @classmethod
    def from_instance(cls, node_inst: orm.Node | orm.Group) -> str:
        if isinstance(node_inst, orm.CalculationNode):
            return cls.CALCULATIONS.value
        elif isinstance(node_inst, orm.WorkflowNode):
            return cls.WORKFLOWS.value
        elif isinstance(node_inst, orm.Data):
            return cls.DATA.value
        elif isinstance(node_inst, orm.Group):
            return cls.GROUPS.value
        else:
            msg = f'Dumping not implemented yet for node type: {type(node_inst)}'
            raise NotImplementedError(msg)

    @classmethod
    def from_class(cls, orm_class: Type) -> str:
        if issubclass(orm_class, orm.CalculationNode):
            return cls.CALCULATIONS.value
        elif issubclass(orm_class, orm.WorkflowNode):
            return cls.WORKFLOWS.value
        elif issubclass(orm_class, orm.Data):
            return cls.DATA.value
        elif issubclass(orm_class, orm.Group):
            return cls.GROUPS.value
        else:
            msg = f'Dumping not implemented yet for node type: {orm_class}'
            raise NotImplementedError(msg)

    @classmethod
    def to_class(cls, key: 'DumpStoreKeys') -> Type:
        mapping = {
            cls.CALCULATIONS: orm.CalculationNode,
            cls.WORKFLOWS: orm.WorkflowNode,
            cls.DATA: orm.Data,
            cls.GROUPS: orm.Group,
        }
        if key in mapping:
            return mapping[key]
        else:
            msg = f'No node type mapping exists for key: {key}'
            raise ValueError(msg)


# NOTE: Should this be a singleton?
@dataclass
class DumpTimes:
    _instance = None
    last: datetime | None = None
    # Fixed time set at instantiation
    _current: datetime = field(default_factory=timezone.now)
    # start: datetime | None = field(default_factory=timezone.now)
    range_start: datetime | None = None
    range_end: datetime | None = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def current(self) -> datetime:
        """
        Returns the fixed time that was set upon instantiation of the class.
        """
        return self._current

    @classmethod
    def from_file(cls, dump_paths: 'DumpPaths') -> 'DumpTimes':
        try:
            with dump_paths.log_path.open('r', encoding='utf-8') as f:
                prev_dump_data = json.load(f)
                return cls(last=datetime.fromisoformat(prev_dump_data['last_dump_time']))
        except:
            raise


@dataclass
class DumpPaths:
    parent: Path = field(default_factory=Path.cwd)
    child: Path = field(default_factory=lambda: Path('aiida-dump'))
    top_level: Path = field(default=None, init=True)  # Added top_level property

    safeguard_file = '.aiida_dump_safeguard'

    def __post_init__(self):
        # Set top_level during initialization if not provided
        if self.top_level is None:
            self.top_level = self.parent / self.child  # Default to parent if not specified

    @classmethod
    def from_path(cls, path: Path):
        return cls(parent=path.parent, child=Path(path.name))

    @property
    def absolute(self) -> Path:
        """Returns the absolute path by joining parent and child."""
        return self.parent / self.child

    @property
    def safeguard_path(self) -> Path:
        """Returns the path to a safeguard file."""
        return self.absolute / self.safeguard_file

    @property
    def log_path(self) -> Path:
        from aiida.tools.dumping.logger import DumpLogger

        """Returns the path of the logger JSON."""
        return self.absolute / DumpLogger.dump_LOG_FILE

    # NOTE: Should this return a new instance?
    def extend_paths(self, subdir: str) -> 'DumpPaths':
        """
        Creates a new DumpPaths instance with an additional subdirectory.

        Args:
            subdir: The name of the subdirectory to add

        Returns:
            A new DumpPaths instance with the updated path structure
        """
        return DumpPaths(parent=self.absolute, child=Path(subdir))


@dataclass
class DumpCollectorConfig:
    """Shared arguments for dumping of collections of nodes."""

    get_processes: bool = True
    get_data: bool = False
    filter_by_last_dump_time: bool = True
    only_top_level_calcs: bool = True
    only_top_level_workflows: bool = True
    group_scope: NodeDumpGroupScope = NodeDumpGroupScope.IN_GROUP


@dataclass
class ProcessDumperConfig:
    """Arguments for dumping process data."""

    include_inputs: bool = True
    include_outputs: bool = False
    include_attributes: bool = True
    include_extras: bool = True
    flat: bool = False
    dump_unsealed: bool = False
    symlink_calcs: bool = False


@dataclass
class BaseCollectionDumperConfig:
    symlink_calcs: bool = False
    delete_missing: bool = False  # TODO


@dataclass
class GroupDumperConfig(BaseCollectionDumperConfig):
    """Arguments for dumping group data."""

    ...


@dataclass
class ProfileDumperConfig(BaseCollectionDumperConfig):
    """Arguments for dumping profile data."""

    organize_by_groups: bool = True
    also_ungrouped: bool = False
    update_groups: bool = False
    symlink_between_groups: bool = False  # TODO

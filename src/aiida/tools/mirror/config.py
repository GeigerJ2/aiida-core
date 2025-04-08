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
    'BaseCollectionMirrorConfig',
    'GroupMirrorConfig',
    'MirrorMode',
    'MirrorPaths',
    'MirrorTimes',
    'MirrorCollectorConfig',
    'NodeMirrorGroupScope',
    'ProcessMirrorConfig',
    'ProfileMirrorConfig',
)


class MirrorMode(Enum):
    OVERWRITE = auto()
    INCREMENTAL = auto()
    DRY_RUN = auto()


class NodeMirrorGroupScope(Enum):
    IN_GROUP = auto()
    ANY = auto()
    NO_GROUP = auto()


class MirrorStoreKeys(str, Enum):
    CALCULATIONS = 'calculations'
    WORKFLOWS = 'workflows'
    GROUPS = 'groups'
    DATA = 'data'

    @classmethod
    def from_instance(cls, node_inst: orm.Node) -> str:
        match node_inst:
            case orm.CalculationNode():
                return cls.CALCULATIONS.value
            case orm.WorkflowNode():
                return cls.WORKFLOWS.value
            case orm.Data():
                return cls.DATA.value
            case orm.Group():
                return cls.GROUPS.value
            case _:
                msg = f'Mirroring not implemented yet for node type: {type(node_inst)}'
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
            msg = f'Mirroring not implemented yet for node type: {orm_class}'
            raise NotImplementedError(msg)

    @classmethod
    def to_class(cls, key: 'MirrorStoreKeys') -> Type[orm.Node]:
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


@dataclass
class MirrorTimes:
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
    def from_file(cls, mirror_paths: 'MirrorPaths') -> 'MirrorTimes':
        try:
            with mirror_paths.log_path.open('r', encoding='utf-8') as f:
                prev_mirror_data = json.load(f)
                return cls(last=datetime.fromisoformat(prev_mirror_data['last_mirror_time']))
        except:
            raise


@dataclass
class MirrorPaths:
    parent: Path = Path.cwd
    child: Path = Path('aiida-mirror')

    @classmethod
    def from_path(cls, path: Path):
        return cls(parent=path.parent, child=path.name)

    @property
    def absolute(self) -> Path:
        """Returns the absolute path by joining parent and child."""
        return self.parent / self.child

    @property
    def safeguard(self) -> Path:
        """Returns the path to a safeguard file."""
        return self.absolute / '.aiida_mirror_safeguard'

    @property
    def log_path(self) -> Path:
        from aiida.tools.mirror.logger import MirrorLogger

        """Returns the path of the logger JSON."""
        return self.absolute / MirrorLogger.MIRROR_LOG_FILE

    # NOTE: Should this return a new instance?
    def extend_paths(self, subdir: str) -> 'MirrorPaths':
        """
        Creates a new MirrorPaths instance with an additional subdirectory.

        Args:
            subdir: The name of the subdirectory to add

        Returns:
            A new MirrorPaths instance with the updated path structure
        """
        return MirrorPaths(parent=self.absolute, child=Path(subdir))


@dataclass
class MirrorCollectorConfig:
    """Shared arguments for mirroring of collections of nodes."""

    get_processes: bool = True
    get_data: bool = False
    filter_by_last_mirror_time: bool = True
    only_top_level_calcs: bool = True
    only_top_level_workflows: bool = True
    group_scope: NodeMirrorGroupScope = NodeMirrorGroupScope.IN_GROUP


@dataclass
class ProcessMirrorConfig:
    """Arguments for mirroring process data."""

    include_inputs: bool = True
    include_outputs: bool = False
    include_attributes: bool = True
    include_extras: bool = True
    flat: bool = False
    mirror_unsealed: bool = False
    symlink_calcs: bool = False


@dataclass
class BaseCollectionMirrorConfig:
    symlink_calcs: bool = False
    delete_missing: bool = False  # TODO


@dataclass
class GroupMirrorConfig(BaseCollectionMirrorConfig):
    """Arguments for mirroring group data."""

    ...


@dataclass
class ProfileMirrorConfig(BaseCollectionMirrorConfig):
    """Arguments for mirroring profile data."""

    organize_by_groups: bool = True  # TODO
    only_groups: bool = False
    update_groups: bool = False
    symlink_between_groups: bool = False  # TODO

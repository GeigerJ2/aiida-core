###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path

from aiida.common import timezone

__all__ = (
    'NodeMirrorGroupScope',
    'MirrorMode',
    'NodeCollectorConfig',
    'ProcessMirrorConfig',
    'BaseCollectionMirrorConfig',
    'GroupMirrorConfig',
    'ProfileMirrorConfig',
    'MirrorPaths',
    'MirrorTimes'
)


class NodeMirrorGroupScope(Enum):
    IN_GROUP = auto()
    ANY = auto()
    NO_GROUP = auto()


class MirrorMode(Enum):
    OVERWRITE = auto()
    INCREMENTAL = auto()
    DRY_RUN = auto()


@dataclass
class MirrorTimes:
    last: datetime | None = None
    current: datetime | None = field(default_factory=timezone.now)
    range_start: datetime | None = None
    range_end: datetime | None = None


# NOTE: Could also add logger and safeguard file path here
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
    def safeguard_path(self) -> Path:
        """Returns the path to a safeguard file."""
        return self.absolute / '.aiida_mirror_safeguard'

    @property
    def logger_path(self) -> Path:
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
class NodeCollectorConfig:
    """Shared arguments for mirroring of collections of nodes."""

    # NOTE: Should the `last_mirror_time` also be here
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

    organize_by_groups: bool = True
    only_groups: bool = False
    update_groups: bool = True  # TODO
    symlink_between_groups: bool = False  # TODO

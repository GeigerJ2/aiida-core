###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################

from __future__ import annotations

from dataclasses import dataclass, fields
from enum import Enum, auto

__all__ = (
    'DumpDetectionConfig',
    'DumpMode',
    'GroupDumpConfig',
    'NodeDumpGroupScope',
    'ProcessDumpConfig',
    'ProfileDumpConfig',
)


class DumpMode(Enum):
    OVERWRITE = auto()
    INCREMENTAL = auto()
    DRY_RUN = auto()


class NodeDumpGroupScope(Enum):
    IN_GROUP = auto()
    ANY = auto()
    NO_GROUP = auto()


@dataclass
class DumpConfig:
    """Unified configuration for all dump operations."""

    # Global options
    dump_mode: DumpMode = DumpMode.INCREMENTAL

    # Node collection options
    get_processes: bool = True
    get_data: bool = False
    filter_by_last_dump_time: bool = True
    only_top_level_calcs: bool = True
    only_top_level_workflows: bool = True
    group_scope: NodeDumpGroupScope = NodeDumpGroupScope.IN_GROUP

    # Process dump options
    include_inputs: bool = True
    include_outputs: bool = False
    include_attributes: bool = True
    include_extras: bool = True
    flat: bool = False
    dump_unsealed: bool = False
    symlink_calcs: bool = False

    # Group options
    delete_missing: bool = False

    # Profile options
    organize_by_groups: bool = True
    also_ungrouped: bool = False
    update_groups: bool = False
    symlink_between_groups: bool = False

    def get_collector_config(self) -> DumpDetectionConfig:
        """Extract configuration for DumpCollector."""
        return DumpDetectionConfig(
            get_processes=self.get_processes,
            get_data=self.get_data,
            filter_by_last_dump_time=self.filter_by_last_dump_time,
            only_top_level_calcs=self.only_top_level_calcs,
            only_top_level_workflows=self.only_top_level_workflows,
            group_scope=self.group_scope,
        )

    def get_process_config(self) -> ProcessDumpConfig:
        """Extract configuration for ProcessDumper."""
        return ProcessDumpConfig(
            include_inputs=self.include_inputs,
            include_outputs=self.include_outputs,
            include_attributes=self.include_attributes,
            include_extras=self.include_extras,
            flat=self.flat,
            dump_unsealed=self.dump_unsealed,
            symlink_calcs=self.symlink_calcs,
        )

    def get_group_config(self) -> GroupDumpConfig:
        """Extract configuration for GroupDumper."""
        return GroupDumpConfig(symlink_calcs=self.symlink_calcs, delete_missing=self.delete_missing)

    def get_profile_config(self) -> ProfileDumpConfig:
        """Extract configuration for ProfileDumper."""
        return ProfileDumpConfig(
            symlink_calcs=self.symlink_calcs,
            delete_missing=self.delete_missing,
            organize_by_groups=self.organize_by_groups,
            also_ungrouped=self.also_ungrouped,
            update_groups=self.update_groups,
            symlink_between_groups=self.symlink_between_groups,
        )

    @classmethod
    def from_component_configs(
        cls,
        process_config: ProcessDumpConfig | None = None,
        group_config: GroupDumpConfig | None = None,
        profile_config: ProfileDumpConfig | None = None,
        detection_config: DumpDetectionConfig | None = None,
    ) -> 'DumpConfig':
        """Construct a unified config from component configs."""
        config = cls()

        # Update from process config if provided
        if process_config:
            for field in fields(ProcessDumpConfig):
                if hasattr(process_config, field.name):
                    setattr(config, field.name, getattr(process_config, field.name))

        # Update from group config if provided
        if group_config:
            for field in fields(GroupDumpConfig):
                if hasattr(group_config, field.name):
                    setattr(config, field.name, getattr(group_config, field.name))

        # Update from profile config if provided
        if profile_config:
            for field in fields(ProfileDumpConfig):
                if hasattr(profile_config, field.name):
                    setattr(config, field.name, getattr(profile_config, field.name))

        # Update from collector config if provided
        if detection_config:
            for field in fields(DumpDetectionConfig):
                if hasattr(detection_config, field.name):
                    setattr(config, field.name, getattr(detection_config, field.name))

        return config


@dataclass
class DumpDetectionConfig:
    """Shared arguments for dumping of collections of nodes."""

    get_processes: bool = True
    get_data: bool = False
    filter_by_last_dump_time: bool = True
    only_top_level_calcs: bool = True
    only_top_level_workflows: bool = True
    group_scope: NodeDumpGroupScope = NodeDumpGroupScope.IN_GROUP


@dataclass
class ProcessDumpConfig:
    """Arguments for dumping process data."""

    include_inputs: bool = True
    include_outputs: bool = False
    include_attributes: bool = True
    include_extras: bool = True
    flat: bool = False
    dump_unsealed: bool = False
    symlink_calcs: bool = False


@dataclass
class GroupDumpConfig:
    """Arguments for dumping group data."""

    symlink_calcs: bool = False
    delete_missing: bool = False


@dataclass
class ProfileDumpConfig:
    """Arguments for dumping profile data."""

    symlink_calcs: bool = False
    delete_missing: bool = False
    organize_by_groups: bool = True
    also_ungrouped: bool = False
    update_groups: bool = False
    symlink_between_groups: bool = False  # TODO

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

from pathlib import Path
from aiida import orm
from aiida.tools.mirror.config import MirrorPaths, MirrorTimes, ProfileMirrorConfig
from aiida.tools.mirror.logger import MirrorLog, MirrorLogger
from aiida.tools.mirror.profile import ProfileMirror

from .utils import compare_tree, tree_add_calc  # tree_multip


class TestProfileMirror:

    _profile_mirror_path = Path("profile-mirror")
    _add_group_label = "add-group"
    _multiply_add_group_label = "multiply-add-group"

    def test_mirror_per_group(self): ...

    def test_mirror_not_in_any_group(self): ...

    def test_do_mirror_add_group(self, tmp_path, setup_add_group):
        add_group = setup_add_group
        mirror_paths = MirrorPaths.from_path(tmp_path / self._profile_mirror_path)
        profile_mirror_inst = ProfileMirror(mirror_paths=mirror_paths)
        profile_mirror_inst.do_mirror()
        import ipdb

        ipdb.set_trace()
        compare_tree(
            expected=tree_add_calc,
            base_path=tmp_path,
            relative_path=self._profile_mirror_path / "groups" / self._add_group_label / 'calculations',
        )

    def test_do_mirror_multiply_add_group(self): ...

    def test_do_mirror_no_group(self): ...

    def test_do_mirror_no_group(self): ...

    def test_do_mirror_organize_by_groups(self): ...

    def test_do_mirror_only_groups(self): ...


def test_delete_missing_group_nodes_retained(): ...


def test_delete_missing_group_nodes_deleted(): ...


@pytest.mark.usefixtures("aiida_profile_clean")
def test_get_groups_to_delete(tmp_path):
    # NOTE: `mirror_logger` and `profile_mirror.mirror_loger` if I construct the `profile_mirror` here and already
    # attach the `mirror_logger`...?
    mirror_paths = MirrorPaths.from_path(tmp_path)
    mirror_logger = MirrorLogger(mirror_paths=mirror_paths)
    groups = []
    for i in range(2):
        group_label = f"group-{i}"
        group = orm.Group(label=group_label)
        group.store()
        mirror_logger.add_entry(
            store=mirror_logger.stores.groups,
            uuid=group.uuid,
            entry=MirrorLog(mirror_path=tmp_path / group_label),
        )
        groups.append(group)

    config = ProfileMirrorConfig(delete_missing=True)
    profile_mirror = ProfileMirror(
        mirror_paths=mirror_paths, mirror_logger=mirror_logger, config=config
    )
    _ = orm.Group.collection.delete(groups[0].pk)

    assert profile_mirror.get_groups_to_delete() == [groups[0].uuid]

    _ = orm.Group.collection.delete(groups[1].pk)
    assert profile_mirror.get_groups_to_delete() == [group.uuid for group in groups]


@pytest.mark.usefixtures("aiida_profile_clean")
def test_del_missing_groups(tmp_path):
    # NOTE: `mirror_logger` and `profile_mirror.mirror_loger` if I construct the `profile_mirror` here and already
    # attach the `mirror_logger`...?
    mirror_paths = MirrorPaths.from_path(tmp_path)
    mirror_logger = MirrorLogger(mirror_paths=mirror_paths)
    mirror_times = MirrorTimes()
    group_store = mirror_logger.stores.groups
    groups = []
    for i in range(2):
        group_label = f"group-{i}"
        group = orm.Group(label=group_label)
        group.store()
        mirror_logger.add_entry(
            store=mirror_logger.stores.groups,
            uuid=group.uuid,
            entry=MirrorLog(mirror_path=tmp_path / group_label),
        )
        groups.append(group)

    config = ProfileMirrorConfig(delete_missing=True)
    profile_mirror = ProfileMirror(
        mirror_paths=mirror_paths, mirror_logger=mirror_logger, config=config
    )

    path_to_del = group_store.get_entry(uuid=groups[0].uuid).mirror_path

    # import ipdb; ipdb.set_trace()
    _ = orm.Group.collection.delete(groups[0].pk)

    profile_mirror.delete_missing_groups()
    assert path_to_del

    # assert profile_mirror.get_groups_to_delete() == [groups[0].uuid]

    # _ = orm.Group.collection.delete(groups[1].pk)
    # assert profile_mirror.get_groups_to_delete() == [group.uuid for group in groups]

    # to_delete_uuid = ProfileMirror.get_groups_to_delete()
    # assert to_delete_uuid[0] == group_uuid

    # import ipdb

    # ipdb.set_trace()

    # profile_mirror

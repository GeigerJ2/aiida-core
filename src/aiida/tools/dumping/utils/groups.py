from pathlib import Path

from aiida import orm
from aiida.common.exceptions import NotExistent


def load_given_groups(groups: list[orm.Group | str]) -> list[orm.Group]:
    """Load groups from identifiers."""
    return_groups: list[orm.Group] = []
    for group in groups:
        loaded_group = load_given_group(group=group)
        if loaded_group is None:
            msg = 'Cannot be None'
            raise ValueError(msg)
        else:
            return_groups.append(loaded_group)

    return return_groups


def load_given_group(group: orm.Group | str | None) -> orm.Group | None:
    """Validate and load a group identifier."""
    if isinstance(group, str):
        try:
            return orm.load_group(group)
        except NotExistent:
            raise
        except:
            raise
    elif isinstance(group, orm.Group):
        return group
    else:
        return None


def get_group_subpath(group: orm.Group) -> Path:
    """Get the subpath for a group based on its entry point."""
    group_entry_point = group.entry_point
    if group_entry_point is None:
        return Path(group.label)

    group_entry_point_name = group_entry_point.name
    if group_entry_point_name == 'core':
        return Path(f'{group.label}')
    if group_entry_point_name == 'core.import':
        return Path('import') / f'{group.label}'

    group_subpath = Path(*group_entry_point_name.split('.'))

    return group_subpath / f'{group.label}'

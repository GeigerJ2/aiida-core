from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from aiida import orm
from aiida.common import timezone
from aiida.common.log import AIIDA_LOGGER
from aiida.manage.configuration import Profile
from aiida.tools.dumping.config import DumpMode

logger = AIIDA_LOGGER.getChild('tools.dumping.utils.paths')

__all__ = (
    'DumpPaths',
    'generate_group_default_dump_path',
    'generate_process_default_dump_path',
    'generate_profile_default_dump_path',
    'prepare_dump_path',
    'resolve_click_path_for_dump',
    'safe_delete_dir',
)


@dataclass
class DumpPaths:
    parent: Path = field(default_factory=Path.cwd)
    child: Path = field(default_factory=lambda: Path('aiida-dump'))
    top_level: Path = field(default=None, init=True)  # Added top_level property

    safeguard_file = '.aiida_dump_safeguard'
    log_file: str = '.aiida_dump_log.json'

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
        """Returns the path of the logger JSON."""
        return self.absolute / self.log_file

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


# NOTE: Could move to BaseDump class
def prepare_dump_path(
    path_to_validate: Path,
    dump_mode: DumpMode,
    safeguard_file: str = DumpPaths.safeguard_file,
    top_level_caller: bool = True,
) -> None:
    # TODO: Add an option to clean the path here
    """Create default dumping directory for a given process node and return it as absolute path.

    :param validate_path: Path to validate for dumping.
    :param safeguard_file: Dumping-specific file that indicates that the directory indeed originated from a `verdi ...
        dump` command to avoid accidentally deleting wrong directory.
        Default: `.aiida_node_metadata.yaml`
    :return: The absolute created dump path.
    :raises ValueError: If both `overwrite` and `incremental` are set to True.
    :raises FileExistsError: If a file or non-empty directory exists at the given path and none of `overwrite` or
        `incremental` are enabled.
    :raises FileNotFoundError: If no `safeguard_file` is found."""

    if path_to_validate.is_file():
        msg = f'A file at the given path `{path_to_validate}` already exists.'
        raise FileExistsError(msg)

    if not path_to_validate.is_absolute():
        msg = f'The path to validate must be an absolute path. Got `{path_to_validate}.'
        raise ValueError(msg)

    # Additional logging for top-level directory
    # Don't want to repeat that for all sub-directories created during dumping
    if top_level_caller:
        if dump_mode == DumpMode.INCREMENTAL:
            msg = 'Incremental dumping selected. Will update directory.'
        elif dump_mode == DumpMode.OVERWRITE:
            msg = 'Overwriting selected. Will clean directory first.'

        logger.report(msg)

    # Handle existing non-empty directory
    if path_to_validate.is_dir() and any(path_to_validate.iterdir()) and dump_mode == DumpMode.OVERWRITE:
        safe_delete_dir(
            path=path_to_validate,
            safeguard_file=safeguard_file,
        )

    # Check if path is symlink, otherwise `mkdir` fails
    if path_to_validate.is_symlink():
        return
    # Finally, (re-)create directory
    # Both shutil.rmtree and `_delete_dir_recursively` delete the original dir
    # If it already existed, e.g. in the `incremental` case, exist_ok=True
    path_to_validate.mkdir(exist_ok=True, parents=True)
    path_to_safeguard_file = path_to_validate / safeguard_file
    if not path_to_safeguard_file.is_file():
        path_to_safeguard_file.touch()


def safe_delete_dir(
    path: Path,
    safeguard_file: str = DumpPaths.safeguard_file,
) -> None:
    """Also deletes the top-level directory itself."""

    if not path.exists():
        return

    is_empty = not any(path.iterdir())
    if is_empty:
        path.rmdir()
        return

    safeguard_exists = (path / safeguard_file).is_file()

    if safeguard_exists:
        try:
            _delete_dir_recursive(path)
            # shutil.rmtree(path_to_validate)
        except OSError:
            # `shutil.rmtree` fails for symbolic links with
            # OSError: Cannot call rmtree on a symbolic link
            _delete_dir_recursive(path)

    else:
        msg = (
            f'Path `{path.name}` exists without safeguard file `{safeguard_file}`. '
            f'Not removing because path might be a directory not created by AiiDA.'
        )
        raise FileNotFoundError(msg)


def _delete_dir_recursive(path):
    """
    Delete folder, sub-folders and files.
    Implementation taken from: https://stackoverflow.com/a/70285390/9431838
    """
    for f in path.glob('**/*'):
        if f.is_symlink():
            f.unlink(missing_ok=True)  # missing_ok is added in python 3.8
        elif f.is_file():
            f.unlink()
        elif f.is_dir():
            try:
                f.rmdir()  # delete empty sub-folder
            except OSError:  # sub-folder is not empty
                _delete_dir_recursive(f)  # recurse the current sub-folder
            except Exception as exception:  # capture other exception
                msg = f'exception name: {exception.__class__.__name__}\nexception msg: {exception}'
                logger.critical(msg)

    try:
        path.rmdir()  # time to delete an empty folder
    except NotADirectoryError:
        path.unlink()  # delete folder even if it is a symlink, linux
    except Exception as exception:
        msg = f'exception name: {exception.__class__.__name__}\nexception msg: {exception}'
        logger.critical(msg)


def generate_process_default_dump_path(
    process_node: orm.ProcessNode, prefix: str | None = None, append_pk: bool = True
) -> Path:
    """Simple helper function to generate the default parent-dumping directory if none given.

    This function is not called for the recursive sub-calls of `_dump_calculation` as it just creates the default
    parent folder for the dumping, if no name is given.

    :param process_node: The `ProcessNode` for which the directory is created.
    :return: The absolute default parent dump path.
    """

    path_entities = []

    if prefix is not None:
        path_entities += [prefix]

    if process_node.label:
        path_entities.append(process_node.label)
    elif process_node.process_label is not None:
        path_entities.append(process_node.process_label)
    elif process_node.process_type is not None:
        path_entities.append(process_node.process_type)

    if append_pk:
        path_entities += [str(process_node.pk)]
    return Path('-'.join(path_entities))


def generate_profile_default_dump_path(profile: Profile, prefix: str = 'profile', appendix: str = 'dump') -> Path:
    return Path(f'{prefix}-{profile.name}-{appendix}')


def generate_group_default_dump_path(group: orm.Group | None, prefix: str = 'group', appendix: str = 'dump') -> Path:
    # TODO: Or, make sure dump not in the group name?
    if not group:
        label_elements = ['no-group', appendix]

    elif 'group' in group.label:
        if appendix == 'group' and prefix != 'group':
            label_elements = [prefix, group.label]
        elif prefix == 'group' and appendix != 'group':
            label_elements = [group.label, appendix]
        elif prefix == 'group' and appendix == 'group':
            label_elements = [group.label]
        else:
            label_elements = [prefix, group.label, appendix]

    elif 'dump' in group.label:
        if appendix == 'dump' and prefix != 'dump':
            label_elements = [prefix, group.label]
        elif prefix == 'dump' and appendix != 'dump':
            label_elements = [group.label, appendix]
        elif prefix == 'dump' and appendix == 'dump':
            label_elements = [group.label]
        else:
            label_elements = [prefix, group.label, appendix]

    else:
        label_elements = [prefix, group.label, appendix]

    return Path('-'.join(label_elements))


# entity: orm.ProcessNode | orm.Group | Profile
def resolve_click_path_for_dump(path: Path | None | str, entity: Any) -> DumpPaths:
    # First check if the entity is of a supported type
    if not isinstance(entity, (orm.ProcessNode, orm.Group, Profile)):
        supported_types = 'ProcessNode, Group, Profile'
        msg = f"Unsupported entity type '{type(entity).__name__}'. Supported types: {supported_types}."
        raise ValueError(msg)

    if path:
        path = Path(path)
        if path.is_absolute():
            dump_sub_path = Path(path.name)
            dump_parent_path = path.parent
        else:
            dump_sub_path = path
            dump_parent_path = Path.cwd()
    else:
        # Use direct isinstance checks to determine which generator to use
        if isinstance(entity, orm.ProcessNode):
            dump_sub_path = generate_process_default_dump_path(entity)
        elif isinstance(entity, orm.Group):
            dump_sub_path = generate_group_default_dump_path(entity)
        elif isinstance(entity, Profile):
            dump_sub_path = generate_profile_default_dump_path(entity)

        dump_parent_path = Path.cwd()

    return DumpPaths(
        parent=dump_parent_path,
        child=dump_sub_path,
    )


def get_directory_stats(path: Path) -> tuple[datetime | None, int | None]:
    """
    Calculate the total size and last modification time of a directory's contents.

    Args:
        path: The directory path.

    Returns:
        A tuple containing:
            - datetime | None: The most recent modification time among all files/dirs,
                               made timezone-aware (UTC assumed if naive).
            - int | None: The total size in bytes of all files within the directory.
                          Returns None if the path doesn't exist or isn't a directory.
    """
    total_size = 0
    latest_mtime_ts = 0.0  # Use float timestamp for comparison

    try:
        if not path.is_dir():
            logger.debug(f'Path {path} is not a directory, cannot calculate stats.')
            return None, None

        # Get mtime of the directory itself initially
        latest_mtime_ts = path.stat().st_mtime

        # Iterate through all files and directories recursively
        for entry in path.rglob('*'):
            try:
                stat_info = entry.stat()
                if entry.is_file():
                    total_size += stat_info.st_size
                # Update latest mtime if this entry is newer
                latest_mtime_ts = max(stat_info.st_mtime, latest_mtime_ts)
            except (OSError, FileNotFoundError) as stat_err:
                # Ignore errors for files/dirs that might disappear during iteration
                logger.debug(f'Could not stat entry {entry}: {stat_err}')

        # Convert the latest timestamp to a timezone-aware datetime object
        latest_mtime_dt = datetime.fromtimestamp(latest_mtime_ts)
        latest_mtime_aware = timezone.make_aware(latest_mtime_dt)  # Assumes local time if naive

        return latest_mtime_aware, total_size

    except (FileNotFoundError, PermissionError) as e:
        logger.error(f'Could not access path {path} to calculate stats: {e}')
        return None, None
    except Exception as e:
        logger.error(f'Unexpected error calculating stats for {path}: {e}', exc_info=True)
        return None, None

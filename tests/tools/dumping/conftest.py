import pytest

from aiida.tools.dumping.config import DumpConfig
from aiida.tools.dumping.content import ContentGenerator
from aiida.tools.dumping.dumper import NodeDumper
from aiida.tools.dumping.filesystem import FileSystemManager
from aiida.tools.dumping.paths import PathResolver
from aiida.tools.dumping.planner import DumpPlanner
from aiida.tools.dumping.tracking import DumpTracker
from aiida.tools.dumping.utils import DumpPaths


@pytest.fixture
def mock_dump_tracker(tmp_path):
    """Fixture providing a DumpTracker instance without loading from file."""
    config = DumpConfig()
    dump_paths = DumpPaths(base_output_path=tmp_path / 'mock_dump', config=config)
    return DumpTracker(dump_paths=dump_paths, last_dump_time_str=None)


@pytest.fixture
def node_dumper(mock_dump_tracker, tmp_path):
    """Fixture providing an initialized NodeDumper (replaces ProcessDumpExecutor)."""
    config = DumpConfig()
    base_path = tmp_path / 'dumper_test'

    # Initialize all components
    fs_manager = FileSystemManager(config)
    path_resolver = PathResolver(config, base_path)
    content_generator = ContentGenerator(config)
    planner = DumpPlanner(config, mock_dump_tracker)

    # Create the main dumper
    dumper = NodeDumper(
        planner=planner,
        fs_manager=fs_manager,
        content_generator=content_generator,
        path_resolver=path_resolver,
        tracker=mock_dump_tracker,
    )
    return dumper


# Optional: Keep the old fixture name for backward compatibility
@pytest.fixture
def process_dump_manager(node_dumper):
    """Legacy fixture name - points to node_dumper for backward compatibility."""
    return node_dumper


# Optional: Individual component fixtures if you need to test them separately
@pytest.fixture
def fs_manager():
    """Fixture providing FileSystemManager."""
    config = DumpConfig()
    return FileSystemManager(config)


@pytest.fixture
def path_resolver(tmp_path):
    """Fixture providing PathResolver."""
    config = DumpConfig()
    return PathResolver(config, tmp_path)


@pytest.fixture
def content_generator():
    """Fixture providing ContentGenerator."""
    config = DumpConfig()
    return ContentGenerator(config)


@pytest.fixture
def dump_planner(mock_dump_tracker):
    """Fixture providing DumpPlanner."""
    config = DumpConfig()
    return DumpPlanner(config, mock_dump_tracker)

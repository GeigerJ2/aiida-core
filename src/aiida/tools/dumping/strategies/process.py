
from aiida.common.log import AIIDA_LOGGER
from aiida.tools.dumping.entities.process import ProcessDumper
from aiida.tools.dumping.strategies.base import DumpStrategy
from aiida.tools.dumping.utils.paths import (
    DumpPaths,
    generate_process_default_dump_path,
    prepare_dump_path,
)
from aiida.tools.dumping.utils.types import DumpChanges

logger = AIIDA_LOGGER.getChild("tools.dumping.strategies.process")


class ProcessDumpStrategy(DumpStrategy):
    """Strategy for dumping a process node"""

    # Accept changes argument for consistency, but ignore it
    def dump(self, changes: DumpChanges | None = None):
        """Dumps the specific process node associated with this strategy."""
        process_node = self.entity
        if process_node is None:
            logger.error(
                "ProcessDumpStrategy executed without a valid process node entity."
            )
            return

        logger.info(
            f"Executing ProcessDumpStrategy for node: PK={process_node.pk}, UUID={process_node.uuid}"
        )

        # Path preparation logic (as before)
        process_subdir = generate_process_default_dump_path(process_node)
        process_dump_paths = DumpPaths(
            parent=self.engine.dump_paths.absolute, child=process_subdir
        )
        prepare_dump_path(
            path_to_validate=process_dump_paths.absolute,
            dump_mode=self.engine.config.dump_mode,
            safeguard_file=self.engine.dump_paths.safeguard_file,
            top_level_caller=False,
        )

        # Create ProcessDumper directly
        try:
            process_dumper = ProcessDumper(
                process_node=process_node,
                dump_mode=self.engine.config.dump_mode,
                dump_paths=process_dump_paths,
                dump_logger=self.engine.dump_logger,
                config=self.engine.config.get_process_config(),
            )
            process_dumper.dump(
                top_level_caller=True
            )  # Let ProcessDumper manage its scope
            logger.info(f"Successfully dumped process node: PK={process_node.pk}")
        except Exception as e:
            logger.error(
                f"Failed to dump process node {process_node.pk}: {e}", exc_info=True
            )

        logger.info(f"Finished ProcessDumpStrategy for node: PK={process_node.pk}")

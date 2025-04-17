# dumping/strategies/process.py
from __future__ import annotations

from typing import TYPE_CHECKING

from aiida.common.log import AIIDA_LOGGER

# REMOVE the import of ProcessDumper from entities
# from aiida.tools.dumping.entities.process import ProcessDumper
from aiida.tools.dumping.strategies.base import DumpStrategy
from aiida.tools.dumping.utils.paths import (
    prepare_dump_path,
    # DumpPaths is not needed directly here anymore
    # generate_process_default_dump_path is handled by NodeManager now
)

if TYPE_CHECKING:
    # Keep type hints
    from aiida.orm import ProcessNode
    from aiida.tools.dumping.logger import DumpLogger
    from aiida.tools.dumping.utils.types import DumpChanges


logger = AIIDA_LOGGER.getChild("tools.dumping.strategies.process")


class ProcessDumpStrategy(DumpStrategy):
    """Strategy for dumping a single process node as the top-level entity."""

    # Accept changes and logger arguments for consistency with base class / engine call
    def dump(
        self, changes: DumpChanges | None = None, dump_logger: DumpLogger | None = None
    ):
        """Dumps the specific process node associated with this strategy."""
        process_node: ProcessNode | None = self.entity
        if process_node is None:
            logger.error(
                "ProcessDumpStrategy executed without a valid process node entity."
            )
            return

        logger.info(
            f"Executing ProcessDumpStrategy for node: PK={process_node.pk}, UUID={process_node.uuid}"
        )

        # The top-level path for this dump was already resolved by the facade (ProcessDumper)
        # and is available via the engine's dump_paths.
        process_top_level_path = self.engine.dump_paths.absolute

        # 1. Prepare the top-level directory for this specific process dump
        #    This handles creation and potential overwrite based on dump_mode.
        try:
            prepare_dump_path(
                path_to_validate=process_top_level_path,
                dump_mode=self.engine.config.dump_mode,
                safeguard_file=self.engine.dump_paths.safeguard_file,
                top_level_caller=True,  # This is the top-level operation
            )
        except Exception as e:
            logger.error(
                f"Failed to prepare top-level dump path {process_top_level_path} for node {process_node.pk}: {e}",
                exc_info=True,
            )
            return  # Cannot proceed if top-level dir fails

        # 2. Delegate the actual dumping (incl. content and recursion) to NodeManager
        #    NodeManager's dump_process will handle this node and any children.
        try:
            logger.info(f"Dispatching node {process_node.pk} to NodeManager...")
            # Pass the node and the specific, prepared path where it should be dumped.
            self.engine.node_manager.dump_process(
                process_node=process_node,
                target_path=process_top_level_path,  # The node's content goes directly here
            )
            logger.info(f"NodeManager finished processing node: PK={process_node.pk}")

            # 3. Generate README for the top-level process dump (optional)
            # Call the helper via the NodeManager instance after dumping is done.
            try:
                self.engine.node_manager.readme_generator.generate(
                    process_node, process_top_level_path
                )
            except Exception as e:
                logger.warning(
                    f"Failed to generate README for process {process_node.pk}: {e}"
                )

        except Exception as e:
            # Catch potential errors during the call to NodeManager
            logger.error(
                f"Failed during NodeManager execution for process node {process_node.pk}: {e}",
                exc_info=True,
            )
            # Cleanup might be handled within NodeManager's dump_process on its internal errors

        logger.info(f"Finished ProcessDumpStrategy for node: PK={process_node.pk}")


# from aiida.common.log import AIIDA_LOGGER
# from aiida.tools.dumping.entities.process import ProcessDumper
# from aiida.tools.dumping.strategies.base import DumpStrategy
# from aiida.tools.dumping.utils.paths import (
#     DumpPaths,
#     generate_process_default_dump_path,
#     prepare_dump_path,
# )
# from aiida.tools.dumping.utils.types import DumpChanges

# logger = AIIDA_LOGGER.getChild("tools.dumping.strategies.process")


# class ProcessDumpStrategy(DumpStrategy):
#     """Strategy for dumping a process node"""

#     # Accept changes argument for consistency, but ignore it
#     def dump(self, changes: DumpChanges | None = None):
#         """Dumps the specific process node associated with this strategy."""
#         process_node = self.entity
#         if process_node is None:
#             logger.error(
#                 "ProcessDumpStrategy executed without a valid process node entity."
#             )
#             return

#         logger.info(
#             f"Executing ProcessDumpStrategy for node: PK={process_node.pk}, UUID={process_node.uuid}"
#         )

#         # Path preparation logic (as before)
#         process_subdir = generate_process_default_dump_path(process_node)
#         process_dump_paths = DumpPaths(
#             parent=self.engine.dump_paths.absolute, child=process_subdir
#         )
#         prepare_dump_path(
#             path_to_validate=process_dump_paths.absolute,
#             dump_mode=self.engine.config.dump_mode,
#             safeguard_file=self.engine.dump_paths.safeguard_file,
#             top_level_caller=False,
#         )

#         # Create ProcessDumper directly
#         try:
#             process_dumper = ProcessDumper(
#                 process_node=process_node,
#                 dump_mode=self.engine.config.dump_mode,
#                 dump_paths=process_dump_paths,
#                 dump_logger=self.engine.dump_logger,
#                 config=self.engine.config.get_process_config(),
#             )
#             process_dumper.dump(
#                 top_level_caller=True
#             )  # Let ProcessDumper manage its scope
#             logger.info(f"Successfully dumped process node: PK={process_node.pk}")
#         except Exception as e:
#             logger.error(
#                 f"Failed to dump process node {process_node.pk}: {e}", exc_info=True
#             )

#         logger.info(f"Finished ProcessDumpStrategy for node: PK={process_node.pk}")

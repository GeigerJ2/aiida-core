###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################
"""Functionality for dumping of ProcessNodes."""

from __future__ import annotations

import contextlib
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Callable

import yaml

from aiida import orm
from aiida.common import LinkType
from aiida.common.exceptions import NotExistentAttributeError
from aiida.common.log import AIIDA_LOGGER
from aiida.orm.utils import LinkTriple
from aiida.tools.dumping.config import DumpConfig

if TYPE_CHECKING:
    from aiida.tools.dumping.config import DumpConfig

logger = AIIDA_LOGGER.getChild("tools.dumping.utils.process_handlers")

# Type hint for the recursive dump function expected by WorkflowWalker
DumpProcessorType = Callable[[orm.ProcessNode, Path], None]


class NodeMetadataWriter:
    """Handles writing the .aiida_node_metadata.yaml file."""

    def __init__(self, config: "DumpConfig"):
        self.config = config

    def write(
        self,
        process_node: orm.ProcessNode,
        output_path: Path,
        output_filename: str = ".aiida_node_metadata.yaml",
    ) -> None:
        """Dump the selected ProcessNode properties, attributes, and extras to a YAML file."""
        node_properties = [
            "label",
            "description",
            "pk",
            "uuid",
            "ctime",
            "mtime",
            "node_type",
            "process_type",
            "is_finished_ok",
        ]
        user_properties = ("first_name", "last_name", "email", "institution")
        computer_properties = ("label", "hostname", "scheduler_type", "transport_type")

        metadata_dict = {
            prop: getattr(process_node, prop, None) for prop in node_properties
        }
        node_dict = {"Node data": metadata_dict}

        with contextlib.suppress(AttributeError):
            node_dbuser = process_node.user
            user_dict = {
                prop: getattr(node_dbuser, prop, None) for prop in user_properties
            }
            node_dict["User data"] = user_dict

        with contextlib.suppress(AttributeError):
            node_dbcomputer = process_node.computer
            if node_dbcomputer:  # Check if computer is assigned
                computer_dict = {
                    prop: getattr(node_dbcomputer, prop, None)
                    for prop in computer_properties
                }
                node_dict["Computer data"] = computer_dict

        if self.config.include_attributes:
            node_attributes = process_node.base.attributes.all
            if node_attributes:
                node_dict["Node attributes"] = node_attributes

        if self.config.include_extras:
            node_extras = process_node.base.extras.all
            if node_extras:
                node_dict["Node extras"] = node_extras

        output_file = output_path / output_filename
        try:
            with output_file.open("w", encoding="utf-8") as handle:
                # Use default_flow_style=None for better readability of nested structures
                yaml.dump(
                    node_dict,
                    handle,
                    sort_keys=False,
                    default_flow_style=None,
                    indent=2,
                )
        except Exception as e:
            logger.error(
                f"Failed to write YAML metadata for node {process_node.pk}: {e}"
            )


class NodeRepoIoDumper:
    """Handles dumping repository contents and linked I/O Data nodes."""

    def __init__(self, config: "DumpConfig"):
        self.config = config

    def dump_calculation_content(
        self, calculation_node: orm.CalculationNode, output_path: Path
    ) -> None:
        """Dump repository and I/O file contents for a CalculationNode."""
        io_dump_mapping = self._generate_calculation_io_mapping(flat=self.config.flat)

        # Dump the main repository contents
        try:
            repo_target = output_path / io_dump_mapping.repository
            repo_target.mkdir(parents=True, exist_ok=True)

            calculation_node.base.repository.copy_tree(repo_target)
        except Exception as e:
            logger.error(
                f"Failed copying repository for calc {calculation_node.pk}: {e}"
            )

        # Dump the repository contents of `outputs.retrieved` if it exists
        if hasattr(calculation_node.outputs, "retrieved"):
            try:
                retrieved_target = output_path / io_dump_mapping.retrieved
                retrieved_target.mkdir(parents=True, exist_ok=True)
                calculation_node.outputs.retrieved.base.repository.copy_tree(
                    retrieved_target
                )
            except Exception as e:
                logger.error(
                    f"Failed copying retrieved output for calc {calculation_node.pk}: {e}"
                )
        else:
            logger.debug(
                f"No 'retrieved' output node found for calc {calculation_node.pk}."
            )

        # Dump the node_inputs (linked Data nodes)
        # TODO: Ensure also here that no empty `node_inputs` directories are created
        if self.config.include_inputs:
            try:
                input_links = calculation_node.base.links.get_incoming(
                    link_type=LinkType.INPUT_CALC
                ).all()
                if input_links:
                    input_path = output_path / io_dump_mapping.inputs
                    input_path.mkdir(parents=True, exist_ok=True)
                    self._dump_calculation_io_files(
                        parent_path=input_path,
                        link_triples=input_links,
                    )
            except Exception as e:
                logger.error(
                    f"Failed dumping inputs for calc {calculation_node.pk}: {e}"
                )

        # Dump the node_outputs (created Data nodes, excluding 'retrieved')
        if self.config.include_outputs:
            # TODO: Possibly also use here explicit attribute chack rather than relying on try-except
            # TODO: Which might execute certain statements, then fail, and leave the result of prev. statements leftover
            try:
                output_links = calculation_node.base.links.get_outgoing(
                    link_type=LinkType.CREATE
                ).all()
                output_links_filtered = [
                    lt for lt in output_links if lt.link_label != "retrieved"
                ]
                if output_links_filtered:
                    output_path_target = output_path / io_dump_mapping.outputs
                    output_path_target.mkdir(parents=True, exist_ok=True)
                    self._dump_calculation_io_files(
                        parent_path=output_path_target,
                        link_triples=output_links_filtered,
                    )
            except Exception as e:
                logger.error(
                    f"Failed dumping outputs for calc {calculation_node.pk}: {e}"
                )

    def _dump_calculation_io_files(
        self,
        parent_path: Path,
        link_triples: list[LinkTriple],
    ):
        """Helper to dump linked input/output Data nodes."""
        for link_triple in link_triples:
            node = link_triple.node
            link_label = link_triple.link_label
            try:
                if not self.config.flat:
                    relative_parts = link_label.split("__")
                    linked_node_path = parent_path.joinpath(*relative_parts)
                else:
                    # Dump content directly into parent_path, letting copy_tree handle structure
                    linked_node_path = parent_path

                linked_node_path.parent.mkdir(parents=True, exist_ok=True)
                node.base.repository.copy_tree(linked_node_path)
            except Exception as e:
                logger.warning(
                    f"Failed copying IO node {node.pk} (link: {link_label}): {e}"
                )

    @staticmethod
    def _generate_calculation_io_mapping(flat: bool = False) -> SimpleNamespace:
        """Helper to map internal names to directory names for CalcNode I/O."""
        aiida_entities = ["repository", "retrieved", "inputs", "outputs"]
        default_dirs = ["inputs", "outputs", "node_inputs", "node_outputs"]

        if flat:
            # Empty string means dump into the parent directory itself
            mapping = {entity: "" for entity in aiida_entities}
        else:
            mapping = dict(zip(aiida_entities, default_dirs))

        return SimpleNamespace(**mapping)


class WorkflowWalker:
    """Handles traversing WorkflowNode children and triggering their dump."""

    def __init__(self, dump_processor: DumpProcessorType):
        """
        Initialize the WorkflowWalker.

        :param dump_processor: A callable (like NodeManager.dump_process) that
                               takes a node and a target path to dump it.
        """
        self.dump_processor = dump_processor

    def dump_children(self, workflow_node: orm.WorkflowNode, output_path: Path) -> None:
        """Find and recursively dump children of a WorkflowNode."""
        try:
            called_links = workflow_node.base.links.get_outgoing(
                link_type=(LinkType.CALL_CALC, LinkType.CALL_WORK)
            ).all()
            called_links = sorted(
                called_links, key=lambda link_triple: link_triple.node.ctime
            )
        except Exception as e:
            logger.error(
                f"Failed getting children for workflow {workflow_node.pk}: {e}"
            )
            return

        for index, link_triple in enumerate(called_links, start=1):
            child_node = link_triple.node
            # Use static method from NodeManager to generate label consistently
            from aiida.tools.dumping.managers.node import ProcessNodeManager

            child_label = ProcessNodeManager._generate_child_node_label(
                index=index, link_triple=link_triple
            )
            child_output_path = output_path / child_label
            assert isinstance(child_node, orm.ProcessNode)
            try:
                # Call the provided dump_processor function for the child
                self.dump_processor(
                    child_node,
                    child_output_path,
                )
            except Exception as e:
                logger.error(
                    f"Failed dumping child node {child_node.pk} of workflow {workflow_node.pk}: {e}",
                    exc_info=True,
                )


class ReadmeGenerator:
    """Handles generating README.md files for process nodes."""

    def generate(self, process_node: orm.ProcessNode, output_path: Path) -> None:
        """Generate README.md file in the specified output path."""
        import textwrap

        # Ensure these imports are available or handle ImportErrors
        try:
            from aiida.cmdline.utils.ascii_vis import format_call_graph
            from aiida.cmdline.utils.common import (
                get_calcjob_report,
                get_node_info,
                get_process_function_report,
                get_workchain_report,
            )
        except ImportError:
            logger.warning(
                "Could not import AiiDA cmdline utils for README generation. Skipping."
            )
            return

        pk = process_node.pk
        _readme_string = textwrap.dedent(
            f"""\
            # AiiDA Process Dump: {process_node.process_label or process_node.process_type} <{pk}>

            This directory contains files related to the AiiDA process node {pk}.
            - **UUID:** {process_node.uuid}
            - **Type:** {process_node.node_type}

            Sub-directories (if present) represent called calculations or workflows, ordered by creation time.
            File/directory structure within a calculation node:
            - `inputs/`: Contains scheduler submission script (`_aiidasubmit.sh`), stdin file (`aiida.in`), and internal
            AiiDA info (`.aiida/`).
            - `outputs/`: Contains files retrieved by the parser (e.g., `aiida.out`, `_scheduler-stdout.txt`,
            `_scheduler-stderr.txt`).
            - `node_inputs/`: Contains repositories of input data nodes linked via `INPUT_CALC`.
            - `node_outputs/`: Contains repositories of output data nodes linked via `CREATE` (excluding `retrieved`).
            - `.aiida_node_metadata.yaml`: Human-readable metadata, attributes, and extras of this node.
            """
        )

        # Add status, report, show info
        try:
            _readme_string += (
                f"\n## Process Status (`verdi process status {pk}`)\n\n```\n"
                f"{format_call_graph(process_node)}\n```\n"
            )
        except Exception as e:
            logger.debug(f"Could not format call graph for README: {e}")

        try:
            if isinstance(process_node, orm.CalcJobNode):
                report = get_calcjob_report(process_node)
            # TODO: Fix and uncomment
            # elif isinstance(process_node, orm.WorkChainNode):
            #     report = get_workchain_report(process_node)
            elif isinstance(process_node, (orm.CalcFunctionNode, orm.WorkFunctionNode)):
                report = get_process_function_report(process_node)
            else:
                report = "N/A"
            _readme_string += f"\n## Process Report (`verdi process report {pk}`)\n\n```\n{report}\n```\n"
        except Exception as e:
            logger.debug(f"Could not generate process report for README: {e}")

        try:
            _readme_string += (
                f"\n## Node Info (`verdi node show {process_node.uuid}`)\n\n```\n"
                "{get_node_info(process_node)}\n```\n"
            )
        except Exception as e:
            logger.debug(f"Could not get node info for README: {e}")

        try:
            (output_path / "README.md").write_text(_readme_string, encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to write README for node {process_node.pk}: {e}")

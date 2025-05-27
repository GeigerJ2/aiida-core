"""Content generation for node dumps."""

from __future__ import annotations

import contextlib
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

import yaml

from aiida import orm
from aiida.common import LinkType
from aiida.orm.utils import LinkTriple

if TYPE_CHECKING:
    from aiida.tools.dumping.config import DumpConfig


class ContentGenerator:
    """Generates dump content for nodes."""

    def __init__(self, config: 'DumpConfig'):
        self.config = config

    def generate_all_content(self, node: orm.ProcessNode, output_path: Path) -> None:
        """Generate all content for a node."""
        self._generate_metadata(node, output_path)

        if isinstance(node, orm.CalculationNode):
            self._generate_calculation_content(node, output_path)
        elif isinstance(node, orm.WorkflowNode):
            self._generate_workflow_content(node, output_path)

    def _generate_metadata(self, node: orm.ProcessNode, output_path: Path) -> None:
        """Generate metadata YAML file."""
        node_properties = [
            'label',
            'description',
            'pk',
            'uuid',
            'ctime',
            'mtime',
            'node_type',
            'process_type',
            'is_finished_ok',
        ]
        user_properties = ('first_name', 'last_name', 'email', 'institution')
        computer_properties = ('label', 'hostname', 'scheduler_type', 'transport_type')

        metadata_dict = {prop: getattr(node, prop, None) for prop in node_properties}
        node_dict = {'Node data': metadata_dict}

        with contextlib.suppress(AttributeError):
            node_dbuser = node.user
            user_dict = {prop: getattr(node_dbuser, prop, None) for prop in user_properties}
            node_dict['User data'] = user_dict

        with contextlib.suppress(AttributeError):
            node_dbcomputer = node.computer
            if node_dbcomputer:
                computer_dict = {prop: getattr(node_dbcomputer, prop, None) for prop in computer_properties}
                node_dict['Computer data'] = computer_dict

        if self.config.include_attributes:
            node_attributes = node.base.attributes.all
            if node_attributes:
                node_dict['Node attributes'] = node_attributes

        if self.config.include_extras:
            node_extras = node.base.extras.all
            if node_extras:
                node_dict['Node extras'] = node_extras

        output_file = output_path / 'aiida_node_metadata.yaml'
        with output_file.open('w', encoding='utf-8') as handle:
            yaml.dump(node_dict, handle, sort_keys=False, default_flow_style=None, indent=2)

    def _generate_calculation_content(self, node: orm.CalculationNode, output_path: Path) -> None:
        """Generate calculation-specific content."""
        io_mapping = self._get_calculation_io_mapping()

        # Repository content
        repo_target = output_path / io_mapping.repository
        repo_target.mkdir(parents=True, exist_ok=True)
        node.base.repository.copy_tree(repo_target)

        # Retrieved output
        if hasattr(node.outputs, 'retrieved') and node.outputs.retrieved is not None:
            retrieved_target = output_path / io_mapping.retrieved
            retrieved_target.mkdir(parents=True, exist_ok=True)
            node.outputs.retrieved.base.repository.copy_tree(retrieved_target)

        # Input files
        if self.config.include_inputs:
            input_links = node.base.links.get_incoming(link_type=LinkType.INPUT_CALC).all()
            if input_links:
                input_path = output_path / io_mapping.inputs
                self._dump_io_files(input_path, input_links)

        # Output files
        if self.config.include_outputs:
            output_links = node.base.links.get_outgoing(link_type=LinkType.CREATE).all()
            output_links_filtered = [link for link in output_links if link.link_label != 'retrieved']
            has_dumpable_output = any(
                isinstance(link.node, (orm.SinglefileData, orm.FolderData)) for link in output_links_filtered
            )
            if output_links_filtered and has_dumpable_output:
                output_path_target = output_path / io_mapping.outputs
                output_path_target.mkdir(parents=True, exist_ok=True)
                self._dump_io_files(output_path_target, output_links_filtered)

    def _generate_workflow_content(self, node: orm.WorkflowNode, output_path: Path) -> None:
        """Generate workflow-specific content (children will be handled by orchestrator)."""
        pass  # Children handled by NodeDumper recursively

    def _dump_io_files(self, parent_path: Path, link_triples: list[LinkTriple]) -> None:
        """Dump linked I/O files."""
        for link_triple in link_triples:
            node = link_triple.node
            link_label = link_triple.link_label

            if not self.config.flat:
                relative_parts = link_label.split('__')
                linked_node_path = parent_path.joinpath(*relative_parts)
            else:
                linked_node_path = parent_path

            if node.base.repository.list_object_names():
                linked_node_path.parent.mkdir(parents=True, exist_ok=True)
                node.base.repository.copy_tree(linked_node_path)

    def _get_calculation_io_mapping(self) -> SimpleNamespace:
        """Get I/O directory mapping."""
        aiida_entities = ['repository', 'retrieved', 'inputs', 'outputs']
        default_dirs = ['inputs', 'outputs', 'node_inputs', 'node_outputs']

        if self.config.flat:
            mapping = {entity: '' for entity in aiida_entities}
        else:
            mapping = dict(zip(aiida_entities, default_dirs))

        return SimpleNamespace(**mapping)

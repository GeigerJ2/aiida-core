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

from pathlib import Path
from typing import TYPE_CHECKING

from aiida import orm
from aiida.common.exceptions import NotExistent
from aiida.common.log import AIIDA_LOGGER
from aiida.tools.dumping.config import DumpConfig
from aiida.tools.dumping.engine import DumpEngine
from aiida.tools.dumping.utils.paths import (
    DumpPaths,
    generate_process_default_dump_path,
)

if TYPE_CHECKING:
    from aiida.tools.dumping.config import DumpConfig

# TODO: See if I can always use name, or pass the dumping sub module explicitly

logger = AIIDA_LOGGER.getChild("tools.dumping.entities.process")


class ProcessDumper:
    """Facade to initiate dumping of a single ProcessNode."""

    def __init__(
        self,
        process: orm.ProcessNode | int | str,
        config: DumpConfig | None = None,
        output_path: str | Path | None = None,  # Changed from dump_paths
    ):
        """
        Initialize the ProcessDumper facade.

        :param process: The ProcessNode instance or its PK, UUID, or label.
        :param config: The DumpConfig instance. If None, a default config is used.
        :param output_path: The destination path for the dump. If None, a default is generated.
        """
        self.process = ProcessDumper._load_process_node(process)
        self.config = config or DumpConfig()

        # Resolve DumpPaths based on output_path and the node
        if output_path is None:
            default_path = generate_process_default_dump_path(process_node=self.process)
            self.dump_paths = DumpPaths(parent=Path.cwd(), child=default_path)
        else:
            self.dump_paths = DumpPaths.from_path(output_path)

        # Create the engine, passing the context
        self.engine = DumpEngine(
            config=self.config,
            dump_paths=self.dump_paths,
            # top_level_entity_type='process' # Pass context
        )

    @staticmethod
    def _load_process_node(identifier: orm.ProcessNode | int | str) -> orm.ProcessNode:
        """Load the process node from its identifier."""
        if isinstance(identifier, orm.ProcessNode):
            return identifier
        try:
            return orm.load_node(identifier=identifier)
        except NotExistent as exc:
            raise ValueError(
                f"Process node with identifier '{identifier}' not found."
            ) from exc
        except Exception as exc:
            raise ValueError(
                f"Error loading process node '{identifier}': {exc}"
            ) from exc

    def dump(self) -> None:
        """Perform the dump operation by invoking the engine."""
        logger.info(
            f"Initiating dump for ProcessNode PK={self.process.pk} via DumpEngine."
        )
        # The engine will select the ProcessDumpStrategy
        self.engine.dump(entity=self.process)
        logger.info(f"Dump completed for ProcessNode PK={self.process.pk}.")


# class ProcessDumper(BaseDumper):
#     """Class to handle dumping of an AiiDA process."""

#     def __init__(
#         self,
#         process: orm.ProcessNode,
#         # TODO: This is now part of the global config. Here, still only ProcessDumperConfig available, so needed. Could
#         # change.
#         dump_paths: DumpPaths,
#         dump_logger: DumpLogger,
#         config: ProcessDumpConfig,
#         dump_times: DumpTimes,
#         dump_mode: DumpMode = DumpMode.INCREMENTAL,
#     ) -> None:
#         """Initialize the ProcessDump."""

#         self.process = process
#         self.dump_logger = dump_logger
#         self.dump_paths = dump_paths
#         self.config = config
#         self.dump_times = dump_times
#         # self.config = config or ProcessDumperConfig()

#         super().__init__(
#             dump_mode=dump_mode,
#             dump_paths=dump_paths,
#         )

#     def _generate_readme(self) -> None:
#         """Generate README.md file in main dumping directory.

#         :param process_node: `CalculationNode` or `WorkflowNode`.
#         :param output_path: Output path for dumping.

#         """

#         import textwrap

#         from aiida.cmdline.utils.ascii_vis import format_call_graph
#         from aiida.cmdline.utils.common import (
#             get_calcjob_report,
#             get_node_info,
#             get_process_function_report,
#             get_workchain_report,
#         )

#         process_node = self.process
#         pk = process_node.pk

#         _readme_string = textwrap.dedent(
#             f"""\
#         This directory contains the files involved in the calculation/workflow
#         `{process_node.process_label} <{pk}>` run with AiiDA.

#         Child calculations/workflows (also called `CalcJob`s/`CalcFunction`s and `WorkChain`s/`WorkFunction`s in AiiDA
#         jargon) run by the parent workflow are contained in the directory tree as sub-folders and are sorted by their
#         creation time. The directory tree thus dumps the logical execution of the workflow, which can also be queried
#         by running `verdi process status {pk}` on the command line.

#         By default, input and output files of each calculation can be found in the corresponding "inputs" and "outputs"
#         directories (the former also contains the hidden ".aiida" folder with machine-readable job execution settings).
#         Additional input and output files (depending on the type of calculation) are placed in the "node_inputs" and
#         "node_outputs", respectively.

#         Lastly, every folder also contains a hidden, human-readable `.aiida_node_metadata.yaml` file with the relevant
#         AiiDA node data for further inspection."""
#         )

#         # `verdi process status`
#         process_status = format_call_graph(calc_node=process_node, max_depth=None, call_link_label=True)
#         _readme_string += f'\n\n\nOutput of `verdi process status {pk}`:\n\n```shell\n{process_status}\n```'

#         # `verdi process report`
#         # Copied over from `cmd_process`
#         if isinstance(process_node, orm.CalcJobNode):
#             process_report = get_calcjob_report(process_node)
#         elif isinstance(process_node, orm.WorkChainNode):
#             process_report = get_workchain_report(process_node, levelname='REPORT', indent_size=2, max_depth=None)
#         elif isinstance(process_node, (orm.CalcFunctionNode, orm.WorkFunctionNode)):
#             process_report = get_process_function_report(process_node)
#         else:
#             process_report = f'Nothing to show for node type {process_node.__class__}'

#         _readme_string += f'\n\n\nOutput of `verdi process report {pk}`:\n\n```shell\n{process_report}\n```'

#         # `verdi process show`?
#         process_show = get_node_info(node=process_node)
#         _readme_string += f'\n\n\nOutput of `verdi process show {pk}`:\n\n```shell\n{process_show}\n```'

#         (self.dump_paths.absolute / 'README.md').write_text(_readme_string)

#     @staticmethod
#     def _generate_child_node_label(index: int, link_triple: LinkTriple, append_pk: bool = True) -> str:
#         """Small helper function to generate and clean directory label for child nodes during recursion.

#         :param index: Index assigned to step at current level of recursion.
#         :param link_triple: `LinkTriple` of `ProcessNode` explored during recursion.
#         :return: Chlild node label during recursion.
#         """
#         node = link_triple.node
#         link_label = link_triple.link_label

#         # Generate directories with naming scheme akin to `verdi process status`
#         label_list = [f'{index:02d}', link_label]

#         try:
#             process_label = node.process_label
#             if process_label is not None and process_label != link_label:
#                 label_list += [process_label]

#         except AttributeError:
#             process_type = node.process_type
#             if process_type is not None and process_type != link_label:
#                 label_list += [process_type]

#         if append_pk:
#             label_list += [str(node.pk)]

#         node_label = '-'.join(label_list)
#         # `CALL-` as part of the link labels also for MultiplyAddWorkChain -> Seems general enough, so remove
#         node_label = node_label.replace('CALL-', '')
#         return node_label.replace('None-', '')

#     def dump(
#         self,
#         io_dump_paths: list[str | Path] | None = None,
#         top_level_caller: bool = True,
#     ) -> None:
#         """Dumps all data involved in a `ProcessNode`, including its outgoing links.

#         Note that if an outgoing link is a `WorkflowNode`, the function recursively calls itself, while files are
#         only actually created when a `CalculationNode` is reached.

#         :param process_node: The parent `ProcessNode` node to be dumped.
#         :param output_path: Custom output path where the directory tree will be created.
#         :param io_dump_paths: Subdirectories created for each `CalculationNode`.
#             Default: ['inputs', 'outputs', 'node_inputs', 'node_outputs']
#         :raises: ExportValidationError if the node is not sealed and dump_unsealed is False.
#         """
#         process_node = self.process

#         if not process_node.is_sealed and not self.config.dump_unsealed:
#             pk = process_node.pk
#             msg = f'Process `{pk}` must be sealed before it can be dumped, or `--dump-unsealed` set to True.'
#             raise ExportValidationError(msg)

#         # This here is mainly for `include_attributes` and `include_extras`.
#         # I don't want to include them in the general class `__init__`, as they don't really fit there.
#         # But the `_dump_node_yaml` function is private, so it's never called outside by the user.
#         # Setting the class attributes here dynamically is probably not a good solution, but it works for now.
#         # for key, value in kwargs.items():
#         #     setattr(self, key, value)

#         if top_level_caller:
#             prepare_dump_path(
#                 path_to_validate=self.dump_paths.absolute,
#                 dump_mode=self.dump_mode,
#                 safeguard_file=self.dump_paths.safeguard_file,
#                 top_level_caller=top_level_caller,
#             )

#             # current_mapping = self.dump_logger.build_current_group_node_mapping()
#             # self.dump_logger.group_node_mapping = current_mapping

#         if isinstance(process_node, orm.CalculationNode):
#             self._dump_calculation(
#                 calculation_node=process_node,
#                 output_path=self.dump_paths.absolute,
#                 io_dump_paths=io_dump_paths,
#             )

#         elif isinstance(process_node, orm.WorkflowNode):
#             self._dump_workflow(
#                 workflow_node=process_node,
#                 output_path=self.dump_paths.absolute,
#                 io_dump_paths=io_dump_paths,
#             )

#         if top_level_caller:
#             # When should the logger ever be None?
#             assert self.dump_logger is not None
#             self.dump_logger.save(current_dump_time=self.dump_times.current)

#     def _dump_workflow(
#         self,
#         workflow_node: orm.WorkflowNode,
#         output_path,
#         io_dump_paths: list[str | Path] | None = None,
#     ) -> None:
#         """Recursive function to traverse a `WorkflowNode` and dump its `CalculationNode` s.

#         :param workflow_node: `WorkflowNode` to be traversed. Will be updated during recursion.
#         :param output_path: Dumping parent directory. Will be updated during recursion.
#         :param io_dump_paths: Custom subdirectories for `CalculationNode` s, defaults to None
#         """

#         if not output_path:
#             output_path = self.dump_paths.absolute

#         output_path.mkdir(parents=True, exist_ok=True)

#         self._write_node_yaml(process_node=workflow_node, output_path=output_path)
#         (output_path / DumpPaths.safeguard_file).touch()

#         if self.dump_logger is not None:
#             workflow_store = self.dump_logger.get_store_by_name('workflows')

#             workflow_store.add_entry(
#                 uuid=workflow_node.uuid,
#                 entry=DumpLog(path=output_path.resolve()),
#             )

#         called_links = workflow_node.base.links.get_outgoing(link_type=(LinkType.CALL_CALC, LinkType.CALL_WORK)).all()
#         called_links = sorted(called_links, key=lambda link_triple: link_triple.node.ctime)

#         for index, link_triple in enumerate(called_links, start=1):
#             child_node = link_triple.node
#             child_label = self._generate_child_node_label(index=index, link_triple=link_triple)
#             child_output_path = output_path.resolve() / child_label

#             # Recursive function call for `WorkFlowNode`
#             if isinstance(child_node, orm.WorkflowNode):
#                 self._dump_workflow(
#                     workflow_node=child_node,
#                     output_path=child_output_path,
#                     io_dump_paths=io_dump_paths,
#                 )

#             # Once a `CalculationNode` as child reached, dump it
#             elif isinstance(child_node, orm.CalculationNode):
#                 calculation_store = self.dump_logger.get_store_by_name('calculations')

#                 # TODO: Could add a `uuid_in_store` or similarly named method

#                 if not self.config.symlink_calcs or child_node.uuid not in calculation_store.entries.keys():
#                     self._dump_calculation(
#                         calculation_node=child_node,
#                         output_path=child_output_path,
#                         io_dump_paths=io_dump_paths,
#                     )

#                 else:
#                     try:
#                         if (store_entry := calculation_store.get_entry(child_node.uuid)) is not None:
#                             os.symlink(
#                                 store_entry.path,
#                                 child_output_path,
#                             )
#                     except FileExistsError:
#                         # For debugging
#                         raise
#                 # else:
#                 #     self._dump_calculation(
#                 #         calculation_node=child_node,
#                 #         output_path=child_output_path,
#                 #         io_dump_paths=io_dump_paths,
#                 #     )

#     def _dump_calculation(
#         self,
#         calculation_node: orm.CalculationNode,
#         output_path: Path,
#         io_dump_paths: list[str | Path] | None = None,
#     ) -> None:
#         """Dump the contents of a `CalculationNode` to a specified output path.

#         :param calculation_node: The `CalculationNode` to be dumped.
#         :param output_path: The path where the files will be dumped.
#         :param io_dump_paths: Subdirectories created for the `CalculationNode`.
#             Default: ['inputs', 'outputs', 'node_inputs', 'node_outputs']
#         """

#         prepare_dump_path(
#             path_to_validate=output_path,
#             dump_mode=self.dump_mode,
#             safeguard_file=self.dump_paths.safeguard_file,
#             top_level_caller=False,
#         )

#         self._write_node_yaml(process_node=calculation_node, output_path=output_path)

#         io_dump_mapping = self._generate_calculation_io_mapping(io_dump_paths=io_dump_paths, flat=self.config.flat)

#         # Dump the repository contents of the node
#         calculation_node.base.repository.copy_tree(output_path.resolve() / io_dump_mapping.repository)

#         # Dump the repository contents of `outputs.retrieved`
#         with contextlib.suppress(NotExistentAttributeError):
#             calculation_node.outputs.retrieved.base.repository.copy_tree(
#                 output_path.resolve() / io_dump_mapping.retrieved
#             )

#         # Dump the node_inputs
#         if self.config.include_inputs:
#             input_links = calculation_node.base.links.get_incoming(link_type=LinkType.INPUT_CALC)
#             # Need to create the path before, otherwise getting Exception
#             input_path = output_path / io_dump_mapping.inputs
#             input_path.mkdir(parents=True, exist_ok=True)

#             self._dump_calculation_io_files(
#                 parent_path=output_path / io_dump_mapping.inputs,
#                 link_triples=input_links,
#             )

#         # Dump the node_outputs apart from `retrieved`
#         if self.config.include_outputs:
#             output_links = list(calculation_node.base.links.get_outgoing(link_type=LinkType.CREATE))
#             output_links = [output_link for output_link in output_links if output_link.link_label != 'retrieved']

#             self._dump_calculation_io_files(
#                 parent_path=output_path / io_dump_mapping.outputs,
#                 link_triples=output_links,
#             )

#         if self.dump_logger is not None:
#             calculation_store = self.dump_logger.get_store_by_name('calculations')

#             if calculation_node.uuid not in calculation_store.entries:
#                 calculation_store.add_entry(
#                     uuid=calculation_node.uuid,
#                     entry=DumpLog(
#                         path=output_path,
#                     ),
#                 )

#     def _dump_calculation_io_files(
#         self,
#         parent_path: Path,
#         link_triples: orm.LinkManager | list[orm.LinkTriple],
#     ):
#         """Small helper function to dump linked input/output nodes of a `orm.CalculationNode`.

#         :param parent_path: Parent directory for dumping the linked node contents.
#         :param link_triples: list of link triples.
#         """

#         for link_triple in link_triples:
#             link_label = link_triple.link_label

#             if not self.config.flat:
#                 linked_node_path = parent_path / Path(*link_label.split('__'))
#             else:
#                 # Don't use link_label at all -> But, relative path inside FolderData is retained
#                 linked_node_path = parent_path

#             link_triple.node.base.repository.copy_tree(linked_node_path.resolve())

#     @staticmethod
#     def _generate_calculation_io_mapping(
#         io_dump_paths: list[str | Path] | None = None, flat: bool = False
#     ) -> SimpleNamespace:
#         """Helper function to generate mapping for entities dumped for each `CalculationNode`.

#         This is to avoid exposing AiiDA terminology, like `repository` to the user, while keeping track of which
#         entities should be dumped into which directory, and allowing for alternative directory names.

#         :param io_dump_paths: Subdirectories created for the `CalculationNode`.
#             Default: ['inputs', 'outputs', 'node_inputs', 'node_outputs']
#         :return: SimpleNamespace mapping.
#         """

#         aiida_entities_to_dump: list[str] = [
#             'repository',
#             'retrieved',
#             'inputs',
#             'outputs',
#         ]
#         default_calculation_io_dump_paths: list[str | Path] = [
#             'inputs',
#             'outputs',
#             'node_inputs',
#             'node_outputs',
#         ]
#         if flat and io_dump_paths is None:
#             logger.report(
#                 'Flat set to True and no `io_dump_paths`. Dumping in a flat directory, files might be overwritten.'
#             )
#             empty_calculation_io_dump_paths = [''] * 4

#             return SimpleNamespace(**dict(zip(aiida_entities_to_dump, empty_calculation_io_dump_paths)))

#         if not flat and io_dump_paths is None:
#             msg = (
#                 'Flat set to False but no `io_dump_paths` provided. '
#                 + f'Will use the defaults {default_calculation_io_dump_paths}.'
#             )
#             logger.debug(msg)
#             io_dump_paths = default_calculation_io_dump_paths

#         elif flat:
#             logger.report('Flat set to True but `io_dump_paths` provided. These will be used, but `inputs` not nested.')
#         else:
#             logger.report(
#                 'Flat set to False but no `io_dump_paths` provided. These will be used, but `node_inputs` flattened.'
#             )

#         assert io_dump_paths is not None
#         return SimpleNamespace(**dict(zip(aiida_entities_to_dump, io_dump_paths)))

#     def _write_node_yaml(
#         self,
#         process_node: orm.ProcessNode,
#         output_path: Path,
#         output_filename: str = '.aiida_node_metadata.yaml',
#     ) -> None:
#         """Dump the selected `ProcessNode` properties, attributes, and extras to a YAML file.

#         :param process_node: The `ProcessNode` to dump.
#         :param output_path: The path to the directory where the YAML file will be saved.
#         :param output_filename: The name of the output YAML file. Defaults to `.aiida_node_metadata.yaml`.
#         """

#         node_properties = [
#             'label',
#             'description',
#             'pk',
#             'uuid',
#             'ctime',
#             'mtime',
#             'node_type',
#             'process_type',
#             'is_finished_ok',
#         ]

#         user_properties = ('first_name', 'last_name', 'email', 'institution')

#         computer_properties = ('label', 'hostname', 'scheduler_type', 'transport_type')

#         metadata_dict = {
#             metadata_property: getattr(process_node, metadata_property) for metadata_property in node_properties
#         }
#         node_dict = {'Node data': metadata_dict}
#         # Add user data
#         with contextlib.suppress(AttributeError):
#             node_dbuser = process_node.user
#             user_dict = {user_property: getattr(node_dbuser, user_property) for user_property in user_properties}
#             node_dict['User data'] = user_dict

#         # Add computer data
#         with contextlib.suppress(AttributeError):
#             node_dbcomputer = process_node.computer
#             computer_dict = {
#                 computer_property: getattr(node_dbcomputer, computer_property)
#                 for computer_property in computer_properties
#             }
#             node_dict['Computer data'] = computer_dict
#         # Add node attributes
#         if self.config.include_attributes:
#             node_attributes = process_node.base.attributes.all
#             node_dict['Node attributes'] = node_attributes

#         if self.config.include_extras:
#             if node_extras := process_node.base.extras.all:
#                 node_dict['Node extras'] = node_extras

#         output_file = output_path.resolve() / output_filename
#         with open(output_file, 'w') as handle:
#             yaml.dump(node_dict, handle, sort_keys=False)

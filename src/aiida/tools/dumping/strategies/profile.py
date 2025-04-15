from aiida.common.log import AIIDA_LOGGER
from aiida.tools.dumping.strategies.base import DumpStrategy

logger = AIIDA_LOGGER.getChild("tools.dumping.strategies.profile")


class ProfileDumpStrategy(DumpStrategy):
    """Strategy for dumping an entire profile"""
    
    def dump(self):
        # Update group-node mapping
        current_mapping = self.engine.dump_logger.build_current_group_node_mapping()
        self.engine.dump_logger.group_node_mapping = current_mapping
        
        # Handle all groups using the group manager
        self.engine.group_manager.handle_groups()
        
        # Handle ungrouped nodes if needed
        if self.engine.config.also_ungrouped:
            # This method would now be in the engine or another manager
            self._handle_ungrouped_nodes()
            
    def _handle_ungrouped_nodes(self):
        """Handle dumping of ungrouped nodes."""
        from aiida.tools.dumping.detect.detector import DumpChangeDetector
        from aiida.tools.dumping.config import DumpConfig, NodeDumpGroupScope
        from aiida.tools.dumping.utils.paths import DumpPaths
        
        # Create a detector specifically for ungrouped nodes
        ungrouped_detector = DumpChangeDetector(
            self.engine.dump_logger,
            # Create config with NO_GROUP scope
            DumpConfig(**{**self.engine.config.__dict__, 'group_scope': NodeDumpGroupScope.NO_GROUP}),
        )

        # Get path for ungrouped nodes
        if self.engine.config.organize_by_groups:
            no_group_path = self.engine.dump_paths.absolute / 'no-group'
        else:
            no_group_path = self.engine.dump_paths.absolute

        # Get changes for ungrouped nodes
        ungrouped_changes = ungrouped_detector.detect_changes()

        # Handle the dumping of nodes
        if ungrouped_changes['new_nodes']:
            logger.report(f"Processing ungrouped nodes")
            self.engine.node_processor.dump_nodes(ungrouped_changes['new_nodes'])

# from aiida.common.log import AIIDA_LOGGER
# from aiida.tools.dumping.strategies.base import DumpStrategy

# logger = AIIDA_LOGGER.getChild("tools.dumping.engine")


# class ProfileDumpStrategy(DumpStrategy):
#     """Strategy for dumping an entire profile"""
    
#     def dump(self):
#         # Update group-node mapping
#         current_mapping = self.engine.dump_logger.build_current_group_node_mapping()
#         self.engine.dump_logger.group_node_mapping = current_mapping
        
#         # Handle all groups
#         self.engine._handle_groups()
        
#         # Handle ungrouped nodes if needed
#         if self.engine.config.also_ungrouped:
#             self.engine._handle_ungrouped_nodes()

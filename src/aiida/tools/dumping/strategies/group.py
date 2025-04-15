
from aiida.common.log import AIIDA_LOGGER
from aiida.tools.dumping.strategies.base import DumpStrategy

logger = AIIDA_LOGGER.getChild("tools.dumping.engine")

class GroupDumpStrategy(DumpStrategy):
    """Strategy for dumping a group's contents"""
    
    def dump(self):
        # Detect changes for this group
        group = self.entity
        changes = self.engine.detector.detect_changes(group=group)
        
        # Update group structure if needed
        if self.engine.config.update_groups:
            self.engine._update_group_structure(changes['group_changes'])
            
        # Dump new nodes
        self.engine._dump_nodes(changes['new_nodes'], group)

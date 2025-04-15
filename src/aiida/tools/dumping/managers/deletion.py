from aiida.common.log import AIIDA_LOGGER
from aiida.tools.dumping.detect.detector import DumpChangeDetector
from aiida.tools.dumping.utils.paths import safe_delete_dir

logger = AIIDA_LOGGER.getChild("tools.dumping.managers.deletion")


class DeletionManager:
    """Handles deletion of nodes that no longer exist in the database."""

    def __init__(self, config, dump_paths, dump_logger):
        self.config = config
        self.dump_paths = dump_paths
        self.dump_logger = dump_logger

    def handle_deleted_nodes(self):
        """Process and delete nodes that no longer exist in the database."""
        logger.report("Checking for deleted nodes...")
        # import ipdb; ipdb.set_trace()

        # Create a detector to find deleted nodes
        detector = DumpChangeDetector(self.dump_logger, self.config)
        deleted_nodes = detector.detect_deleted_nodes()

        # Count deleted nodes of each type
        deleted_calcs_count = len(deleted_nodes.calculations)
        deleted_wfs_count = len(deleted_nodes.workflows)
        deleted_data_count = len(deleted_nodes.data)
        deleted_groups_count = len(deleted_nodes.groups)

        total_deleted = (
            deleted_calcs_count
            + deleted_wfs_count
            + deleted_data_count
            + deleted_groups_count
        )

        if total_deleted == 0:
            logger.report("No deleted nodes found.")
            return

        logger.report(
            f"Found {total_deleted} deleted nodes: "
            f"{deleted_calcs_count} calculations, "
            f"{deleted_wfs_count} workflows, "
            f"{deleted_data_count} data, "
            f"{deleted_groups_count} groups"
        )

        # Process each type of deleted node
        for store_name in ["calculations", "workflows", "data", "groups"]:
            for uuid in getattr(deleted_nodes, store_name):
                self.delete_node_from_logger(store_name, uuid)

    def delete_node_from_logger(self, store_name, uuid):
        """Remove a node from the logger and delete its directory if it exists."""
        store = getattr(self.dump_logger, store_name)
        entry = store.get_entry(uuid)

        if entry:
            path = entry.path
            logger.report(f"Deleting {store_name[:-1]} with UUID {uuid}")

            # Delete the directory if it exists
            if path.exists():
                safe_delete_dir(
                    path=path, safeguard_file=self.dump_paths.safeguard_file
                )

            # Remove from logger
            self.dump_logger.del_entry(store, uuid)

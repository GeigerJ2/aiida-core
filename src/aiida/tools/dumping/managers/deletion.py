from __future__ import annotations
from aiida.common.log import AIIDA_LOGGER
from aiida.tools.dumping.detect.detector import DumpChangeDetector
from aiida.tools.dumping.utils.types import DumpChanges, GroupInfo
from aiida.tools.dumping.utils.paths import safe_delete_dir

logger = AIIDA_LOGGER.getChild("tools.dumping.managers.deletion")


class DeletionManager:
    """Handles deletion of nodes that no longer exist in the database."""

    def __init__(self, config, dump_paths, dump_logger, detector):
        self.config = config
        self.dump_paths = dump_paths
        self.dump_logger = dump_logger
        self.detector = detector

    def handle_deleted_entities(self) -> None:
        """Detects and removes dump artifacts for entities deleted from the DB."""
        logger.info("Detecting deleted entities for removal...")

        # 1. Detect Deleted Nodes
        try:
            # Assumes detector instance is available (e.g., self.engine.detector)
            deleted_node_uuids: set[str] = self.detector.detect_deleted_nodes()
            logger.debug(f"Detected {len(deleted_node_uuids)} deleted node UUIDs.")
        except Exception as e:
            logger.error(f"Error detecting deleted nodes: {e}", exc_info=True)
            deleted_node_uuids = set()

        # 2. Detect Deleted Groups
        try:
            # Call detect_group_changes just to extract the 'deleted' part
            group_changes = self.detector.detect_group_changes(specific_group=None)
            deleted_group_info: list[GroupInfo] = group_changes.deleted
            logger.debug(f"Detected {len(deleted_group_info)} deleted groups.")
        except Exception as e:
            logger.error(f"Error detecting deleted groups: {e}", exc_info=True)
            deleted_group_info = []

        # --- Process Deletions ---
        nodes_processed = False
        groups_processed = False

        # Delete Nodes
        if deleted_node_uuids:
            logger.report(f"Found {len(deleted_node_uuids)} deleted nodes to process.")
            for node_uuid in deleted_node_uuids:
                # Assume helper method exists and handles logger+disk removal
                self.delete_node_from_logger_and_disk(node_uuid)
            nodes_processed = True
        # No need for explicit "else: logger.info(...)" here if report covers count

        # Delete Groups
        if deleted_group_info:
            logger.report(f"Found {len(deleted_group_info)} deleted groups to process.")
            for group_info in deleted_group_info:
                # Assume helper method exists and handles logger+disk removal
                self.delete_group_from_logger_and_disk(group_info.uuid)
            groups_processed = True
        # No need for explicit "else: logger.info(...)" here if report covers count

        # Save logger only if deletions occurred
        if nodes_processed or groups_processed:
            logger.info("Saving log after processing deletions.")
            self.dump_logger.save_log()
        else:
            # Use report level for user feedback
            logger.report("No deleted entities found requiring removal.")

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

    def handle_deletions_from_changes(self, changes: DumpChanges):
        logger.report("Handling deletions based on detected changes...")

        # 1. Delete Nodes
        node_uuids_to_delete = changes.nodes.deleted
        if node_uuids_to_delete:
            logger.report(
                f"Found {len(node_uuids_to_delete)} deleted nodes to process."
            )
            for node_uuid in node_uuids_to_delete:
                self.delete_node_from_logger_and_disk(
                    node_uuid
                )  # Assumes helper method exists

        # 2. Delete Groups
        group_info_to_delete = changes.groups.deleted
        if group_info_to_delete:
            logger.report(
                f"Found {len(group_info_to_delete)} deleted groups to process."
            )
            for group_info in group_info_to_delete:
                self.delete_group_from_logger_and_disk(
                    group_info.uuid
                )  # Assumes helper method exists

        if not node_uuids_to_delete and not group_info_to_delete:
            logger.report("No deleted entities found requiring action.")

        # Save logger if changes were made
        if node_uuids_to_delete or group_info_to_delete:
            self.dump_logger.save_log()

    def delete_node_from_logger_and_disk(self, uuid: str):
        """Helper to remove node entry from logger and delete dump directory."""
        # Find which store the node belongs to (calc, work, data)
        store_key = None
        for key in ["calculations", "workflows", "data"]:
            store = getattr(self.dump_logger, key, None)
            if store and uuid in store.entries:
                store_key = key
                break
        if not store_key:
            logger.warning(f"Could not find logger store for deleted node UUID {uuid}")
            return

        store = getattr(self.dump_logger, store_key)
        entry = store.get_entry(uuid)
        safe_delete_dir(path=entry.path)
        self.delete_node_from_logger(store_name=store_key, uuid=uuid)

    def delete_group_from_logger_and_disk(self, uuid: str):
        """Helper to remove group entry from logger and delete dump directory."""
        store = self.dump_logger.groups
        entry = store.get_entry(uuid)
        safe_delete_dir(path=entry.path)
        self.delete_node_from_logger(store_name="groups", uuid=uuid)

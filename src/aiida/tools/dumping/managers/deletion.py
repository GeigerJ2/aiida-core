# dumping/managers/deletion.py
from __future__ import annotations

from typing import TYPE_CHECKING

# No longer needs orm or QueryBuilder
from aiida.common.log import AIIDA_LOGGER
from aiida.tools.dumping.utils.paths import DumpPaths, safe_delete_dir

# Import DumpChanges to receive deletion info
from aiida.tools.dumping.utils.types import DumpChanges

logger = AIIDA_LOGGER.getChild('tools.dumping.managers.deletion')

if TYPE_CHECKING:
     from aiida.tools.dumping.config import DumpConfig
     from aiida.tools.dumping.storage.logger import DumpLogger


class DeletionManager:
    """Executes deletion of dumped artifacts based on provided changes."""

    def __init__(self, config: DumpConfig, dump_paths: DumpPaths, dump_logger: DumpLogger):
        self.config: DumpConfig = config
        self.dump_paths: DumpPaths = dump_paths
        self.dump_logger: DumpLogger = dump_logger

    def handle_deleted_entities(self, changes: DumpChanges) -> bool:
        """
        Removes dump artifacts for entities marked as deleted in the changes object.
        Returns True if any deletions were performed, False otherwise.
        """
        something_deleted = False
        node_uuids_to_delete = changes.nodes.deleted
        group_info_to_delete = changes.groups.deleted # List of GroupInfo objects

        if not node_uuids_to_delete and not group_info_to_delete:
            logger.info('No deleted entities identified in changes object.')
            return False

        logger.info('Processing deletions based on detected changes...')

        # --- Process Node Deletions ---
        if node_uuids_to_delete:
            logger.report(f'Removing artifacts for {len(node_uuids_to_delete)} deleted nodes...')
            for node_uuid in node_uuids_to_delete:
                if self.delete_node_from_logger_and_disk(node_uuid):
                    something_deleted = True
        else:
            logger.info('No deleted nodes to process.')

        # --- Process Group Deletions ---
        if group_info_to_delete:
            logger.report(f'Removing artifacts for {len(group_info_to_delete)} deleted groups...')
            # Extract UUIDs from the GroupInfo objects
            group_uuids_to_delete = {g.uuid for g in group_info_to_delete}
            for group_uuid in group_uuids_to_delete:
                 if self.delete_group_from_logger_and_disk(group_uuid):
                      something_deleted = True
        else:
            logger.info('No deleted groups to process.')

        return something_deleted

    # _detect_deleted_nodes - REMOVED
    # _detect_deleted_groups - REMOVED

    # delete_node_from_logger_and_disk - Stays the same as in previous response
    def delete_node_from_logger_and_disk(self, uuid: str) -> bool:
        """Helper to remove node entry from logger and delete dump directory."""
        store = self.dump_logger.get_store_by_uuid(uuid)
        if not store:
            logger.warning(f'Could not find logger store for deleted node UUID {uuid}. Cannot remove.')
            return False
        entry = store.get_entry(uuid)
        if not entry:
            logger.warning(f"Log entry not found for UUID {uuid} in its store. Cannot remove.")
            return False
        path_to_delete = entry.path
        # Determine store key for deletion from logger
        store_key = next((s_name for s_name in ['calculations', 'workflows', 'data']
                          if getattr(self.dump_logger, s_name, None) == store), None)
        if not store_key:
             logger.error(f"Consistency error: Could not determine store key name for node {uuid}.")
             return False

        logger.report(f"Deleting directory '{path_to_delete.relative_to(self.dump_paths.parent)}' for deleted node UUID {uuid}")
        try:
            safe_delete_dir(path=path_to_delete, safeguard_file='.aiida_node_metadata.yaml')
            deleted_from_log = self.dump_logger.del_entry(store_key=store_key, uuid=uuid)
            if not deleted_from_log:
                 logger.warning(f"Failed to remove log entry for deleted node {uuid} although directory was likely removed.")
            return True
        except FileNotFoundError as e:
             logger.warning(f"Safeguard check failed or directory not found for deleted node {uuid} at {path_to_delete}: {e}")
             self.dump_logger.del_entry(store_key=store_key, uuid=uuid)
             return False
        except Exception as e:
             logger.error(f"Failed to delete directory or log entry for deleted node {uuid} at {path_to_delete}: {e}", exc_info=True)
             self.dump_logger.del_entry(store_key=store_key, uuid=uuid)
             return False

    # delete_group_from_logger_and_disk - Stays the same as in previous response
    def delete_group_from_logger_and_disk(self, uuid: str) -> bool:
        """Helper to remove group entry from logger and delete dump directory (if hierarchical)."""
        group_entry = self.dump_logger.groups.get_entry(uuid)
        if not group_entry:
            logger.warning(f'Log entry not found for deleted group UUID {uuid}. Cannot remove.')
            return False
        path_to_delete = group_entry.path
        should_delete_dir = (
            self.config.organize_by_groups and
            path_to_delete != self.dump_paths.absolute
        )
        if should_delete_dir:
            logger.report(f"Deleting directory '{path_to_delete.relative_to(self.dump_paths.absolute)}' for deleted group UUID {uuid}")
            try:
                 safe_delete_dir(path=path_to_delete, safeguard_file=DumpPaths.safeguard_file)
            except FileNotFoundError as e:
                 logger.warning(f"Safeguard check failed or directory not found for deleted group {uuid} at {path_to_delete}: {e}")
            except Exception as e:
                 logger.error(f"Failed to delete directory for deleted group {uuid} at {path_to_delete}: {e}", exc_info=True)
        else:
            logger.debug(f"Not deleting directory for group {uuid} (flat structure or root path).")

        deleted_from_log = self.dump_logger.del_entry(store_key='groups', uuid=uuid)
        if not deleted_from_log:
             logger.warning(f"Failed to remove log entry for deleted group {uuid}.")
        else:
             logger.debug(f"Removed log entry for deleted group {uuid}.")
        return deleted_from_log



# from __future__ import annotations

# from typing import TYPE_CHECKING

# from aiida import orm
# from aiida.common.log import AIIDA_LOGGER
# from aiida.tools.dumping.utils.paths import safe_delete_dir
# from aiida.tools.dumping.utils.types import DumpChanges, DumpStoreKeys

# if TYPE_CHECKING:
#     from aiida.tools.dumping.config import DumpConfig
#     from aiida.tools.dumping.storage.logger import DumpLogger
#     from aiida.tools.dumping.utils.paths import DumpPaths


# logger = AIIDA_LOGGER.getChild("tools.dumping.managers.deletion")


# class DeletionManager:
#     """Handles deletion of nodes that no longer exist in the database."""

#     def __init__(
#         self, config: DumpConfig, dump_paths: DumpPaths, dump_logger: DumpLogger
#     ):
#         self.config: DumpConfig = config
#         self.dump_paths: DumpPaths = dump_paths
#         self.dump_logger: DumpLogger = dump_logger

#     def handle_deleted_entities(self) -> bool:
#         """
#         Detects and removes dump artifacts for entities deleted from the DB.
#         Returns True if any deletions were performed, False otherwise.
#         """
#         logger.info("Detecting deleted entities for removal...")
#         something_deleted = False

#         # 1. Detect Deleted Nodes
#         deleted_node_uuids = self._detect_deleted_nodes()

#         # 2. Detect Deleted Groups
#         deleted_group_uuids = self._detect_deleted_groups()

#         # --- Process Deletions ---
#         # Delete Nodes
#         if deleted_node_uuids:
#             logger.report(
#                 f"Removing artifacts for {len(deleted_node_uuids)} deleted nodes..."
#             )
#             for node_uuid in deleted_node_uuids:
#                 if self.delete_node_from_logger_and_disk(node_uuid):
#                     something_deleted = True
#         else:
#             logger.info("No deleted nodes found in log requiring removal.")

#         # Delete Groups
#         if deleted_group_uuids:
#             logger.report(
#                 f"Removing artifacts for {len(deleted_group_uuids)} deleted groups..."
#             )
#             for group_uuid in deleted_group_uuids:
#                 if self.delete_group_from_logger_and_disk(group_uuid):
#                     something_deleted = True
#         else:
#             logger.info("No deleted groups found in log requiring removal.")

#         # No need to save logger here - saving happens centrally in DumpEngine
#         # if something_deleted:
#         #     logger.info('Saving log after processing deletions.')
#         #     self.dump_logger.save(...) # Engine saves

#         return something_deleted

#     # def handle_deleted_entities(self) -> None:
#     #     """Detects and removes dump artifacts for entities deleted from the DB."""
#     #     logger.info("Detecting deleted entities for removal...")

#     #     # 1. Detect Deleted Nodes
#     #     try:
#     #         # Assumes detector instance is available (e.g., self.engine.detector)
#     #         deleted_node_uuids: set[str] = self.detector.detect_deleted_nodes()
#     #         logger.debug(f"Detected {len(deleted_node_uuids)} deleted node UUIDs.")
#     #     except Exception as e:
#     #         logger.error(f"Error detecting deleted nodes: {e}", exc_info=True)
#     #         deleted_node_uuids = set()

#     #     # 2. Detect Deleted Groups
#     #     try:
#     #         # Call detect_group_changes just to extract the 'deleted' part
#     #         group_changes = self.detector.detect_group_changes(specific_group=None)
#     #         deleted_group_info: list[GroupInfo] = group_changes.deleted
#     #         logger.debug(f"Detected {len(deleted_group_info)} deleted groups.")
#     #     except Exception as e:
#     #         logger.error(f"Error detecting deleted groups: {e}", exc_info=True)
#     #         deleted_group_info = []

#     #     # --- Process Deletions ---
#     #     nodes_processed = False
#     #     groups_processed = False

#     #     # Delete Nodes
#     #     if deleted_node_uuids:
#     #         logger.report(f"Found {len(deleted_node_uuids)} deleted nodes to process.")
#     #         for node_uuid in deleted_node_uuids:
#     #             # Assume helper method exists and handles logger+disk removal
#     #             self.delete_node_from_logger_and_disk(node_uuid)
#     #         nodes_processed = True
#     #     # No need for explicit "else: logger.info(...)" here if report covers count

#     #     # Delete Groups
#     #     if deleted_group_info:
#     #         logger.report(f"Found {len(deleted_group_info)} deleted groups to process.")
#     #         for group_info in deleted_group_info:
#     #             # Assume helper method exists and handles logger+disk removal
#     #             self.delete_group_from_logger_and_disk(group_info.uuid)
#     #         groups_processed = True
#     #     # No need for explicit "else: logger.info(...)" here if report covers count

#     #     # Save logger only if deletions occurred
#     #     if nodes_processed or groups_processed:
#     #         logger.info("Saving log after processing deletions.")
#     #         self.dump_logger.save()()
#     #     else:
#     #         # Use report level for user feedback
#     #         logger.report("No deleted entities found requiring removal.")

#     def delete_node_from_logger(self, store_name, uuid):
#         """Remove a node from the logger and delete its directory if it exists."""
#         store = getattr(self.dump_logger, store_name)
#         entry = store.get_entry(uuid)

#         if entry:
#             path = entry.path
#             logger.report(f"Deleting {store_name[:-1]} with UUID {uuid}")

#             # Delete the directory if it exists
#             if path.exists():
#                 safe_delete_dir(
#                     path=path, safeguard_file=self.dump_paths.safeguard_file
#                 )

#             # Remove from logger
#             self.dump_logger.del_entry(store, uuid)

#     def handle_deletions_from_changes(self, changes: DumpChanges):
#         logger.report("Handling deletions based on detected changes...")

#         # 1. Delete Nodes
#         node_uuids_to_delete = changes.nodes.deleted
#         if node_uuids_to_delete:
#             logger.report(
#                 f"Found {len(node_uuids_to_delete)} deleted nodes to process."
#             )
#             for node_uuid in node_uuids_to_delete:
#                 self.delete_node_from_logger_and_disk(
#                     node_uuid
#                 )  # Assumes helper method exists

#         # 2. Delete Groups
#         group_info_to_delete = changes.groups.deleted
#         if group_info_to_delete:
#             logger.report(
#                 f"Found {len(group_info_to_delete)} deleted groups to process."
#             )
#             for group_info in group_info_to_delete:
#                 self.delete_group_from_logger_and_disk(
#                     group_info.uuid
#                 )  # Assumes helper method exists

#         if not node_uuids_to_delete and not group_info_to_delete:
#             logger.report("No deleted entities found requiring action.")

#         # Save logger if changes were made
#         if node_uuids_to_delete or group_info_to_delete:
#             self.dump_logger.save()()

#     def delete_node_from_logger_and_disk(self, uuid: str):
#         """Helper to remove node entry from logger and delete dump directory."""
#         # Find which store the node belongs to (calc, work, data)
#         # TODO: Use `get_store_by_uuid` instead
#         store_key = None
#         for key in ["calculations", "workflows", "data"]:
#             store = getattr(self.dump_logger, key, None)
#             if store and uuid in store.entries:
#                 store_key = key
#                 break
#         if not store_key:
#             logger.warning(f"Could not find logger store for deleted node UUID {uuid}")
#             return

#         store = getattr(self.dump_logger, store_key)
#         entry = store.get_entry(uuid)
#         safe_delete_dir(path=entry.path)
#         self.delete_node_from_logger(store_name=store_key, uuid=uuid)

#     def delete_group_from_logger_and_disk(self, uuid: str):
#         """Helper to remove group entry from logger and delete dump directory."""
#         store = self.dump_logger.groups
#         entry = store.get_entry(uuid)
#         safe_delete_dir(path=entry.path)
#         self.delete_node_from_logger(store_name="groups", uuid=uuid)

#     # TODO: Why do I even need these methods? Shouldn't I get the changes via the `DumpChanges` object
#     def _detect_deleted_nodes(self) -> set[str]:
#         """Detect nodes logged previously but now absent from the DB."""
#         all_deleted_uuids: set[str] = set()
#         stores_coll = self.dump_logger.stores_collection

#         for store_name in [
#             "calculations",
#             "workflows",
#             "data",
#         ]:  # Check relevant node stores
#             orm_class = DumpStoreKeys.to_class(DumpStoreKeys(store_name))
#             dump_store = getattr(stores_coll, store_name)

#             if not dump_store or not dump_store.entries:
#                 continue  # Skip empty stores

#             logged_uuids = set(dump_store.entries.keys())

#             # Query DB for existing UUIDs of this type
#             try:
#                 qb = orm.QueryBuilder().append(orm_class, project=["uuid"])
#                 db_uuids = set(qb.all(flat=True))
#             except Exception as e:
#                 logger.warning(
#                     f"DB query failed while checking for deleted {orm_class.__name__}: {e}"
#                 )
#                 continue  # Skip this type on error

#             missing_uuids = logged_uuids - db_uuids
#             if missing_uuids:
#                 logger.debug(
#                     f"Found {len(missing_uuids)} deleted {orm_class.__name__} UUIDs."
#                 )
#                 all_deleted_uuids.update(missing_uuids)

#         return all_deleted_uuids

#     def _detect_deleted_groups(self) -> set[str]:
#         """Detect groups logged previously but now absent from the DB."""
#         deleted_group_uuids: set[str] = set()
#         group_store = self.dump_logger.groups  # Access group store directly

#         if not group_store or not group_store.entries:
#             return deleted_group_uuids  # No logged groups

#         logged_group_uuids = set(group_store.entries.keys())

#         # Query DB for existing group UUIDs
#         try:
#             qb = orm.QueryBuilder().append(orm.Group, project=["uuid"])
#             db_group_uuids = set(qb.all(flat=True))
#         except Exception as e:
#             logger.warning(f"DB query failed while checking for deleted Groups: {e}")
#             return deleted_group_uuids  # Return empty set on error

#         missing_group_uuids = logged_group_uuids - db_group_uuids
#         if missing_group_uuids:
#             logger.debug(f"Found {len(missing_group_uuids)} deleted Group UUIDs.")
#             deleted_group_uuids.update(missing_group_uuids)

#         return deleted_group_uuids

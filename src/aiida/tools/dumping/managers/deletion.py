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
    from aiida.tools.dumping.logger import DumpLogger


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
        group_info_to_delete = changes.groups.deleted  # List of GroupInfo objects

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

    # delete_node_from_logger_and_disk - Stays the same as in previous response
    def delete_node_from_logger_and_disk(self, uuid: str) -> bool:
        """Helper to remove node entry from logger and delete dump directory."""
        store = self.dump_logger.get_store_by_uuid(uuid)
        if not store:
            logger.warning(f'Could not find logger store for deleted node UUID {uuid}. Cannot remove.')
            return False
        entry = store.get_entry(uuid)
        if not entry:
            logger.warning(f'Log entry not found for UUID {uuid} in its store. Cannot remove.')
            return False
        path_to_delete = entry.path
        # Determine store key for deletion from logger
        store_key = next(
            (
                s_name
                for s_name in ['calculations', 'workflows', 'data']
                if getattr(self.dump_logger, s_name, None) == store
            ),
            None,
        )
        if not store_key:
            logger.error(f'Consistency error: Could not determine store key name for node {uuid}.')
            return False

        logger.report(
            f"Deleting directory '{path_to_delete.relative_to(self.dump_paths.parent)}' for deleted node UUID {uuid}"
        )
        try:
            safe_delete_dir(path=path_to_delete, safeguard_file='.aiida_node_metadata.yaml')
            deleted_from_log = self.dump_logger.del_entry(store_key=store_key, uuid=uuid)
            if not deleted_from_log:
                logger.warning(
                    f'Failed to remove log entry for deleted node {uuid} although directory was likely removed.'
                )
            return True
        except FileNotFoundError as e:
            logger.warning(
                f'Safeguard check failed or directory not found for deleted node {uuid} at {path_to_delete}: {e}'
            )
            self.dump_logger.del_entry(store_key=store_key, uuid=uuid)
            return False
        except Exception as e:
            logger.error(
                f'Failed to delete directory or log entry for deleted node {uuid} at {path_to_delete}: {e}',
                exc_info=True,
            )
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
        should_delete_dir = self.config.organize_by_groups and path_to_delete != self.dump_paths.absolute
        if should_delete_dir:
            logger.report(
                f"Deleting directory '{path_to_delete.relative_to(self.dump_paths.absolute)}' for deleted group UUID {uuid}"
            )
            try:
                safe_delete_dir(path=path_to_delete, safeguard_file=DumpPaths.safeguard_file)
            except FileNotFoundError as e:
                logger.warning(
                    f'Safeguard check failed or directory not found for deleted group {uuid} at {path_to_delete}: {e}'
                )
            except Exception as e:
                logger.error(
                    f'Failed to delete directory for deleted group {uuid} at {path_to_delete}: {e}', exc_info=True
                )
        else:
            logger.debug(f'Not deleting directory for group {uuid} (flat structure or root path).')

        deleted_from_log = self.dump_logger.del_entry(store_key='groups', uuid=uuid)
        if not deleted_from_log:
            logger.warning(f'Failed to remove log entry for deleted group {uuid}.')
        else:
            logger.debug(f'Removed log entry for deleted group {uuid}.')
        return deleted_from_log


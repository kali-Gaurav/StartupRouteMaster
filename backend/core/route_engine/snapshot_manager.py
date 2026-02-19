import pickle
import os
from datetime import datetime
from typing import Optional
import logging

from .graph import StaticGraphSnapshot

logger = logging.getLogger(__name__)

class SnapshotManager:
    """
    Manages serialization and deserialization of StaticGraphSnapshot objects.
    Aims to provide efficient saving and loading of the static graph.
    """

    def __init__(self, snapshot_dir: str = "snapshots"):
        self.snapshot_dir = snapshot_dir
        os.makedirs(self.snapshot_dir, exist_ok=True)

    def _get_snapshot_path(self, date: datetime) -> str:
        """Generates a file path for a given date's snapshot."""
        filename = f"graph_snapshot_{date.strftime('%Y%m%d')}.pkl"
        return os.path.join(self.snapshot_dir, filename)

    def save_snapshot(self, snapshot: StaticGraphSnapshot) -> Optional[str]:
        """
        Saves a StaticGraphSnapshot object to a file.
        Returns the path to the saved file if successful, None otherwise.
        """
        if not snapshot:
            logger.warning("Attempted to save an empty snapshot.")
            return None
        
        filepath = self._get_snapshot_path(snapshot.date)
        try:
            with open(filepath, 'wb') as f:
                pickle.dump(snapshot, f)
            logger.info(f"StaticGraphSnapshot for {snapshot.date.date()} saved to {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Failed to save snapshot to {filepath}: {e}")
            return None

    def load_snapshot(self, date: datetime) -> Optional[StaticGraphSnapshot]:
        """
        Loads a StaticGraphSnapshot object from a file for a given date.
        Returns the loaded snapshot if successful, None otherwise.
        """
        filepath = self._get_snapshot_path(date)
        if not os.path.exists(filepath):
            logger.info(f"No snapshot found for {date.date()} at {filepath}")
            return None
        
        try:
            with open(filepath, 'rb') as f:
                snapshot = pickle.load(f)
            logger.info(f"StaticGraphSnapshot for {date.date()} loaded from {filepath}")
            return snapshot
        except Exception as e:
            logger.error(f"Failed to load snapshot from {filepath}: {e}")
            # Consider deleting corrupted file or handling versioning
            return None

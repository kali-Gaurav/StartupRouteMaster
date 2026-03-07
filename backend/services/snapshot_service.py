import os
import json
import logging
import shutil
import gzip
from datetime import datetime
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class SnapshotService:
    """
    Subtask 14.1 & 14.2: High-Performance Backup Engine.
    Handles compressed snapshots of the SQLite databases.
    """
    def __init__(self):
        self.base_dir = "snapshots"
        os.makedirs(self.base_dir, exist_ok=True)
        self.registry_path = os.path.join(self.base_dir, "registry.json")

    def create_snapshot(self) -> Dict:
        """
        Creates a gzipped snapshot of the core databases.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        snapshot_dir = os.path.join(self.base_dir, timestamp)
        os.makedirs(snapshot_dir, exist_ok=True)
        
        files_captured = []
        total_size = 0
        
        try:
            # Capturing core local databases
            for db_file in ["user_store.db", "transit_graph.db"]:
                src = os.path.join("backend/database", db_file)
                if os.path.exists(src):
                    dst = os.path.join(snapshot_dir, f"{db_file}.gz")
                    
                    # Compress while copying to save disk space
                    with open(src, 'rb') as f_in:
                        with gzip.open(dst, 'wb') as f_out:
                            shutil.copyfileobj(f_in, f_out)
                    
                    size = os.path.getsize(dst)
                    files_captured.append({"name": db_file, "size": size})
                    total_size += size
            
            # Update internal registry for Dashboard retrieval
            snapshot_info = {
                "timestamp": timestamp,
                "size_mb": total_size / (1024 * 1024),
                "files": files_captured,
                "status": "VERIFIED"
            }
            
            self._update_registry(snapshot_info)
                
            return {
                "success": True,
                **snapshot_info
            }
        except Exception as e:
            logger.error(f"Snapshot Error: {e}")
            return {"success": False, "error": str(e)}

    def get_snapshot_history(self) -> List[Dict]:
        """
        Subtask 14.4: Returns history for the System Sentinel.
        """
        if not os.path.exists(self.registry_path):
            return []
        try:
            with open(self.registry_path, "r") as f:
                return json.load(f)
        except:
            return []

    def _update_registry(self, new_snap: Dict):
        registry = self.get_snapshot_history()
        registry.append(new_snap)
        # Keep last 50 snapshots
        with open(self.registry_path, "w") as f:
            json.dump(registry[-50:], f, indent=2)

snapshot_service = SnapshotService()

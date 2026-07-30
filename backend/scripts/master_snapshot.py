import os
import tarfile
import logging
import time
from pathlib import Path
from datetime import datetime
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nexus.snapshot")

class ProductionSnapshotForge:
    """
    [Task 92] Atomic Snapshot Utility.
    Freezes 'transit_graph', 'user_store', and critical configuration.
    Generates a single fail-safe rollback tarball.
    """
    def __init__(self, root_dir: str = "."):
        self.root_dir = Path(root_dir).resolve()
        self.artifacts_dir = self.root_dir / "snapshots"
        self.artifacts_dir.mkdir(exist_ok=True)
        
        self.critical_files = [
            "database/user_store.db",
            "database/transit_graph.db",
            "railway_data.db",
            "gunicorn_conf.py",
            "app.py",
            "requirements.txt",
            ".env.example"
        ]

    def create_snapshot(self) -> Optional[str]:
        """Saves a timestamped snapshot of critical production files."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        snapshot_name = f"nexus_snapshot_{timestamp}.tar.gz"
        snapshot_path = self.artifacts_dir / snapshot_name
        
        logger.info(f"🚀 [NEXUS:SNAPSHOT] Initiating Master Freeze: {snapshot_name}")
        
        try:
            with tarfile.open(snapshot_path, "w:gz") as tar:
                for rel_path in self.critical_files:
                    abs_path = self.root_dir / rel_path
                    if abs_path.exists():
                        tar.add(abs_path, arcname=rel_path)
                        logger.info(f"✅ Frozen: {rel_path}")
                    else:
                        logger.warning(f"⚠️ Missing: {rel_path}")
            
            logger.info(f"🏁 [NEXUS:SNAPSHOT] Forge Complete: {snapshot_path}")
            return str(snapshot_path)
        except Exception as e:
            logger.error(f"❌ Snapshot Failure: {e}")
            return None

if __name__ == "__main__":
    forge = ProductionSnapshotForge()
    forge.create_snapshot()

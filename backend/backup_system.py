import os
import shutil
import logging
from datetime import datetime
from database.config import Config

logger = logging.getLogger("backup-system")

def backup_databases():
    """
    Task 20.11: Atomic DB Backups.
    Backs up the local SQLite transit graph and emergency cache.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = os.path.join(Config.BASE_DIR, "data", "backups")
    os.makedirs(backup_dir, exist_ok=True)

    targets = [
        os.path.join(Config.BASE_DIR, "emergency_cache.json"),
        os.path.join(Config.BASE_DIR, "data", "transit_graph.db"),
        os.path.join(Config.BASE_DIR, "backend.env")
    ]

    logger.info(f"📂 Initializing System Backup: {timestamp}")

    for target in targets:
        if os.path.exists(target):
            dest = os.path.join(backup_dir, f"{os.path.basename(target)}.{timestamp}.bak")
            try:
                shutil.copy2(target, dest)
                logger.info(f"✅ Backed up {target} -> {dest}")
            except Exception as e:
                logger.error(f"❌ Backup failed for {target}: {e}")

    # Cleanup old backups (keep last 10)
    try:
        backups = sorted([os.path.join(backup_dir, f) for f in os.listdir(backup_dir)])
        if len(backups) > 30:
            for old_file in backups[:-30]:
                os.remove(old_file)
                logger.info(f"🧹 Cleaned up old backup: {old_file}")
    except Exception as e:
        logger.error(f"❌ Backup cleanup failed: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    backup_databases()

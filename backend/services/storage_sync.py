import os
import time
import logging
import asyncio
import hashlib
import zstandard as zstd
import shutil
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime

from database.config import Config
from utils.storage import storage as r2_storage

logger = logging.getLogger("routemaster.storage_sync")

class R2SyncManager:
    """
    Task 11: Cloudflare R2 & Local DB Synchronization.
    Ensures persistent storage for SQLite databases across ephemeral deployments (Railway).
    Supports bi-directional sync and periodic backups.
    """
    def __init__(self, db_paths: Optional[List[str]] = None):
        # Default critical data to sync for Nexus Fiber
        self.db_paths = db_paths or [
            "database/user_store.db",
            "database/transit_graph.db",
            "database/railway_data.db",
            "database/snapshots", # Support directory sync
            "nexus_vitals.mmap"
        ]
        self.sync_interval = 3600 # 1 hour
        self._is_syncing = False
        self.cctx = zstd.ZstdCompressor(level=3)
        self.dctx = zstd.ZstdDecompressor()

    def _get_abs_path(self, rel_path: str) -> Path:
        return Path(Config.BASE_DIR) / rel_path

    async def sync_from_r2(self, db_rel_path: str) -> bool:
        """Download remote database with checksum verification and atomic swap."""
        local_path = self._get_abs_path(db_rel_path)
        object_name = f"backups/{db_rel_path.replace('/', '_')}.zst"
        tmp_path = local_path.with_suffix(".tmp")
        
        logger.info(f"R2 Sync: Checking remote for {db_rel_path}...")
        
        loop = asyncio.get_running_loop()
        try:
            # 1. Get remote metadata (Blocking S3)
            metadata = await loop.run_in_executor(None, r2_storage.get_object_metadata, object_name)
            if not metadata:
                logger.warning(f"R2 Sync: No remote metadata found for {object_name}")
                return False

            remote_sha = metadata.get('sha256')
            
            # 2. Check local checksum (Blocking IO)
            if local_path.exists():
                local_sha = await loop.run_in_executor(None, r2_storage.calculate_sha256, local_path)
                if remote_sha == local_sha:
                    logger.info(f"R2 Sync: Local {db_rel_path} matches remote checksum. No download needed.")
                    return True
            
            # 3. Atomic Download & Decompress
            logger.info(f"R2 Sync: Downloading & Decompressing {object_name}...")
            # Ensure parent directory exists
            local_path.parent.mkdir(parents=True, exist_ok=True)
            
            zst_tmp = local_path.with_suffix(".zst.tmp")
            
            def _download_and_decompress():
                if r2_storage.download_file(object_name, zst_tmp):
                    # Decompress to .tmp
                    with open(zst_tmp, 'rb') as ifh, open(tmp_path, 'wb') as ofh:
                        self.dctx.copy_stream(ifh, ofh)
                    
                    # Atomic Replace
                    os.replace(tmp_path, local_path)
                    os.remove(zst_tmp)
                    return True
                return False

            return await loop.run_in_executor(None, _download_and_decompress)

        except Exception as e:
            logger.error(f"R2 Sync Error (Download): {e}")
            if tmp_path.exists(): os.remove(tmp_path)
            return False

    async def sync_to_r2(self, db_rel_path: str) -> bool:
        """Upload local database with compression and checksum tracking."""
        local_path = self._get_abs_path(db_rel_path)
        object_name = f"backups/{db_rel_path.replace('/', '_')}.zst"
        zst_path = local_path.with_suffix(".zst.tmp")

        if not local_path.exists():
            logger.warning(f"R2 Sync: Local file {local_path} does not exist. Skipping upload.")
            return False

        loop = asyncio.get_running_loop()
        try:
            # 1. Calculate Local Checksum
            local_sha = await loop.run_in_executor(None, r2_storage.calculate_sha256, local_path)
            
            # 2. Check if remote matches (Skip if same hash)
            metadata = await loop.run_in_executor(None, r2_storage.get_object_metadata, object_name)
            if metadata and metadata.get('sha256') == local_sha:
                logger.debug(f"R2 Sync: Remote {db_rel_path} already matches local hash. Skipping upload.")
                return True

            # 3. Compress & Upload
            logger.info(f"R2 Sync: Compressing & Uploading {db_rel_path}...")
            
            def _compress_and_upload():
                with open(local_path, 'rb') as ifh, open(zst_path, 'wb') as ofh:
                    self.cctx.copy_stream(ifh, ofh)
                    
                success = r2_storage.upload_file(
                    zst_path, 
                    object_name, 
                    metadata={'sha256': local_sha, 'original_name': str(local_path.name)}
                )
                
                if zst_path.exists(): os.remove(zst_path)
                return success

            return await loop.run_in_executor(None, _compress_and_upload)
            
        except Exception as e:
            logger.error(f"R2 Sync Error (Upload): {e}")
            if zst_path.exists(): os.remove(zst_path)
            return False

    async def full_sync_down(self):
        """Sync ALL databases/directories from R2 to local."""
        logger.info("R2 Sync: Starting full download sync...")
        
        # 1. Expand paths (Directories need to list R2 first)
        expanded_paths = []
        for rel_path in self.db_paths:
            if rel_path.endswith("/") or rel_path.split("/")[-1].find(".") == -1: # Assumption: no extension = directory
                # Prefix in R2
                prefix = f"backups/{rel_path.replace('/', '_')}"
                remote_objs = r2_storage.list_objects(prefix=prefix)
                for obj in remote_objs:
                    key = obj['Key']
                    # Convert back to rel_path (undo backups/ and _ replace)
                    # This is complex because of _ replacement.
                    # Simplification: If it's a directory, we need to know what files were uploaded.
                    pass 
            else:
                expanded_paths.append(rel_path)
                
        # Actually, let's just make sync_to_r2 and sync_from_r2 handle directories by walking them.
        tasks = [self.sync_path(path, direction="down") for path in self.db_paths]
        await asyncio.gather(*tasks)
        logger.info("R2 Sync: Full download sync complete.")

    async def full_sync_up(self):
        """Sync ALL databases/directories from local to R2."""
        logger.info("R2 Sync: Starting full backup sync...")
        tasks = [self.sync_path(path, direction="up") for path in self.db_paths]
        await asyncio.gather(*tasks)
        logger.info("R2 Sync: Full backup sync complete.")

    async def sync_path(self, rel_path: str, direction: str = "up"):
        """Sync a single file or a directory."""
        abs_path = self._get_abs_path(rel_path)
        
        if abs_path.is_dir():
            # Walk directory
            tasks = []
            for item in abs_path.iterdir():
                if item.is_file():
                    item_rel = f"{rel_path}/{item.name}"
                    if direction == "up":
                        tasks.append(self.sync_to_r2(item_rel))
                    else:
                        tasks.append(self.sync_from_r2(item_rel))
            if tasks:
                await asyncio.gather(*tasks)
        else:
            if direction == "up":
                await self.sync_to_r2(rel_path)
            else:
                await self.sync_from_r2(rel_path)

    async def run_periodic_sync(self):
        """Background task for periodic backups with orchestrator feedback."""
        from core.orchestrator import orchestrator
        logger.info(f"R2 Sync: Periodic backup worker started (Interval: {self.sync_interval}s)")
        
        while not orchestrator.is_shutting_down:
            await asyncio.sleep(self.sync_interval)
            
            # Don't sync if system is under heavy load
            from core.metrics import jit_metrics
            if jit_metrics.is_overloaded:
                logger.warning("⏳ R2 Sync: System overloaded, skipping periodic backup iteration.")
                continue

            last_start = time.time()
            try:
                await self.full_sync_up()
                # Task 2.3: Report Health
                duration = time.time() - last_start
                # You could add generic metrics here if needed
                logger.info(f"R2 Sync: Periodic sync took {duration:.2f}s")
            except Exception as e:
                logger.error(f"Periodic Sync Failure: {e}")

# CLI Entry Point [Task 2.5]
if __name__ == "__main__":
    import sys
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(description="RouteMaster R2 Sync CLI")
    parser.add_argument("command", choices=["up", "down", "restore"], help="Sync command")
    parser.add_argument("--path", help="Specific DB path to sync")
    args = parser.parse_args()

    sync_mgr = R2SyncManager()
    
    async def run():
        if args.command == "up":
            if args.path: await sync_mgr.sync_to_r2(args.path)
            else: await sync_mgr.full_sync_up()
        elif args.command == "down" or args.command == "restore":
            if args.path: await sync_mgr.sync_from_r2(args.path)
            else: await sync_mgr.full_sync_down()

    asyncio.run(run())

# Global Instance
r2_sync_manager = R2SyncManager()

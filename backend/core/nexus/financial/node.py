import logging
import asyncio
import time
from core.nexus.node import NexusNode
from services.storage_sync import r2_sync_manager

logger = logging.getLogger("nexus.financial.node")

class FinancialSentinelNode(NexusNode):
    """[Task 4.2 & 4.10] Financial Integrity Node (Layer 2)."""
    
    def __init__(self, name: str = "financial", critical: bool = True, dependencies=None):
        super().__init__(name, critical=critical, dependencies=dependencies if dependencies else ["database"])
        self.sync_mgr = r2_sync_manager
        self.sync_interval = 600 # 10 mins for financial data
        
    async def on_start(self):
        """[Task 4.2] Initialize Financial Sync Perimeter."""
        logger.info("[NEXUS:FINANCIAL] Activating Financial Sentinel (Layer 2)...")
        
        # [Task 44] Ghost-Mode Recovery Cycle
        from .recovery import saga_recovery
        await saga_recovery.scan_and_recover()
        
        # 1. Immediate Backup Sync to ensure R2 has latest state at boot
        # (This avoids data loss during crash loops)
        logger.info("[NEXUS:FINANCIAL] Performing baseline Ledger synchronization...")
        try:
            # We sync the user_store.db which holds FinancialLedger
            await self.sync_mgr.sync_to_r2("database/user_store.db")
            logger.info("[NEXUS:FINANCIAL] Baseline Sync complete.")
        except Exception as e:
            logger.error(f"[NEXUS:FINANCIAL] Initial sync failed: {e}")

        # 2. Start Periodic Sentinel Tasks [Task 4.2 & 4.3]
        self._sync_task = asyncio.create_task(self._periodic_sentinel())

    async def _periodic_sentinel(self):
        while True:
            # [Task 21] Signal Health
            from core.nexus.bootstrapper import nexus_boot
            nexus_boot.recovery.record_heartbeat(self.name)
            
            await asyncio.sleep(self.sync_interval)
            try:
                # 1. Parity Check [Task 4.3]
                from .parity import financial_parity
                if not await financial_parity.verify_system_parity():
                    logger.critical("[NEXUS:FINANCIAL] LEDGER DISCREPANCY DETECTED. Blocking payouts.")
                
                # 2. S3 Sync [Task 4.2]
                await self.sync_mgr.sync_to_r2("database/user_store.db")
                logger.info("[NEXUS:FINANCIAL] Sentinel Out-of-Band Backup Successful.")
            except Exception as e:
                logger.error(f"[NEXUS:FINANCIAL] SENTINEL BACKUP FAILURE: {e}")

    async def on_stop(self):
        """[Task 1.6 & 4.2] Final Flush before halt."""
        logger.info("[NEXUS:FINANCIAL] Final Force-Syncing Ledger to Cloudflare R2...")
        if hasattr(self, "_sync_task"):
            self._sync_task.cancel()
            
        try:
            await self.sync_mgr.sync_to_r2("database/user_store.db")
            logger.info("[NEXUS:FINANCIAL] Atomic Force-Sync complete.")
        except Exception as e:
             logger.critical(f"[NEXUS:FINANCIAL] DISASTER: FINAL SYNC FAILED: {e}")

financial_node = FinancialSentinelNode()

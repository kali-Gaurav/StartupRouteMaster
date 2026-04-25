import logging
import asyncio
from core.nexus.node import NexusNode
from .firewall import nexus_firewall

logger = logging.getLogger("nexus.security.node")

class NexusSecurityNode(NexusNode):
    """[Task 2.1 & 2.10] Nexus Security Governance Node (P0 / Layer -1)."""
    
    def __init__(self, name: str = "security", critical: bool = True, dependencies=None):
        super().__init__(name, critical=critical, dependencies=dependencies if dependencies else [])
        self.firewall = nexus_firewall
        
    async def on_start(self):
        """[Task 2.1 & 2.2] Initialize VPS Security Perimeter."""
        logger.info("[NEXUS:SECURITY] Activating VPS Security Perimeter (Layer -1)...")
        
        # 1. Firewall Baseline
        await self.firewall.allow_port(80)
        await self.firewall.allow_port(443)
        await self.firewall.allow_port(22)
        
        # 2. SSH Audit [Task 2.2]
        from .ssh_controller import ssh_hardener
        ssh_report = ssh_hardener.audit_config()
        logger.info(f"[NEXUS:SECURITY] SSH Security Status: {ssh_report['status']}")
        
        # 4. F2B Watcher [Task 2.3]
        from .f2b_watcher import f2b_watcher
        self._f2b_task = asyncio.create_task(self._f2b_loop(f2b_watcher))
        logger.info("[NEXUS:SECURITY] Fail2Ban Watchdog Initialized.")
        
        # 5. OS & SSL Audits [Task 2.5 & 2.7]
        from .os_checker import os_checker
        from .ssl_checker import ssl_checker
        os_report = await os_checker.check_patches()
        ssl_report = await ssl_checker.check_expiry()
        
        logger.info(f"[NEXUS:SECURITY] OS Status: {os_report['status']}, SSL Status: {ssl_report['status']}")

        # 6. Fingerprint Isolation [Task 2.4]
        from .fingerprint import nexus_fp
        logger.info(f"[NEXUS:SECURITY] Fingerprint Store Ready: {nexus_fp.storage_dir}")

    async def _f2b_loop(self, watcher):
        """Infinite loop to scan auth.log for suspicious footprints."""
        while True:
            # [Task 21] Signal Health to Sentinel
            from core.nexus.bootstrapper import nexus_boot
            nexus_boot.recovery.record_heartbeat(self.name)
            
            await watcher.scan_logs()
            await asyncio.sleep(300) # Every 5 minutes

    async def on_stop(self):
        """Cleanup Security context."""
        if hasattr(self, "_f2b_task"):
            self._f2b_task.cancel()
        logger.info("[NEXUS:SECURITY] Persistence Handover to OS complete.")
        pass

security_node = NexusSecurityNode()

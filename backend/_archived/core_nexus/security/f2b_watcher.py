import logging
import os
import re
from typing import Set

logger = logging.getLogger("nexus.security.f2b")

class Fail2BanWatcher:
    """[Task 2.3] Log-based Brute Force Protection (Nexus-F2B)."""
    
    def __init__(self, log_path: str = "/var/log/auth.log"):
        self.log_path = log_path
        self.blacklist: Set[str] = set()
        
    async def scan_logs(self):
        """Analyze auth.log for suspicious IP footprints and trigger firewall blocks."""
        if not os.path.exists(self.log_path):
             return self.blacklist

        from .firewall import nexus_firewall
        new_bans = 0
        try:
            with open(self.log_path, 'r') as f:
                lines = f.readlines()[-200:]
                
                for line in lines:
                    match = re.search(r"(?:Failed password|Invalid user) .* from (\d+\.\d+\.\d+\.\d+)", line)
                    if match:
                        ip = match.group(1)
                        if ip not in self.blacklist:
                            self.blacklist.add(ip)
                            new_bans += 1
                            # ACTIVE DEFENSE: Trigger instant block
                            logger.warning(f"🛡️ [NEXUS:F2B] Detected Attacker {ip}. Prompting Firewall Block.")
                            await nexus_firewall.block_port(0, protocol=f"from {ip}") # Block all from IP

            if new_bans > 0:
                logger.warning(f"🚨 [NEXUS:F2B] Synchronized {new_bans} New Bans to Firewall.")
                
        except Exception as e:
            logger.error(f"🚨 F2B Watcher failed: {e}")
            
        return self.blacklist

f2b_watcher = Fail2BanWatcher()

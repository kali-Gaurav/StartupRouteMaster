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
        
    def scan_logs(self):
        """Analyze auth.log for suspicious IP footprints."""
        if not os.path.exists(self.log_path):
             return self.blacklist

        new_bans = 0
        try:
            with open(self.log_path, 'r') as f:
                # We read only the last N lines for performance
                lines = f.readlines()[-200:]
                
                for line in lines:
                    # Pattern 1: Failed password
                    match = re.search(r"Failed password for .* from (\d+\.\d+\.\d+\.\d+)", line)
                    if match:
                        ip = match.group(1)
                        if ip not in self.blacklist:
                            self.blacklist.add(ip)
                            new_bans += 1
                            
                    # Pattern 2: Invalid user
                    match = re.search(r"Invalid user .* from (\d+\.\d+\.\d+\.\d+)", line)
                    if match:
                        ip = match.group(1)
                        if ip not in self.blacklist:
                            self.blacklist.add(ip)
                            new_bans += 1

            if new_bans > 0:
                logger.warning(f"🚨 [NEXUS:F2B] Detected {new_bans} New Malicious IPs. Blacklist Synchronized.")
                
        except Exception as e:
            logger.error(f"🚨 F2B Watcher failed: {e}")
            
        return self.blacklist

f2b_watcher = Fail2BanWatcher()

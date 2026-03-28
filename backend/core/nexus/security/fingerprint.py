import logging
import os
import stat
import platform
from typing import Optional, Dict

logger = logging.getLogger("nexus.security.fingerprint")

class NexusFingerprint:
    """[Task 2.4] Fingerprint Isolation. Protected storage for sensitive V3 keys."""
    
    def __init__(self, storage_dir: str = ".nexus/etc/keys/"):
        self.storage_dir = storage_dir
        self.is_linux = platform.system() == "Linux"
        self._ensure_dir()
        
    def _ensure_dir(self):
        """Create and harden the sensitive directory."""
        if not os.path.exists(self.storage_dir):
             os.makedirs(self.storage_dir, exist_ok=True)
             
        if self.is_linux:
             try:
                 # chmod 700: Owner only (rwx)
                 os.chmod(self.storage_dir, stat.S_IRWXU)
                 logger.info(f"🛡️ [NEXUS:FP] Directory Hardened (chmod 700): {self.storage_dir}")
             except: pass

    async def store_key(self, name: str, value: str):
        """Securely store a key."""
        path = os.path.join(self.storage_dir, f"{name}.nexus")
        with open(path, "w") as f:
            f.write(value)
            
        if self.is_linux:
             # chmod 600: Owner only (rw)
             os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
             
        logger.info(f"🔑 [NEXUS:FP] Sensitive Key {name} Isolated successfully.")

    async def get_key(self, name: str) -> Optional[str]:
        """Retrieve a key if it exists."""
        path = os.path.join(self.storage_dir, f"{name}.nexus")
        if os.path.exists(path):
             with open(path, "r") as f:
                 return f.read()
        return None

nexus_fp = NexusFingerprint()

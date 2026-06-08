import subprocess
import logging
import platform

logger = logging.getLogger("nexus.security.firewall")

class NexusFirewall:
    """[Task 2.1] Linux UFW Controller (DevOps-as-Code)."""
    
    def __init__(self, ssh_port: int = 22):
        self.ssh_port = ssh_port
        self.is_linux = platform.system() == "Linux"
        
    def _run_cmd(self, cmd: list) -> str:
        if not self.is_linux:
             logger.debug(f"[FIREWALL:DRY_RUN] Command: {' '.join(cmd)}")
             return "dry_run_authorized"
             
        try:
            result = subprocess.run(["sudo"] + cmd, capture_output=True, text=True, timeout=5)
            if result.returncode != 0:
                logger.error(f"Firewall CMD Error: {result.stderr}")
            return result.stdout
        except Exception as e:
            logger.error(f"Firewall Subprocess Failed: {e}")
            return str(e)

    async def allow_port(self, port: int, protocol: str = "tcp"):
        """Permit traffic to a specific port."""
        logger.info(f"[FIREWALL] Allowing {protocol}/{port}...")
        return self._run_cmd(["ufw", "allow", f"{port}/{protocol}"])

    async def block_port(self, port: int, protocol: str = "tcp"):
        """Block traffic to a specific port (Safety locked for SSH)."""
        if port == self.ssh_port:
             logger.warning(f"[FIREWALL] BLOCK REJECTED: Refusing to lock out SSH port {port}!")
             return False
             
        logger.info(f"[FIREWALL] Blocking {protocol}/{port}...")
        return self._run_cmd(["ufw", "deny", f"{port}/{protocol}"])

    async def get_status(self):
        """Query UFW active rules."""
        return self._run_cmd(["ufw", "status", "numbered"])

nexus_firewall = NexusFirewall()

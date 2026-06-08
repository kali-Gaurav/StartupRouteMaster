import logging
import os
import re

logger = logging.getLogger("nexus.security.ssh")

class SSHHardener:
    """[Task 2.2] SSH-as-Code. Audits and enforces sshd_config hardening."""
    
    def __init__(self, config_path: str = "/etc/ssh/sshd_config"):
        self.config_path = config_path
        
    def audit_config(self) -> dict:
        """Read sshd_config and verify security parameters."""
        logger.info(f"[NEXUS:SSH] Auditing security configuration at {self.config_path}...")
        
        report = {
            "root_login_disabled": False,
            "password_auth_disabled": False,
            "custom_port_active": False,
            "status": "VULNERABLE"
        }
        
        if not os.path.exists(self.config_path):
             logger.warning("[NEXUS:SSH] Config not found (NON-LINUX/DEV). Using safe defaults.")
             return report

        try:
            with open(self.config_path, 'r') as f:
                content = f.read()
                
            # 1. PermitRootLogin no
            if re.search(r"^PermitRootLogin\s+no", content, re.MULTILINE):
                report["root_login_disabled"] = True

            # 2. PasswordAuthentication no
            if re.search(r"^PasswordAuthentication\s+no", content, re.MULTILINE):
                report["password_auth_disabled"] = True

            # 3. Custom Port (e.g., not 22)
            port_match = re.search(r"^Port\s+(\d+)", content, re.MULTILINE)
            if port_match and port_match.group(1) != "22":
                report["custom_port_active"] = True
                
            if all([report["root_login_disabled"], report["password_auth_disabled"]]):
                report["status"] = "HARDENED"
                
        except Exception as e:
            logger.error(f"Failed to audit SSH config: {e}")
            
        return report

ssh_hardener = SSHHardener()

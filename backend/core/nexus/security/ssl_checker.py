import logging
import socket
import ssl
from datetime import datetime
from typing import Optional

logger = logging.getLogger("nexus.security.ssl")

class SSLIntegrityChecker:
    """[Task 2.5] Certbot/SSL Expiration Monitor."""
    
    def __init__(self, hostname: str = "localhost"):
        self.hostname = hostname
        
    async def check_expiry(self, domain: Optional[str] = None) -> dict:
        """Query certificate expiration via raw SSL socket."""
        target = domain or self.hostname
        logger.info(f"🛡️ [NEXUS:SSL] Auditing Certificate Integrity for {target}...")
        
        report = {"status": "UNKNOWN", "days_remaining": 0}
        
        try:
            context = ssl.create_default_context()
            with socket.create_connection((target, 443), timeout=5) as sock:
                with context.wrap_socket(sock, server_hostname=target) as ssock:
                    cert = ssock.getpeercert()
                    
            expiry_str = cert['notAfter']
            expiry_dt = datetime.strptime(expiry_str, '%b %d %H:%M:%S %Y %Z')
            remaining = (expiry_dt - datetime.utcnow()).days
            
            report["days_remaining"] = remaining
            if remaining < 7:
                 report["status"] = "EXPIRED" if remaining <= 0 else "CRITICAL"
            elif remaining < 30:
                 report["status"] = "RENEW_READY"
            else:
                 report["status"] = "HEALTHY"
                 
            logger.info(f"✅ [NEXUS:SSL] Certificate Health: {report['status']} ({remaining} days left).")
            
        except Exception as e:
            logger.warning(f"🔕 [NEXUS:SSL] Unable to audit remote SSL: {e}. Skipping in Local/Dev.")
            
        return report

ssl_checker = SSLIntegrityChecker()

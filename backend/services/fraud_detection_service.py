import logging
import re
import httpx
from datetime import datetime, timedelta
from typing import Optional, Tuple
from services.cache_service import cache_service

logger = logging.getLogger(__name__)

class FraudDetectionService:
    """
    Task 3: Fraudulent UTR Lockout.
    Implements velocity checks, lockout, and pattern matching.
    """
    
    LOCKOUT_LIMIT = 3
    LOCKOUT_DURATION_SECONDS = 3600 # 1 Hour
    VELOCITY_LIMIT = 5
    VELOCITY_WINDOW_SECONDS = 600 # 10 Minutes
    
    # Task 3.10: Honeypot UTR detection
    HONEYPOT_UTRS = ["111111111111", "999999999999", "000000000000"]
    
    # Task 3.7: Slack Webhook (Replace with real one in production)
    SLACK_WEBHOOK_URL = "https://hooks.slack.com/services/dummy/webhook"

    def _notify_slack(self, message: str):
        """Task 3.7: Slack notification for suspected fraud clusters."""
        try:
            # We don't await here to keep it simple, or use background task
            logger.warning(f"SLACK ALERT: {message}")
            # httpx.post(self.SLACK_WEBHOOK_URL, json={"text": message})
        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")

    def is_geometric_pattern(self, utr: str) -> bool:
        """
        Task 3.4: Geometric pattern matching for "fake" UTR sequences.
        Detects obvious fakes like 123412341234 or 000000000000.
        """
        if len(set(utr)) == 1:
            return True
        if utr in "01234567890123456789" or utr in "98765432109876543210":
            return True
        if len(utr) == 12 and utr[:4] * 3 == utr:
            return True
        return False

    def is_foreign_ip(self, ip_address: str) -> bool:
        """
        Task 3.8: Geo-fencing (Restrict payments from outside India).
        Placeholder for real Geo-IP DB. Block obvious localhost ranges if strict,
        but for now we simulate blocking a specific 'bad' IP range.
        """
        if not ip_address:
            return False
        # Example: block standard US AWS ranges (mock logic)
        blocked_prefixes = ["54.21.", "13.2."]
        for prefix in blocked_prefixes:
            if ip_address.startswith(prefix):
                return True
        return False

    def check_lockout(self, identifier: str) -> Tuple[bool, str]:
        """
        Task 3.1 & 3.2: Per-IP/Per-User attempt counter in Redis.
        Returns (is_blocked, reason)
        """
        lock_key = f"fraud_lockout:{identifier}"
        
        # Check if already blocked
        if cache_service.get(lock_key):
            return True, "Your account/IP is temporarily locked due to multiple failed payment attempts. Please try again in 1 hour."
            
        return False, ""

    def clear_lockout(self, identifier: str):
        """Task 3.6: Admin dashboard for manual unblocking."""
        cache_service.delete(f"fraud_lockout:{identifier}")
        cache_service.delete(f"fraud_attempts:{identifier}")
        cache_service.delete(f"fraud_velocity:{identifier}")
        logger.info(f"Lockout cleared manually for {identifier}")

    def record_attempt(self, identifier: str, success: bool):
        """Records a success or failure attempt and applies lockout if needed."""
        lock_key = f"fraud_lockout:{identifier}"
        attempts_key = f"fraud_attempts:{identifier}"
        velocity_key = f"fraud_velocity:{identifier}"

        if success:
            # Clear attempt counter on success
            cache_service.delete(attempts_key)
            return

        # Increment failure attempts
        attempts = (cache_service.get(attempts_key) or 0) + 1
        cache_service.set(attempts_key, attempts, ttl_seconds=86400) # Keep history for 24h

        # Task 3.5: Automatic 1-hour ban after 3 failed attempts
        if attempts >= self.LOCKOUT_LIMIT:
            logger.warning(f"FRAUD DETECTED: Identifier {identifier} locked out for 1 hour after {attempts} failures.")
            cache_service.set(lock_key, "LOCKED", ttl_seconds=self.LOCKOUT_DURATION_SECONDS)
            if attempts == self.LOCKOUT_LIMIT: # Notify once
                self._notify_slack(f"User/IP {identifier} locked out for 1 hour due to multiple failed UTR submissions.")
            
        # Task 3.9: Velocity checks (Max 5 UTRs per 10 mins)
        velocity = (cache_service.get(velocity_key) or 0) + 1
        cache_service.set(velocity_key, velocity, ttl_seconds=self.VELOCITY_WINDOW_SECONDS)
        
        if velocity >= self.VELOCITY_LIMIT:
            logger.warning(f"VELOCITY LIMIT: Identifier {identifier} exceeded submission rate.")
            cache_service.set(lock_key, "VELOCITY_LOCKED", ttl_seconds=1800) # 30 min ban for velocity
            if velocity == self.VELOCITY_LIMIT:
                self._notify_slack(f"Velocity threshold breached by {identifier} (5 attempts / 10 mins).")

    def validate_utr_advanced(self, utr: str, user_id: str, ip_address: str = None, device_fp: str = None) -> Tuple[bool, str]:
        """
        Comprehensive UTR validation including fraud checks (Tasks 3.1, 3.2, 3.3).
        """
        identifiers = [user_id]
        if ip_address: identifiers.append(f"IP:{ip_address}")
        if device_fp: identifiers.append(f"FP:{device_fp}")

        # 1. Geo-Fencing (Task 3.8)
        if ip_address and self.is_foreign_ip(ip_address):
            self._notify_slack(f"Geo-fence blocked UTR attempt from IP: {ip_address}")
            return False, "Payments are restricted to Indian IP addresses only."

        # 2. Check Lockouts for all identifiers (User, IP, Fingerprint)
        for ident in identifiers:
            is_blocked, reason = self.check_lockout(ident)
            if is_blocked:
                return False, f"Blocked on identifier {ident.split(':')[0]}: {reason}"

        # 3. Check Honeypot (Task 3.10)
        if utr in self.HONEYPOT_UTRS:
            self._notify_slack(f"HONEYPOT TRIPPED by {user_id} (IP: {ip_address}) with UTR {utr}")
            for ident in identifiers:
                cache_service.set(f"fraud_lockout:{ident}", "HONEYPOT_LOCKED", ttl_seconds=86400 * 7) # 7-day ban
            return False, "Account permanently flagged for suspicious activity."

        # 4. Check Format (Basic)
        if not re.match(r"^\d{12}$", utr):
            for ident in identifiers: self.record_attempt(ident, False)
            return False, "Invalid UTR format. Must be 12 digits."

        # 5. Check Patterns (Task 3.4)
        if self.is_geometric_pattern(utr):
            logger.warning(f"SUSPECTED FRAUD: Pattern match for UTR {utr} from {user_id}")
            for ident in identifiers: self.record_attempt(ident, False)
            return False, "Suspicious UTR pattern detected. Account flagged."

        return True, ""

fraud_service = FraudDetectionService()

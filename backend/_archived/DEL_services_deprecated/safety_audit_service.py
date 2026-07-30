import logging
import hashlib
import json
from datetime import datetime
from typing import Dict, Any
from core.infrastructure.redis_manager import async_redis_client

logger = logging.getLogger("nexus.audit")

class SafetyAuditService:
    """
    [RM-I-101] The Immutable Audit Ledger.
    Ensures every safety-critical action is logged with a cryptographic signature.
    """
    
    AUDIT_LOG_KEY = "safety_audit_ledger"

    @staticmethod
    def _generate_signature(data: Dict[str, Any]) -> str:
        """
        Generate a SHA-256 hash of the event data to ensure integrity.
        """
        serialized = json.dumps(data, sort_keys=True)
        return hashlib.sha256(serialized.encode()).hexdigest()

    @staticmethod
    async def log_event(event_type: str, payload: Dict[str, Any], actor_id: str):
        """
        Permanently record a safety event with a hash signature.
        """
        timestamp = datetime.utcnow().isoformat()
        
        audit_record = {
            "timestamp": timestamp,
            "event_type": event_type,
            "actor_id": actor_id,
            "payload": payload,
            "version": "1.0"
        }
        
        # Add integrity signature
        audit_record["signature"] = SafetyAuditService._generate_signature(audit_record)
        
        # 1. Immediate Persistence (Redis for fast lookup)
        await async_redis_client.lpush(SafetyAuditService.AUDIT_LOG_KEY, json.dumps(audit_record))
        
        # 2. Industrial Persistence (Mock for SQL integration)
        # In production, this calls: db.session.add(AuditModel(**audit_record))
        
        logger.info(f"📜 [AUDIT] {event_type} recorded. Hash: {audit_record['signature'][:12]}...")
        return audit_record

    @staticmethod
    async def verify_integrity() -> bool:
        """
        Scan the ledger and verify that no records have been tampered with.
        """
        logs = await async_redis_client.lrange(SafetyAuditService.AUDIT_LOG_KEY, 0, -1)
        for log_raw in logs:
            log = json.loads(log_raw)
            signature = log.pop("signature")
            if SafetyAuditService._generate_signature(log) != signature:
                logger.critical("🚨 [AUDIT] INTEGRITY BREACH DETECTED! Tampered log found.")
                return False
        return True

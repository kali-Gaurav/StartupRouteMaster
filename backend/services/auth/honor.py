import logging
import json
import hashlib
from datetime import datetime
from typing import Dict, Any, List
from core.infrastructure.redis_manager import async_redis_client

logger = logging.getLogger("nexus.honor")

class HonorLedgerService:
    """
    [RM-F-904] Sathi Honor & Rewards Ledger.
    Incentivizes safety assistance through verifiable credit rewards.
    """
    
    LEDGER_STREAM = "honor:ledger"
    BALANCE_PREFIX = "honor:balance:"

    @staticmethod
    async def record_safety_act(sathi_id: str, act_type: str, evidence_id: str, credit_val: int = 100):
        """
        [Council Feature] Record a verified act of safety and reward credits.
        """
        # 1. Create a signed entry for the ledger
        timestamp = datetime.utcnow().isoformat()
        signature = hashlib.sha256(f"{sathi_id}{act_type}{timestamp}".encode()).hexdigest()
        
        entry = {
            "sathi_id": sathi_id,
            "act_type": act_type,
            "evidence_id": evidence_id,
            "credits": credit_val,
            "timestamp": timestamp,
            "signature": signature
        }
        
        # 2. Add to Immutable Redis Stream
        await async_redis_client.xadd(HonorLedgerService.LEDGER_STREAM, entry)
        
        # 3. Increment Sathi Balance
        await async_redis_client.incr(f"{HonorLedgerService.BALANCE_PREFIX}{sathi_id}", credit_val)
        
        logger.info(f"🏆 [HONOR] Sathi {sathi_id} rewarded {credit_val} credits for {act_type}.")
        return entry

    @staticmethod
    async def get_sathi_balance(sathi_id: str) -> int:
        """
        Retrieve total Honor Credits for a Sathi.
        """
        val = await async_redis_client.get(f"{HonorLedgerService.BALANCE_PREFIX}{sathi_id}")
        return int(val) if val else 0

if __name__ == "__main__":
    import asyncio
    async def test():
        await HonorLedgerService.record_safety_act("SATHI_007", "SENIOR_ASSISTANCE", "INCIDENT_99")
    asyncio.run(test())

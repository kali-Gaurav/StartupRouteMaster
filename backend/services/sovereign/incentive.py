"""
Sovereign Incentive Fulfillment Service
========================================
Patent Innovation #6: Trustless incentive fulfillment for demand redistribution.

This service manages the lifecycle of incentives issued by the EDR algorithm:
1. ISSUE: Recorded during search.
2. SELECT: User chooses the nudged route.
3. VERIFY: User actually completes the booking.
4. FULFILL: Loyalty points or cashback credited to user account.
"""

import logging
import uuid
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from decimal import Decimal

from core.sovereign.edr_algorithm import IncentiveCategory

logger = logging.getLogger("sovereign.incentives")

class IncentiveService:
    """
    Handles the financial and loyalty state of Sovereign incentives.
    """

    def __init__(self, db_session=None):
        self.db = db_session

    async def record_issued_incentive(
        self,
        user_id: str,
        nudge_id: str,
        amount: float,
        category: IncentiveCategory,
        route_id: str,
        expires_in_hours: int = 2
    ) -> str:
        """
        Records an incentive as 'Issued' in the cache/DB.
        """
        try:
            from services.multi_layer_cache import multi_layer_cache
            if multi_layer_cache.redis:
                claim_token = str(uuid.uuid4())[:8]
                payload = {
                    "user_id": user_id,
                    "nudge_id": nudge_id,
                    "amount": amount,
                    "category": category.value,
                    "route_id": route_id,
                    "status": "ISSUED",
                    "issued_at": datetime.utcnow().isoformat(),
                    "expires_at": (datetime.utcnow() + timedelta(hours=expires_in_hours)).isoformat()
                }
                
                # Store in Redis for fast lookup during booking
                key = f"incentive:token:{claim_token}"
                await multi_layer_cache.redis.set(key, str(payload), ex=expires_in_hours * 3600)
                
                logger.info(f"💰 [INCENTIVE] Issued Rs {amount} to {user_id} via {nudge_id}. Token: {claim_token}")
                return claim_token
        except Exception as e:
            logger.error(f"Failed to record issued incentive: {e}")
        return ""

    async def claim_incentive(self, claim_token: str, booking_id: str) -> bool:
        """
        Called when a user completes a booking for a nudged route.
        Transitions the incentive from ISSUED to CLAIMED.
        """
        try:
            from services.multi_layer_cache import multi_layer_cache
            if not multi_layer_cache.redis:
                return False

            key = f"incentive:token:{claim_token}"
            data_raw = await multi_layer_cache.redis.get(key)
            if not data_raw:
                logger.warning(f"Invalid or expired claim token: {claim_token}")
                return False

            # In production, we'd parse this properly
            # data = eval(data_raw) 
            
            # Update state to CLAIMED
            # In a real DB, we would add the booking_id to the record
            await multi_layer_cache.redis.delete(key)
            
            # Record conversion for A/B testing
            from core.sovereign.ab_engine import ab_engine
            # await ab_engine.record_conversion(...) 
            
            logger.info(f"✅ [INCENTIVE] Incentive {claim_token} CLAIMED for booking {booking_id}")
            return True
        except Exception as e:
            logger.error(f"Incentive claim failed: {e}")
            return False

# Global Instance
incentive_service = IncentiveService()

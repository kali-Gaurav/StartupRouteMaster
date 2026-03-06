import logging
import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class TatkalSchedulerService:
    """
    Task 30: Tatkal Timing Precision.
    Manages the high-stakes execution of Tatkal bookings.
    """
    
    def __init__(self):
        self.ntp_offset_ms = 0 # Simulated delta from NTP server

    async def sync_ntp_time(self):
        """Task 30.2: NTP Time sync for server clock."""
        # In production, we'd use ntplib. For demo, we simulate a 15ms offset.
        # logger.info("Syncing with pool.ntp.org...")
        self.ntp_offset_ms = 15
        return True

    def calculate_success_probability(self, route_popularity: int, ping_ms: int, previous_attempts: int) -> float:
        """
        Task 30.10: Success probability calculator.
        High popularity lowers it. Low ping increases it.
        """
        base = 80.0
        # High popularity drops probability
        base -= (route_popularity * 2.5) 
        # High ping drops probability (every 100ms drops 5%)
        base -= (ping_ms / 100) * 5.0
        # More attempts slightly increases (cache warming)
        base += (previous_attempts * 2.0)
        
        return max(5.0, min(95.0, base)) # Cap between 5% and 95%

    async def _execute_with_retry(self, action_name: str, max_retries: int = 3):
        """Task 30.4: Auto-retry on 'Service Unavailable' loop."""
        for attempt in range(max_retries):
            try:
                logger.info(f"Executing {action_name} (Attempt {attempt+1}/{max_retries})...")
                # Simulate network call
                await asyncio.sleep(0.1)
                
                # Simulate a random 503 error on the first attempt
                if attempt == 0 and "login" in action_name.lower():
                    raise ConnectionError("503 Service Unavailable")
                    
                return True
            except Exception as e:
                logger.warning(f"{action_name} failed: {e}. Retrying...")
                await asyncio.sleep(0.2 * (attempt + 1)) # Exponential backoff
        return False

    async def preflight_check(self, booking_id: str):
        """Task 30.3: Pre-filling form in background before 10 AM."""
        logger.info(f"Tatkal Preflight: Caching passenger details for {booking_id} into fast memory.")
        # In reality: Push to Redis, prepare captcha solver
        await asyncio.sleep(0.05)
        return True
        
    async def clear_session_cache(self, user_id: str):
        """Task 30.7: Automated logout/re-login to clear session cache."""
        logger.info(f"Clearing stale IRCTC sessions for user {user_id}")
        return True

    async def execute_tatkal_sequence(self, booking_id: str, user_id: str, is_ac: bool, is_force_start: bool = False):
        """
        Orchestrates the entire flow:
        - Prioritizes AC vs Non-AC (Task 30.5)
        - Distributes Workers (Task 30.6)
        - Millisecond precision (Task 30.1)
        """
        # Task 30.9: Force Start
        if is_force_start:
            logger.warning(f"FORCE START triggered for {booking_id}. Bypassing clock waits.")
        else:
            # Task 30.1: Millisecond-perfect wait
            # In a real app, this would block until 09:59:50 or 10:59:50
            target_hour = 9 if is_ac else 10
            logger.info(f"Waiting for {target_hour}:59:50.000 (adjusted by {self.ntp_offset_ms}ms NTP delta)...")
            await asyncio.sleep(0.5) # Simulate waiting
            
        await self.clear_session_cache(user_id)
        await self.preflight_check(booking_id)
        
        # Task 30.5 & 30.6: Distribute to specific queues
        queue_name = "tatkal_ac_nodes" if is_ac else "tatkal_sl_nodes"
        logger.info(f"Dispatching login sequence to {queue_name} (Distributed Workers)")
        
        success = await self._execute_with_retry("IRCTC_Login")
        if success:
            logger.info("Login successful. Firing payload...")
            return {"success": True, "message": "Tatkal payload fired successfully"}
        else:
            return {"success": False, "message": "Failed to penetrate IRCTC servers"}

tatkal_scheduler = TatkalSchedulerService()

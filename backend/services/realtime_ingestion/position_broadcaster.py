"""
Background Broadcaster for live train positions.
Bridges the PositionEstimator and WebSocketManager.
"""

import asyncio
import logging
import json
import time
from datetime import datetime
from typing import Dict, Any

from backend.database import SessionLocal
from .position_estimator import TrainPositionEstimator
from backend.core.monitoring import BROADCASTER_TICK_DURATION

logger = logging.getLogger(__name__)

class PositionBroadcaster:
    """
    Background loop that computes and broadcasts train positions 
    for all active WebSocket subscriptions.
    """
    def __init__(self, interval_seconds: int = 5):
        self.interval = interval_seconds
        self.is_running = False

    async def start(self):
        # Lazy import for manager to avoid circular deps
        from backend.api.websockets import manager
        
        if self.is_running:
            return
        self.is_running = True
        logger.info(f"PositionBroadcaster started with {self.interval}s interval")
        
        while self.is_running:
            tick_start = time.perf_counter()
            try:
                # 1. Get active subscriptions
                active_trains = list(manager.train_subscriptions.keys())
                
                if active_trains:
                    db = SessionLocal()
                    estimator = TrainPositionEstimator(db)
                    
                    for train_no in active_trains:
                        # 2. Compute position
                        # This uses our Phase 11 Interpolation logic
                        position = estimator.estimate_position(train_no)
                        
                        if position:
                            # 2.1 Cache last known position in Redis (Distributed State)
                            history_key = f"pos:last:{train_no}"
                            from backend.services.multi_layer_cache import multi_layer_cache
                            await multi_layer_cache.initialize()
                            if multi_layer_cache.redis:
                                await multi_layer_cache.redis.setex(history_key, 60, json.dumps(position))

                            # 3. Broadcast to all clients watching this train (Distributed)
                            await manager.broadcast_to_train(train_no, position)
                    
                    db.close()
                
            except Exception as e:
                logger.error(f"Broadcaster Error: {e}")
            finally:
                BROADCASTER_TICK_DURATION.observe(time.perf_counter() - tick_start)
                # Sleep until next pulse
                await asyncio.sleep(self.interval)

    def stop(self):
        self.is_running = False
        logger.info("PositionBroadcaster stopped")

# Global singleton for the broadcaster
broadcaster = PositionBroadcaster(interval_seconds=3) # High frequency for SOS smoothness

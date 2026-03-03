"""
[Metrics] monitor_engine_health.py (TODO #49)

Checks Redis for engine usage counters and alerts if there's a sudden drop.
"""

import asyncio
import logging
import sys
import os
from datetime import datetime, timedelta

# Ensure backend package is importable
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from services.multi_layer_cache import multi_layer_cache

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("health-monitor")

async def monitor_usage():
    await multi_layer_cache.initialize()
    if not multi_layer_cache.redis:
        logger.error("Redis not connected. Cannot monitor usage.")
        return

    today = datetime.utcnow().date().isoformat()
    yesterday = (datetime.utcnow().date() - timedelta(days=1)).isoformat()
    
    key_today = f"metrics:engine_usage:{today}"
    key_yesterday = f"metrics:engine_usage:{yesterday}"
    
    usage_today = await multi_layer_cache.redis.hgetall(key_today)
    usage_yesterday = await multi_layer_cache.redis.hgetall(key_yesterday)
    
    logger.info(f"Engine Usage Today: {usage_today}")
    logger.info(f"Engine Usage Yesterday: {usage_yesterday}")
    
    # Simple alert logic
    if usage_yesterday and not usage_today:
        logger.critical("ALERT: No engine usage recorded today! Check system status.")
    
    for engine, count_y in usage_yesterday.items():
        count_t = int(usage_today.get(engine, 0))
        count_y = int(count_y)
        
        # If today's usage is < 20% of yesterday (and it's not early morning)
        if count_y > 10 and count_t < (count_y * 0.2) and datetime.utcnow().hour > 6:
            logger.critical(f"ALERT: Significant drop in usage for {engine.decode()}! {count_y} -> {count_t}")

if __name__ == "__main__":
    asyncio.run(monitor_usage())

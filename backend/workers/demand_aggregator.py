import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import Dict
from database.redis_client import redis_client
from database.models import Payment as PaymentModel

logger = logging.getLogger("routemaster.demand_aggregator")

class DemandAggregator:
    """
    Consumes search telemetry and generates a 'Demand Heatmap'.
    This heatmap is used by the Routing Engine to adjust route priority.
    """
    def __init__(self):
        self.stream_key = "search_telemetry"
        self.group_name = "demand_aggregator_group"
        self.consumer_name = "aggregator_1"
        self.decay_script = """
            local current = tonumber(redis.call('HGET', KEYS[1], ARGV[1]) or 0)
            local new = (current * 0.95) + 1
            redis.call('HSET', KEYS[1], ARGV[1], new)
            return new
        """

    async def start(self):
        logger.info("Demand Aggregator started...")
        try:
            await redis_client.xgroup_create(self.stream_key, self.group_name, id='0', mkstream=True)
        except Exception:
            pass 

        while True:
            try:
                messages = await redis_client.xreadgroup(
                    self.group_name, 
                    self.consumer_name, 
                    {self.stream_key: ">"}, 
                    count=10, 
                    block=5000
                )
                
                for stream, msgs in messages:
                    for msg_id, data in msgs:
                        decoded_data = {k.decode(): v.decode() for k, v in data.items()}
                        await self.process_event(decoded_data)
                        await redis_client.xack(self.stream_key, self.group_name, msg_id)
            
            except Exception as e:
                logger.error(f"Demand Aggregator Error: {e}")
                await asyncio.sleep(5)

    async def process_event(self, event: Dict[str, str]):
        """Aggregates event into the Demand Heatmap using atomic decay."""
        origin = event.get("origin")
        dest = event.get("destination")
        if not origin or not dest:
            return

        hour = datetime.utcnow().strftime("%H")
        key = f"demand:{origin}:{dest}:{hour}"
        
        # Execute Lua script for atomic decay
        await redis_client.eval(self.decay_script, 1, "global_demand_heatmap", key)
        
        logger.debug(f"Decayed & Recorded demand for {key}")

aggregator = DemandAggregator()

if __name__ == "__main__":
    asyncio.run(aggregator.start())

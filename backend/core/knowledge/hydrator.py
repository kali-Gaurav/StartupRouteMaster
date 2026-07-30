"""
🧠 KNOWLEDGE GRAPH HYDRATOR — Real-time Delay & Inefficiency Sync
Fetches live transit data to update the Travel Knowledge Graph with dynamic insights.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any

from core.knowledge.travel_graph import knowledge_graph, KnowledgeNode
from services.rapidapi_provider import rapidapi_provider

logger = logging.getLogger(__name__)

class KnowledgeHydrator:
    """
    Background service that hydrates the Travel Knowledge Graph with real-time data.
    Focuses on 'Trunk Routes' and 'Major Hubs'.
    """

    def __init__(self, interval_seconds: int = 300):
        self.interval_seconds = interval_seconds
        self.is_running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        if self.is_running:
            return
        self.is_running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("🚀 Knowledge Hydrator started.")

    async def stop(self):
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("🛑 Knowledge Hydrator stopped.")

    async def _run_loop(self):
        while self.is_running:
            try:
                await self.hydrate_all()
            except Exception as e:
                logger.error(f"❌ Error during hydration cycle: {e}")
            
            await asyncio.sleep(self.interval_seconds)

    async def hydrate_all(self):
        """Main hydration logic."""
        logger.info("🔄 Starting Knowledge Graph hydration cycle...")
        
        # 1. Hydrate Station Delays
        await self._hydrate_station_delays(["NDLS", "HWH", "CNB", "PNBE", "MGS"])
        
        # 2. Hydrate Train Delays (Top Tier)
        await self._hydrate_train_delays(["12301", "12302", "12304", "12312", "12274"])
        
        logger.info("✅ Hydration cycle complete.")

    async def _hydrate_station_delays(self, stations: List[str]):
        """Fetches live station data to identify platform bottlenecks."""
        for code in stations:
            try:
                live_data = await rapidapi_provider.get_live_station(code, hours=2)
                if live_data and hasattr(live_data, 'data'):
                    # Analyze delays to identify 'Congested' status
                    trains = live_data.data
                    avg_delay = sum(t.get('delay', 0) for t in trains) / len(trains) if trains else 0
                    
                    node = knowledge_graph.get_node(code)
                    if node:
                        node.attributes['avg_station_delay'] = avg_delay
                        if avg_delay > 30:
                            node.tags.add("CONGESTED_HUB")
                            if "High average delays detected (>30m)" not in node.inefficiencies:
                                node.inefficiencies.append("High average delays detected (>30m)")
                        else:
                            node.tags.discard("CONGESTED_HUB")
            except Exception as e:
                logger.error(f"Failed to hydrate station {code}: {e}")

    async def _hydrate_train_delays(self, train_numbers: List[str]):
        """Fetches live train status to identify corridor inefficiencies."""
        for num in train_numbers:
            try:
                status = await rapidapi_provider.get_live_train_status(num)
                if status and hasattr(status, 'data'):
                    delay = status.data.get('delay', 0)
                    current_station = status.data.get('current_station_name', 'Unknown')
                    
                    node = knowledge_graph.get_node(num)
                    if not node:
                        node = KnowledgeNode(id=num, type="TRAIN")
                        knowledge_graph.add_node(node)
                    
                    node.attributes['current_delay'] = delay
                    node.attributes['current_position'] = current_station
                    node.attributes['last_updated'] = datetime.now().isoformat()
                    
                    if delay > 60:
                        msg = f"Running {delay}m late at {current_station}"
                        if msg not in node.inefficiencies:
                            # Clear old dynamic delay messages
                            node.inefficiencies = [i for i in node.inefficiencies if "Running" not in i]
                            node.inefficiencies.append(msg)
            except Exception as e:
                logger.error(f"Failed to hydrate train {num}: {e}")

# Singleton
knowledge_hydrator = KnowledgeHydrator()

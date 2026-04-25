"""
LiveHydrationAgent - Phase 7: Real-time Telemetry Ingestion
===========================================================
This agent proactively fetches live train status data and hydrates the
TravelKnowledgeGraph and database with real-time metrics.
"""

import logging
import asyncio
import time
from datetime import datetime, timedelta, date
from typing import Dict, Any, List, Optional

from services.agents.base_agent import BaseAgent, AgentPriority
from services.live_status_service import LiveStatusService, LiveStatusConfig, LiveStatusProvider
from services.knowledge_graph_service import TravelKnowledgeGraph
from database.session import SessionTransit
from database.models import CancelledTrain, TrainMaster

logger = logging.getLogger("agent.live_hydration")

class LiveHydrationAgent(BaseAgent):
    """
    Agent responsible for keeping the Knowledge Graph 'fresh' with live data.
    Runs periodically to update active train status.
    """
    
    name = "LiveHydrationAgent"
    description = "Ingests real-time train telemetry into the Knowledge Graph"
    category = "intelligence"
    priority = AgentPriority.NORMAL
    icon = "🌊"
    color = "#06B6D4"  # Cyan
    version = "1.0.0"
    
    # Run every 5 minutes by default
    auto_schedule_interval = 300.0
    
    def __init__(self, kg: Optional[TravelKnowledgeGraph] = None):
        super().__init__()
        self.kg = kg
        self._live_service = LiveStatusService(LiveStatusConfig(
            provider=LiveStatusProvider.RAPIDAPI,
            cache_ttl_seconds=120
        ))
        self._active_window_hours = 4  # Monitor trains departing +/- 4 hours
        # [Telemetry Sensitivity] Rate Limiting: 50 requests per minute
        self._tokens = 50
        self._last_refill = time.monotonic()
        self._refill_rate = 50 / 60.0 # tokens per second
        
    async def execute(self, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        1. Identify 'Hot Trains' (currently running or departing soon).
        2. Fetch live status in batches.
        3. Update Knowledge Graph nodes/edges.
        4. Sync cancellation table.
        """
        self._log_event("execute", "info", "Starting live hydration cycle")
        
        # 1. Identify Hot Trains
        hot_trains = await self._get_hot_trains()
        if not hot_trains:
            return {
                "status": "success",
                "summary": "No active trains found in the current window",
                "trains_processed": 0
            }
        
        self._log_event("fetch", "info", f"Found {len(hot_trains)} active trains to hydrate")
        
        # 2. Fetch Live Status with rate limiting
        train_numbers: List[str] = [str(t.train_number) for t in hot_trains]
        
        # Priority sort: Hydrate trains with earlier departures first
        # (Assuming TrainMaster has a departure_time or similar)
        
        statuses = {}
        for chunk in [train_numbers[i:i + 10] for i in range(0, len(train_numbers), 10)]:
            await self._wait_for_token(len(chunk))
            batch_status = await self._live_service.get_live_status_batch(chunk)
            statuses.update(batch_status)
        
        # 3. Process Statuses
        processed_count = 0
        updates = []
        cancellations = 0
        
        for train_num, status in statuses.items():
            if not status:
                continue
                
            # Update Knowledge Graph (if available)
            if self.kg:
                await self._update_kg_metrics(train_num, status)
            
            # Sync Database
            is_cancelled = status.get("is_cancelled", False) or status.get("status") == "CANCELLED"
            if is_cancelled:
                await self._mark_cancelled(train_num)
                cancellations += 1
            
            processed_count += 1
            updates.append({
                "train": train_num,
                "delay": status.get("delay_minutes", 0),
                "cancelled": is_cancelled
            })
            
        summary = f"Hydrated {processed_count} trains. {cancellations} cancellations detected."
        self._log_event("complete", "success", summary, data={"updates": updates})
        
        return {
            "status": "success",
            "summary": summary,
            "trains_processed": processed_count,
            "cancellations": cancellations
        }

    async def _get_hot_trains(self) -> List[TrainMaster]:
        """[Heuristic] Identify trains requiring immediate status hydration."""
        with SessionTransit() as db:
            # Simplified query: Get a sample of trains to hydrate
            # In production, we would filter by schedule/route
            trains = db.query(TrainMaster).limit(50).all()
            return trains

    async def _update_kg_metrics(self, train_num: str, status: Dict[str, Any]):
        """Inject live data into the Knowledge Graph."""
        delay = status.get("delay_minutes", 0)
        
        # In a real KG implementation, we'd update specific edges or nodes
        # For now, we update the pattern storage
        route_key = status.get("route_key") # If provided by status
        if not route_key:
            # Try to derive from status details if source/dest available
            source = status.get("source_station_code")
            dest = status.get("dest_station_code")
            if source and dest:
                route_key = f"{source}->{dest}"
        
        if self.kg is not None and route_key and route_key in self.kg.route_patterns:
            pattern = self.kg.route_patterns[route_key]
            # Smoothly update reliability based on live delay
            # High delay = lower reliability
            live_reliability = max(0.1, 1.0 - (delay / 120.0))
            
            # Weighted average with historical reliability
            historical = pattern.get("success_rate", 0.9)
            new_reliability = (historical * 0.7) + (live_reliability * 0.3)
            
            pattern["success_rate"] = round(new_reliability, 2)
            pattern["last_live_update"] = datetime.utcnow().isoformat()
            pattern["current_delay"] = delay

    async def _mark_cancelled(self, train_num: str):
        """Persist train cancellation to database for downstream filtering."""
        today = date.today()
        with SessionTransit() as db:
            existing = db.query(CancelledTrain).filter(
                CancelledTrain.train_no == train_num,
                CancelledTrain.travel_date == today
            ).first()
            
            if not existing:
                cancellation = CancelledTrain(
                    train_no=train_num,
                    travel_date=today,
                    reason=f"Real-time cancellation detected via {self.name}"
                )
                db.add(cancellation)
                db.commit()
                logger.info(f"🚫 [HYDRATION] Persisted cancellation for {train_num}")

    async def _wait_for_token(self, count: int):
        """Simple Token Bucket rate limiter."""
        while True:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(50, self._tokens + (elapsed * self._refill_rate))
            self._last_refill = now
            
            if self._tokens >= count:
                self._tokens -= count
                return
            await asyncio.sleep(1)

    async def shutdown(self):
        """Cleanup live service client."""
        await self._live_service.close()
        await super().shutdown()

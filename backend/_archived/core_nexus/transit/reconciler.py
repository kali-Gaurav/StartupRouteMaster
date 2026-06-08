import logging
import asyncio
import time
from typing import Dict, List, Optional, Set
from core.nexus.node import NexusNode
from core.nexus.state import SystemState

logger = logging.getLogger("nexus.transit.reconciler")

class NexusTransitNode(NexusNode):
    """[Task 9.10] Real-time Transit Gate Lifecycle Orchestrator.
    Manages IRCTC/GTFS-RT delay reconciliation.
    """
    
    def __init__(self, name: str = "transit", critical: bool = False, dependencies=None):
        super().__init__(name, critical=critical, dependencies=dependencies if dependencies else ["search"])
        self._active_trips: Set[str] = set()
        self._initialized = False

    async def on_start(self):
        """[Task 9.10] Register and start the Transit Sentinel."""
        logger.info("[NEXUS:TRANSIT] Delay Reconciler Node Initialized.")
        self._initialized = True
        self._loop_task = asyncio.create_task(self._transit_sentinel_loop())

    async def on_stop(self):
        """[Task 1.6] Graceful halt of transit polling."""
        if hasattr(self, "_loop_task"):
             self._loop_task.cancel()
        logger.info("[NEXUS:TRANSIT] Transit Node Shutdown.")

    async def _transit_sentinel_loop(self):
        """[Task 9.2] Background Polling Sentinel."""
        while True:
            # [Task 21] Heartbeat
            from core.nexus.bootstrapper import nexus_boot
            nexus_boot.recovery.record_heartbeat(self.name)
            
            await asyncio.sleep(120) # Poll every 2 minutes
            if not self._active_trips:
                await asyncio.sleep(10)
                continue
                
            logger.debug(f"[NEXUS:TRANSIT] Syncing status for {len(self._active_trips)} active trips...")
            for trip_id in list(self._active_trips):
                await self._sync_trip_delay(trip_id)

    async def _sync_trip_delay(self, trip_id: str):
         """[Task 9.3] Fetch live status and update Graph Overlay."""
         from services.live_status_service import LiveStatusService
         svc = LiveStatusService()
         
         # Note: trip_id usually contains train_number
         train_no = trip_id.split('_')[0] if '_' in trip_id else trip_id
         
         try:
             status = await svc.get_live_status(train_no)
             if not status: return
             
             delay_mins = status.get("delay_minutes", 0)
             is_cancelled = status.get("status") == "CANCELLED"
             
             # 2. Update Search Graph Overlay [Task 9.3]
             from core.nexus.search.node import search_node
             if search_node.graph:
                  search_node.graph.overlay.set_trip_delay(trip_id, delay_mins)
                  if is_cancelled:
                       search_node.graph.overlay.mark_cancelled(trip_id)
             
             # 3. [Task 13.5] Real-time Broadcast to SSE Clients
             from core.nexus.transit.stream import transit_streamer
             await transit_streamer.broadcast({
                  "trip_id": trip_id,
                  "train_no": train_no,
                  "delay_minutes": delay_mins,
                  "is_cancelled": is_cancelled,
                  "last_scraped": status.get("last_scraped"),
                  "status": status.get("status", "ON_TIME")
             })
                  
             logger.info(f"[NEXUS:TRANSIT] Reconciled & Broadcasted Trip {trip_id}: {delay_mins}m Delay.")
         except Exception as e:
             logger.error(f"[NEXUS:TRANSIT] Delay Sync Failed for {trip_id}: {e}")

    def track_trip(self, trip_id: str):
        """Add a trip to the high-intensity polling pool."""
        self._active_trips.add(trip_id)

transit_node = NexusTransitNode()

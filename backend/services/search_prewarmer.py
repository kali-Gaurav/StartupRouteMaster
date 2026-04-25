import logging
import asyncio
import os
import time
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
from core.hubs import MEGA_HUBS, MAJOR_HUBS
# from core.route_engine.orchestrator import route_orchestrator # Import later to avoid circular dependency
# from core.route_engine.constraints import RouteConstraints, Persona

logger = logging.getLogger("search-prewarmer")

class SearchPreWarmer:
    """
    [Task 151] Smart search pre-warmer to eliminate JIT latency.
    Primes the Hot Path O(1) Accelerator and L1/L2 caches before peak traffic.
    """
    
    def __init__(self):
        self._is_warming = False
        self._last_warmup = 0
        self._warmup_count = 0

    async def run_warmup_cycle(self, limit: int = 50):
        """
        Executes 'Ghost Searches' on top station pairs (MEGA_HUBS) 
        to warm the graph, indices, and hot-path cache.
        """
        if self._is_warming:
            logger.warning("⚠️ Warmup cycle already in progress. Skipping.")
            return
            
        self._is_warming = True
        start_time = time.perf_counter()
        
        try:
            logger.info("🔥 [PREWARMER] Starting Engine Warmup Cycle (Ghost Searches)...")
            from core.route_engine import route_engine
            from core.route_engine.base import RoutingRequest
            from core.route_engine.constraints import RouteConstraints, Persona
            
            # 1. Prepare Hub Pairs
            # Cross-product of top hubs (NDLS, CSMT, HWH, MAS, SBC, ADI)
            # Use only Mega hubs for limited budget
            top_hubs = list(MEGA_HUBS)[:8] 
            pairs = []
            for src in top_hubs:
                for dst in top_hubs:
                    if src != dst:
                        pairs.append((src, dst))
            
            # Limit pairs based on budget
            import random
            random.shuffle(pairs) # Randomize to avoid thundering herd on same pairs
            targets = pairs[:limit]
            
            # 2. Set Dates (Today and Tomorrow if late — only if snapshot already cached)
            dates = [datetime.now()]
            if datetime.now().hour > 18: 
                tomorrow = datetime.now() + timedelta(days=1)
                from core.route_engine.snapshot_manager import SnapshotManager
                _sm = SnapshotManager()
                if os.path.exists(_sm._get_filename(tomorrow)):
                    dates.append(tomorrow)
            
            # 3. Execution (Sequential to avoid VPS RAM spikes, but fast)
            constraints = RouteConstraints(
                persona=Persona.FAST,
                max_results=3,
                yield_goal=10
            )
            
            count = 0
            for src, dst in targets:
                for target_date in dates:
                    try:
                        # [Task 151] Ghost Search: Populates L1/L2 and Hot Path.
                        logger.debug(f"👻 Ghost Search: {src} -> {dst} ({target_date.date()})")
                        req = RoutingRequest(
                            source_code=src,
                            destination_code=dst,
                            departure_date=target_date,
                            constraints=constraints,
                            limit=3,
                            src_cluster_ids=[],
                            dst_cluster_ids=[]
                        )
        # Set request_timeout_ctx so engines get 20s instead of the 5s fallback.
                        # Without this, zombie threads fill the default thread pool.
                        from core.context import request_timeout_ctx
                        _token = request_timeout_ctx.set(10.0)  # 10s per engine max to avoid saturating thread pool
                        try:
                            await route_engine.orchestrator.search_all_tiers(req)
                        finally:
                            request_timeout_ctx.reset(_token)
                        count += 1
                        # Yield to other tasks — longer sleep to allow HTTP requests to get thread pool time
                        await asyncio.sleep(2.0)
                        
                        if count >= limit: break
                    except Exception as e:
                        logger.warning(f"Prewarmer failed pair {src}->{dst}: {e}")
                
                if count >= limit: break
            
            elapsed = time.perf_counter() - start_time
            self._last_warmup = time.time()
            self._warmup_count += 1
            logger.info(f"✅ [PREWARMER] Warmup Cycle Complete. {count} searches performed in {elapsed:.2f}s.")
            
        finally:
            self._is_warming = False

    async def start_background_loop(self):
        """
        Runs warmup on startup and then every 4 hours or before peak.
        """
        # 1. First Run (Startup)
        logger.info("🕒 [PREWARMER] Initializing startup warmup in 5 seconds...")
        await asyncio.sleep(5) 
        await self.run_warmup_cycle(limit=5)  # Small startup warmup — enough to prime graph, not starve HTTP
        
        while True:
            # 2. Daily Schedule (Pre-Peak check)
            now = datetime.now()
            # 7:30 AM (Morning Peak) or 4:30 PM (Evening Peak)
            is_pre_peak = (now.hour == 7 and now.minute >= 30) or (now.hour == 16 and now.minute >= 30)
            
            if is_pre_peak:
                 logger.info("🌤️ [PREWARMER] Peak approaching. Deep warming high-traffic corridors.")
                 await self.run_warmup_cycle(limit=60)
                 await asyncio.sleep(3600 * 2) # Sleep 2 hours to avoid re-triggering
            else:
                 # Standard maintenance every 6 hours
                 await asyncio.sleep(3600 * 6)
                 await self.run_warmup_cycle(limit=10)

    async def run_warmup_cycle_for_corridor(self, source_code: str, destination_code: str):
        """[Task 151 JIT] Targeted warmup for a specific corridor that had a miss."""
        logger.info(f"🔥 [JIT:WARM] Targeted warming for corridor {source_code}->{destination_code}...")
        
        from core.route_engine import route_engine
        from core.route_engine.base import RoutingRequest
        from core.route_engine.constraints import RouteConstraints, Persona
        
        # JIT for Today, Tomorrow, and Week-ahead
        for days in [0, 1, 7]:
            target_date = datetime.now() + timedelta(days=days)
            try:
                 req = RoutingRequest(
                    source_code=source_code,
                    destination_code=destination_code,
                    departure_date=target_date,
                    constraints=RouteConstraints(persona=Persona.FAST),
                    limit=3,
                    src_cluster_ids=[],
                    dst_cluster_ids=[]
                 )
                 await route_engine.orchestrator.search_all_tiers(req)
            except: pass
            await asyncio.sleep(0.5)

search_prewarmer = SearchPreWarmer()

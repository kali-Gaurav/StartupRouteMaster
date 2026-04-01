import os
import re

fname = r"C:\Users\Gaurav Nagar\OneDrive\Desktop\startupV2\backend\core\route_engine\orchestrator.py"
with open(fname, "r", encoding="utf-8") as f:
    code = f.read()

# 1. Add RoutingRequest and BaseRoutingEngine to imports
if "from .base import " not in code:
    code = code.replace("from core.data_structures import Route, RouteSegment, TransferConnection, Persona",
                        "from core.data_structures import Route, RouteSegment, TransferConnection, Persona\nfrom .base import BaseRoutingEngine, RoutingRequest, RoutingResponse")

# 2. Update __init__ registry
init_old = """    def __init__(self, route_engine_instance):
        from .tbr_router import TripBasedRouter # [Task 27.17]
        self.engine = route_engine_instance
        self.ultra_turbo = UltraTurboDirectEngine()
        self.turbo_router = TurboRouter()
        self.fast_router = FastPathRouter(None) # Graph will be set dynamically
        self.raptor = OptimizedRAPTOR()
        self.tbr_router = TripBasedRouter() # [Task 27.17]"""

init_new = """    def __init__(self, route_engine_instance):
        from .tbr_router import TripBasedRouter # [Task 27.17]
        self.engine = route_engine_instance
        self.engines: Dict[str, BaseRoutingEngine] = {
            "ultra_turbo_direct": UltraTurboDirectEngine(),
            "turbo_router": TurboRouter(),
            "fastpath_bfs": FastPathRouter(None),
            "raptor": OptimizedRAPTOR(),
            "trip_based": TripBasedRouter()
        }
        # Keep references if needed by other components, but orchestrator uses the registry
        self.ultra_turbo = self.engines["ultra_turbo_direct"]
        self.turbo_router = self.engines["turbo_router"]
        self.fast_router = self.engines["fastpath_bfs"]
        self.raptor = self.engines["raptor"]
        self.tbr_router = self.engines["trip_based"]"""

code = code.replace(init_old, init_new)

# 3. Modify search_all_tiers signature
sig_old = """    async def search_all_tiers(

        self,
        source_code: str,
        destination_code: str,
        departure_date: datetime,
        constraints: RouteConstraints,
        limit: int = 15,
        db=None,
        skip_heavy: bool = False,
        source_stop=None,
        dest_stop=None,
        on_progress: Optional[Callable[[float], None]] = None,
        discovery_cache_key: Optional[str] = None
    ) -> List[Route]:"""

sig_new = """    async def search_all_tiers(
        self,
        request: RoutingRequest,
        skip_heavy: bool = False,
        source_stop=None,
        dest_stop=None,
        on_progress: Optional[Callable[[float], None]] = None,
        discovery_cache_key: Optional[str] = None
    ) -> List[Route]:
        source_code = request.source_code
        destination_code = request.destination_code
        departure_date = request.departure_date
        constraints = request.constraints
        limit = request.limit
        db = request.db_session"""
code = code.replace(sig_old, sig_new)

# 4. Modify get_engine_coro usage
# Note: Since the file has many nested coros inside wrapped_search, let's write out the new implementation for wrapped_search and the execution logic.

new_search_logic = """
                async def wrapped_search(engine_name: str, priority=10):
                    if priority > 1: await asyncio.sleep(0.005 * priority)
                    async with self._global_resource_sem:
                        st = time.perf_counter()
                        try:
                            # Inner timeout per engine task
                            async with asyncio.timeout(remaining_timeout * 0.9):
                                if engine_name == "HubTier0":
                                    res_obj = await self._search_tier_0_hubs_async(src_cluster_ids[0] if src_cluster_ids else 0, dst_cluster_ids[0] if dst_cluster_ids else 0, departure_date, db)
                                    res = res_obj # Fallback, _search_tier_0_hubs_async returns List[Route]
                                else:
                                    # Use Registry
                                    engine = None
                                    for e in self.engines.values():
                                        if e.engine_id.lower().startswith(engine_name.lower().split("_")[0]):
                                            engine = e
                                            break
                                    if not engine: return []
                                    request.src_cluster_ids = src_cluster_ids
                                    request.dst_cluster_ids = dst_cluster_ids
                                    request.graph = graph
                                    response: RoutingResponse = await engine.find_routes(request)
                                    res = response.routes
                            
                            # [Nexus Stream] Incremental Cache Hydration
                            # Turbo/Ultra results hydration logic removed as it's now internal to the engine

                            if discovery_cache_key and res:
                                # Write to cache in background
                                for r in res: r.metadata["discovery_engine"] = engine_name
                                asyncio.create_task(multi_layer_cache.hset_routes(discovery_cache_key, res))
                                logger.debug(f"🌊 [NEXUS:STREAM] Pushed {len(res)} routes from {engine_name} to cache.")

                            lat = (time.perf_counter() - st) * 1000
                            logger.info(f"Engine {engine_name} took {lat:.2f}ms")
                            # [Task 32] Record latency immediately
                            asyncio.create_task(performance_registry.record(engine_name, lat, len(res)))
                            progress.update()
                            return res
                        except Exception as e:
                            logger.error(f"Engine {engine_name} failed or timed out: {e}", exc_info=True)
                            progress.update()
                            return []

                def is_allowed(name_):
                    if not constraints.permitted_engines: return True
                    return any(e.lower() in name_.lower() for e in constraints.permitted_engines)

                # 3. Dynamic Parallel Search Execution (Task 32: Competitive Ranking)
                all_results = {}
                ranked_engines = await performance_registry.get_ranked_list(
                    is_long_dist=is_long_dist, 
                    is_hub_centric=is_hub_centric
                )
                
                # Split engines into 'Elite' (Top 3) and 'Discovery' (Rest)
                elite_engine_names = ranked_engines[:3]
                secondary_engine_names = ranked_engines[3:]
                
                # --- PHASE 1: Elite Engines (Fastest & Most Accurate) ---
                elite_tasks = {}
                for name in elite_engine_names:
                    if is_allowed(name):
                         elite_tasks[name] = asyncio.create_task(wrapped_search(name, priority=0))

                # Wait for Elite Engines (short-circuit wait)
                if elite_tasks:
                    done_elite, _ = await asyncio.wait(elite_tasks.values(), timeout=2.5)
                    for name, task in elite_tasks.items():
                        if task in done_elite and not task.cancelled():
                             try:
                                 res = task.result()
                                 if res: 
                                     all_results[name] = res
                             except: pass"""

                
# Finding the block in orchestrator to replace.
escaped = code[code.find("async def wrapped_search(name, coro, priority=10):"): code.find("                # --- PHASE 2: Pruning Discovery [Deep Optimization] ---")]
if not escaped:
    print("Failed to find wrapped_search block")
else:
    code = code.replace(escaped, new_search_logic.strip("\n") + "\n\n")

# Further fix secondary and temporal wrapped_search calls
code = code.replace("coro = self._get_engine_coro(name, source_stop.code, dest_stop.code, departure_date, engine_limit, constraints, db, graph, src_cluster_ids, dst_cluster_ids)\n                            if coro:\n                                 secondary_tasks[name] = asyncio.create_task(wrapped_search(name, coro, priority=2))",
                    "secondary_tasks[name] = asyncio.create_task(wrapped_search(name, priority=2))")

code = code.replace("coro = self._get_engine_coro(name, source_stop.code, dest_stop.code, target_date, engine_limit, constraints, db, graph, src_cluster_ids, dst_cluster_ids)\n                                   if coro:\n                                        t_name = f\"{name}_{delta}d\"\n                                        temporal_tasks[t_name] = asyncio.create_task(wrapped_search(name, coro, priority=5))",
                    "t_name = f\"{name}_{delta}d\"\n                                        temporal_tasks[t_name] = asyncio.create_task(wrapped_search(name, priority=5))")

code = code.replace("coro = self._get_engine_coro(name, source_stop.code, dest_stop.code, departure_date, engine_limit, constraints, db, graph, src_satellites, dst_satellites)\n                                   if coro:\n                                        satellite_tasks[f\"{name}_sat\"] = asyncio.create_task(wrapped_search(name, coro, priority=8))",
                    "request.src_cluster_ids = src_satellites\n                                   request.dst_cluster_ids = dst_satellites\n                                   satellite_tasks[f\"{name}_sat\"] = asyncio.create_task(wrapped_search(name, priority=8))")

# Remove Turbo hydration logic from collection since it's already inside Turbo router now
code = code.replace("""all_raw = []
                for name, res in all_results.items():
                    if name in ("Turbo", "UltraTurbo") and isinstance(res[0], dict):
                        all_raw.extend(self._hydrate_turbo_results(res, source_stop.code, dest_stop.code, departure_date))
                    else:
                        all_raw.extend(res)""",
"""all_raw = []
                for name, res in all_results.items():
                    all_raw.extend(res)""")


with open(fname, "w", encoding="utf-8") as f:
    f.write(code)

print("Orchestrator refactor script completed successfully.")

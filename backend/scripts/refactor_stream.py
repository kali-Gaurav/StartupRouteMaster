import re

fname = r"C:\Users\Gaurav Nagar\OneDrive\Desktop\startupV2\backend\core\route_engine\orchestrator.py"
with open(fname, "r", encoding="utf-8") as f:
    code = f.read()

sig_old = """    async def stream_all_tiers(
        self,
        source_code: str,
        destination_code: str,
        departure_date: datetime,
        constraints: RouteConstraints,
        limit: int = 15,
        db=None,
        source_stop=None,
        dest_stop=None
    ):"""

sig_new = """    async def stream_all_tiers(
        self,
        request: RoutingRequest,
        db=None,
        source_stop=None,
        dest_stop=None
    ):
        source_code = request.source_code
        destination_code = request.destination_code
        departure_date = request.departure_date
        constraints = request.constraints
        limit = request.limit
        if not db and request.db_session: db = request.db_session"""

code = code.replace(sig_old, sig_new)

# Modify process_and_yield and the engine block
new_block = """            async def process_and_yield(name, coro, timeout):
                try:
                    async with asyncio.timeout(timeout):
                        response = await coro
                    if not response: return []
                    if hasattr(response, "routes"):
                        res = response.routes
                    elif isinstance(response, list):
                        res = response
                    else:
                        res = []
                    if not res: return []
                    
                    all_raw = []
                    # Other engines return Route objects
                    for r in res: 
                        if isinstance(r, Route): r.metadata["engine"] = name.lower()
                    all_raw.extend(res)
                        
                    all_routes = [r for r in all_raw if self._is_valid_route(r)]
                    all_routes = await self._filter_cancelled_trains(all_routes, departure_date, db)
                    
                    # [Task 30.4] Streaming Deduplication
                    new_routes = []
                    for r in all_routes:
                        if r.journey_id not in seen_jids:
                            seen_jids.add(r.journey_id)
                            new_routes.append(r)

                    if new_routes:
                        # [Task 10] Discovery Mode: Skip heavy hydration
                        if not constraints.discovery_only:
                            # [Task 30.5] Streaming Hydration
                            await self.hydration_pipeline.execute(new_routes, constraints, graph, db)
                        else:
                            # Minimal metadata for debugging
                            for r in new_routes: r.metadata["discovery_mode"] = True
                        
                        # Apply Metadata & Sorting
                        latency_total = (time.perf_counter() - start_time) * 1000
                        for r in new_routes:
                            r.metadata["orchestrator_latency_ms"] = round(latency_total, 2)
                            if "engine" not in r.metadata: r.metadata["engine"] = name.lower()
                            if "tier" not in r.metadata:
                                if "ultra" in r.metadata["engine"]: r.metadata["tier"] = 1
                                elif "turbo" in r.metadata["engine"]: r.metadata["tier"] = 2
                                else: r.metadata["tier"] = 3
                        
                        return new_routes
                except Exception as e:
                    logger.error(f" Engine {name} failed or timed out: {e}")
                return []

            def is_allowed(name: str) -> bool:
                if not constraints.permitted_engines: return True
                return any(e.lower() in name.lower() for e in constraints.permitted_engines)

            tasks = []
            if is_allowed("HubTier0"):
                tasks.append(asyncio.create_task(process_and_yield("HubTier0", self._search_tier_0_hubs_async(source_stop.id, dest_stop.id, departure_date, db), total_timeout)))
            
            # Using Strategy registry for new engines
            for name, engine in self.engines.items():
                if is_allowed(name):
                    # update request with latest cluster logic
                    request.src_cluster_ids = src_cluster_ids
                    request.dst_cluster_ids = dst_cluster_ids
                    request.graph = graph
                    
                    # specific timeouts
                    t = total_timeout
                    if "fastpath" in name.lower(): t = total_timeout * 0.8
                    if "raptor" in name.lower(): t = total_timeout * 0.9
                    
                    if skip_heavy and ("fastpath" in name.lower() or "raptor" in name.lower() or "tbr" in name.lower()):
                        continue
                    
                    tasks.append(asyncio.create_task(process_and_yield(name, engine.find_routes(request), t)))"""

escaped = code[code.find("async def process_and_yield(name, coro, timeout):") : code.find("            # Use as_completed to yield results instantly as they finish")]
if not escaped:
    print("FAILED to find block")
else:
    code = code.replace(escaped, new_block + "\n")

with open(fname, "w", encoding="utf-8") as f:
    f.write(code)
print("stream_all_tiers updated successfully.")

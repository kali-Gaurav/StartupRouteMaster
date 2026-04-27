
import time
import asyncio
from datetime import timedelta
from typing import List, Callable, Any
from core.data_structures import Route, ensure_datetime
from .constraints import RouteConstraints
from core.pricing.fare_calculator import calculate_fare
from .scoring import RouteScorer
import logging

logger = logging.getLogger(__name__)

class HydrationPipeline:
    """[Task 28.1] Modular pipeline for route result hydration."""
    def __init__(self):
        self.steps: List[Callable] = []

    def add_step(self, step: Callable):
        self.steps.append(step)

    async def execute(self, routes: List[Route], constraints: RouteConstraints, graph: Any, db: Any):
        for step in self.steps:
            st = time.perf_counter()
            try:
                if asyncio.iscoroutinefunction(step):
                    await step(routes, constraints, graph, db)
                else:
                    step(routes, constraints, graph, db)
            except Exception as e:
                logger.warning(f"[HYDRATION] Step {step.__name__} failed (non-fatal): {e}")
            lat = (time.perf_counter() - st) * 1000
            for r in routes:
                if "hydration_stats" not in r.metadata: r.metadata["hydration_stats"] = {}
                r.metadata["hydration_stats"][step.__name__] = round(lat, 2)


    async def _step_realtime_propagation(self, routes: List[Route], constraints: RouteConstraints, graph, db):
        """[Task 16 & Task 30] Advanced delay propagation across transfers."""
        for r in routes:
            for i, s in enumerate(r.segments):
                s.departure_time = ensure_datetime(s.departure_time)
                s.arrival_time = ensure_datetime(s.arrival_time, s.departure_time)
                try:
                    delay = graph.overlay.get_trip_delay(int(s.trip_id)) if s.trip_id is not None else 0
                except (ValueError, TypeError):
                    delay = 0
                if delay > 0:
                    s.departure_time += timedelta(minutes=delay)
                    s.arrival_time += timedelta(minutes=delay)
                    s.metadata["live_delay_mins"] = delay
                    if "alerts" not in r.metadata: r.metadata["alerts"] = []
                    r.metadata["alerts"].append(f"Train {s.train_number} is running {delay}m late.")

            # Re-calculate transfers and total duration
            if len(r.segments) > 1:
                last_arr = ensure_datetime(r.segments[-1].arrival_time)
                first_dep = ensure_datetime(r.segments[0].departure_time)
                r.total_duration = int((last_arr - first_dep).total_seconds() // 60)
                for i in range(len(r.transfers)):
                    # Update transfer wait times based on new realtime arrivals/departures
                    arr_seg_time = ensure_datetime(r.segments[i].arrival_time)
                    dep_seg_time = ensure_datetime(r.segments[i+1].departure_time)
                    wait = int((dep_seg_time - arr_seg_time).total_seconds() // 60)
                    r.transfers[i].duration_minutes = wait
                    if wait < 15: # Critical Threshold
                        r.metadata["reliability_badge"] = "CRITICAL"
                        r.metadata["alerts"].append(f"Risky connection at {r.transfers[i].station_name} ({wait}m wait)!")

    async def _step_vectorized_fares(self, routes: List[Route], constraints: RouteConstraints, graph, db):
        from core.pricing.fare_calculator import calculate_fares_batch
        import numpy as np
        dists = np.array([float(r.total_distance or 0.0) for r in routes], dtype=np.float32)
        batch_fares = calculate_fares_batch(dists, constraints.preferred_class or "SL", is_tatkal=constraints.quota == "TQ", db=db)
        for i, r in enumerate(routes):
            r.total_cost = float(batch_fares[i])
            if r.total_distance > 0:
                for s in r.segments:
                    s.fare = round((s.distance_km / r.total_distance) * r.total_cost, 2)

    def _step_realtime_platforms(self, routes: List[Route], constraints: RouteConstraints, graph, db):
        for r in routes:
            for s in r.segments:
                platform = graph.overlay.platform_changes.get((s.trip_id, s.departure_stop_id))
                if platform:
                    s.metadata["platform_realtime"] = platform
                    s.metadata["platform_note"] = "Live Update"
                else:
                    # [Task 28] Static Heatmap Fallback
                    # Logic: Fast trains (12xxx) usually use lower PFs; Slow trains use higher ones.
                    t_no = str(s.train_number)
                    if t_no.isdigit():
                        if t_no.startswith(("12", "22")): 
                             pf = (int(t_no) % 3) + 1 # PFs 1, 2, 3
                        else:
                             pf = (int(t_no) % 5) + 4 # PFs 4, 5, 6, 7, 8
                        s.metadata["platform_predicted"] = pf
                    else:
                        s.metadata["platform_predicted"] = "TBD"
                    
                    s.metadata["platform_note"] = "Historical Heuristic"

    def _step_amenities(self, routes: List[Route], constraints: RouteConstraints, graph, db):
        for r in routes:
            for s in r.segments:
                t_str = str(s.train_number)
                s.metadata["amenities"] = {
                    "pantry": t_str.startswith(("12", "22")),
                    "e_catering": True,
                    "charging": True,
                    "wifi": t_str.startswith("120")
                }

    async def _step_multi_class_fares(self, routes: List[Route], constraints: RouteConstraints, graph, db):
        # [Task 27] Try multiple classes if the preferred one is missing
        # [Task 12.8] Tier-Aware Fare Discovery (Skip RapidAPI for Free/Discovery Tier)
        mode = constraints.metadata.get("verification_mode", "DISCOVERY_ONLY")
        from .constraints import DiscoveryModel
        is_free_tier = constraints.discovery_model == DiscoveryModel.BACKBONE
        skip_api = is_free_tier or mode == "DISCOVERY_ONLY"
        
        from providers.gateway import provider_gateway
        pref_classes = constraints.preferred_classes or (["3A", "2A", "SL"] if not constraints.preferred_class else [constraints.preferred_class])
        
        async def hydrate_route_fare(r):
            total_cost = 0.0
            for s in r.segments:
                fare_found = False
                # [Elite Policy] Only call RapidAPI if in Omniscient/Elite mode
                if not skip_api:
                    for cls in pref_classes:
                        try:
                            dep_time = ensure_datetime(s.departure_time)
                            f = await provider_gateway.get_fare(
                                s.trip_id,
                                dep_time.strftime("%Y-%m-%d"),
                                getattr(s, "departure_code", ""),
                                getattr(s, "arrival_code", ""),
                                cls,
                            )
                            if f:
                                fare_amount = getattr(f, "amount", 0.0)
                                s.metadata["fare"] = fare_amount
                                s.metadata["class"] = cls
                                total_cost += fare_amount
                                fare_found = True
                                break
                        except Exception: continue
                
                if not fare_found:
                    # HEURISTIC FALLBACK: Use distance-based fare calculator when available
                    if s.distance_km and s.distance_km > 0:
                        fare_result = calculate_fare(s.distance_km, constraints.preferred_class or "SL")
                        s.metadata["fare"] = float(fare_result.get("total_fare", 0.0)) or (s.distance_km * 0.5)
                    else:
                        # Absolute fallback: duration-based estimate
                        t_no = str(s.train_number)
                        base = 350.0 if t_no.startswith(("12", "22")) else 200.0
                        s.metadata["fare"] = base + (s.duration_minutes * 0.4)
                    s.metadata["class"] = constraints.preferred_class or "SL"
                    s.metadata["fare_note"] = "Heuristic Estimate"
                    total_cost += s.metadata["fare"]


            r.total_cost = total_cost

        await asyncio.gather(*[hydrate_route_fare(r) for r in routes])
        return routes

    async def _step_elite_verification(self, routes: List[Route], constraints: RouteConstraints, graph, db):
        """[Premium Tip] Tier 3 Only: Proactive Seat Verification & FOMO Injection."""
        from .constraints import DiscoveryModel
        if constraints.discovery_model != DiscoveryModel.OMNISCIENT:
            return

        from providers.gateway import provider_gateway
        
        async def verify_route_availability(r):
            async def verify_segment(s):
                # [Elite] Verify booking status for the primary class
                cls = s.metadata.get("class", "SL")
                try:
                    dep_time = ensure_datetime(s.departure_time)
                    status = await provider_gateway.get_seat_availability(
                        s.trip_id,
                        dep_time.strftime("%Y-%m-%d"),
                        getattr(s, "departure_code", ""),
                        getattr(s, "arrival_code", ""),
                        cls,
                        constraints.quota
                    )
                    if status:
                        s.metadata["live_availability"] = str(getattr(status, "current_status", "AVAILABLE"))
                        s.metadata["probability"] = float(getattr(status, "probability", 0.95))
                        
                        # [Task 12.9] FOMO Injection
                        avail_count = 0
                        status_str = str(s.metadata["live_availability"]).upper()
                        import re
                        match = re.search(r'(\d+)', status_str)
                        if match: avail_count = int(match.group(1))
                        
                        if "AVAILABLE" in status_str and 0 < avail_count < 10:
                            s.metadata["fomo_badge"] = "LOW_STOCK"
                            r.metadata["has_high_fomo"] = True
                            if "alerts" not in r.metadata: r.metadata["alerts"] = []
                            r.metadata["alerts"].append(f"Hurry! Only {avail_count} seats left in {cls} for {s.train_number}")
                except Exception: pass

            await asyncio.gather(*[verify_segment(s) for s in r.segments])

        await asyncio.gather(*[verify_route_availability(r) for r in routes])

    async def _step_reliability_badges(self, routes: List[Route], constraints: RouteConstraints, graph, db):
        for r in routes:
            rel_sum = 0
            for s in r.segments:
                s_rel = 0.95 if str(s.train_number).startswith("1") else 0.85
                s.metadata["reliability_badge"] = "HIGH" if s_rel > 0.9 else "AVERAGE"
                rel_sum += s_rel
            r.metadata["avg_reliability"] = rel_sum / len(r.segments) if r.segments else 0.5

    def _step_journey_story(self, routes: List[Route], constraints: RouteConstraints, graph, db):
        for r in routes:
            dur_rating = max(1, 5 - ((r.total_duration or 0) / 600.0))
            cost_rating = max(1, 5 - ((r.total_cost or 0.0) / 1000.0))
            tr_rating = max(1, 5 - (len(r.transfers) * 1.5))
            r.metadata["rating"] = round((dur_rating * 0.4) + (cost_rating * 0.3) + (tr_rating * 0.3), 1)
            parts = []
            if len(r.segments) == 1: parts.append("Direct journey")
            else: parts.append(f"{len(r.transfers)} transfer(s)")
            if r.total_duration < 360: parts.append("Very fast")
            dep_time = ensure_datetime(r.segments[0].departure_time) if r.segments else None
            dep_hour = dep_time.hour if dep_time else 12
            if 21 <= dep_hour or dep_hour <= 4: parts.append("Overnight")
            r.metadata["journey_story"] = " • ".join(parts)

    def _step_integrity_check(self, routes: List[Route], constraints: RouteConstraints, graph, db):
        """[Task 28.10] Final data validation & optimized synchronous scoring."""
        for r in routes:
            if not r.total_cost or r.total_cost < 1:
                # Use distance-based heuristic instead of blind ₹500
                if r.total_distance and r.total_distance > 0:
                    fare_result = calculate_fare(r.total_distance, constraints.preferred_class or "SL")
                    r.total_cost = float(fare_result.get("total_fare", 0.0)) or (r.total_distance * 0.5)
                else:
                    # Last resort: estimate from duration
                    r.total_cost = max(150.0, (r.total_duration or 0) * 1.5)
                r.metadata["fare_source"] = "INTEGRITY_ESTIMATE"
            if not r.total_duration or r.total_duration < 1:
                if r.segments:
                    first_dep = ensure_datetime(r.segments[0].departure_time)
                    arrival = ensure_datetime(r.segments[-1].arrival_time, first_dep)
                    departure = ensure_datetime(r.segments[0].departure_time, arrival)
                    r.total_duration = int((arrival - departure).total_seconds() / 60)
            
            # [Task 28.1] Use synchronous scoring to avoid massive event loop overhead
            r.score = RouteScorer.score_route_sync(r, constraints, passengers=constraints.passengers)


    # --- HELPERS ---


def create_default_pipeline() -> HydrationPipeline:
    """Build the default hydration sequence used by the orchestrator."""
    pipeline = HydrationPipeline()
    pipeline.add_step(pipeline._step_realtime_propagation)
    pipeline.add_step(pipeline._step_realtime_platforms)
    pipeline.add_step(pipeline._step_amenities)
    pipeline.add_step(pipeline._step_multi_class_fares)      # Primary fare calculation (API + heuristic)
    pipeline.add_step(pipeline._step_elite_verification)
    pipeline.add_step(pipeline._step_reliability_badges)
    pipeline.add_step(pipeline._step_journey_story)
    pipeline.add_step(pipeline._step_integrity_check)
    return pipeline

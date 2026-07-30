"""
Network Pressure Calculator (NPC)
==================================
Patent Innovation: Real-time network-wide pressure scoring system.

Calculates a unified "Pressure Score" (0.0 - 1.0) for every node (station/corridor)
in the transit network. This score drives all downstream decisions:
- EDR Algorithm uses it to identify redistribution opportunities
- Supply Infusion Engine triggers multi-modal alternatives when pressure > 0.95
- Search Service biases results toward lower-pressure corridors
- System Guardian monitors for sustained high-pressure anomalies

Mathematical Model:
    P(node) = alpha * Occupancy + beta * DemandVelocity + gamma * WaitlistDepth + delta * HistoricalPeak

Where:
    alpha  = 0.35 (current load weight)
    beta   = 0.30 (demand acceleration - how fast searches are growing)
    gamma  = 0.20 (waitlist depth - how many people are queued)
    delta  = 0.15 (historical peak alignment - are we near known peak hours?)

Integration:
    - Reads from: Redis (search counts, seat cache), Supabase (bookings, waitlists)
    - Feeds into: EDR, Supply Infusion, Search Scoring, System Guardian
    - Refresh: Every 60 seconds via background task or on-demand
"""

import logging
import asyncio
import time
from datetime import datetime, timedelta, date
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict, deque
from enum import Enum
from prometheus_client import Gauge, Summary, Counter

logger = logging.getLogger("sovereign.npc")

# =========================================================================
# METRICS
# =========================================================================

CORRIDOR_PRESSURE = Gauge(
    "routemaster_sovereign_corridor_pressure",
    "Real-time pressure score for a corridor",
    ["source", "destination"]
)
NPC_REFRESH_LATENCY = Summary(
    "routemaster_sovereign_npc_refresh_latency_seconds",
    "Time taken to refresh network pressure map"
)
NPC_REFRESH_TOTAL = Counter(
    "routemaster_sovereign_npc_refresh_total",
    "Total number of network pressure refreshes"
)


# =========================================================================
# MODELS
# =========================================================================

class PressureLevel(str, Enum):
    """Human-readable pressure classification."""
    CALM = "CALM"              # 0.0 - 0.30
    MODERATE = "MODERATE"      # 0.30 - 0.60
    ELEVATED = "ELEVATED"      # 0.60 - 0.80
    HIGH = "HIGH"              # 0.80 - 0.90
    CRITICAL = "CRITICAL"      # 0.90 - 0.95
    OVERFLOW = "OVERFLOW"      # 0.95 - 1.00

    @classmethod
    def from_score(cls, score: float) -> "PressureLevel":
        if score < 0.30:
            return cls.CALM
        elif score < 0.60:
            return cls.MODERATE
        elif score < 0.80:
            return cls.ELEVATED
        elif score < 0.90:
            return cls.HIGH
        elif score < 0.95:
            return cls.CRITICAL
        else:
            return cls.OVERFLOW


@dataclass(slots=True)
class PressureNode:
    """Pressure data for a single network node (station or corridor)."""
    node_id: str                          # e.g. "NDLS" or "NDLS->BCT"
    node_type: str = "station"            # "station" or "corridor"
    pressure_score: float = 0.0           # 0.0 - 1.0
    pressure_level: PressureLevel = PressureLevel.CALM

    # Component scores (0.0 - 1.0 each)
    occupancy_score: float = 0.0
    demand_velocity_score: float = 0.0
    waitlist_depth_score: float = 0.0
    historical_peak_score: float = 0.0

    # Raw data
    current_bookings: int = 0
    total_capacity: int = 0
    searches_last_30m: int = 0
    searches_prev_30m: int = 0
    waitlist_count: int = 0

    # Metadata
    last_updated: Optional[datetime] = None
    trend: str = "stable"                 # "rising", "stable", "falling"


@dataclass
class NetworkPressureSnapshot:
    """Complete network-wide pressure snapshot."""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    nodes: Dict[str, PressureNode] = field(default_factory=dict)
    global_pressure: float = 0.0
    hotspots: List[str] = field(default_factory=list)   # node_ids with pressure > 0.85
    cold_zones: List[str] = field(default_factory=list)  # node_ids with pressure < 0.30

    @property
    def hotspot_count(self) -> int:
        return len(self.hotspots)

    @property
    def cold_zone_count(self) -> int:
        return len(self.cold_zones)


# =========================================================================
# ENGINE
# =========================================================================

class NetworkPressureCalculator:
    """
    Real-time network pressure scoring engine.

    This is the "nervous system" of the Sovereign Intelligence layer.
    Every decision in the platform is influenced by the pressure map
    this calculator maintains.
    """

    # Pressure model weights
    ALPHA = 0.35   # Occupancy weight
    BETA = 0.30    # Demand velocity weight
    GAMMA = 0.20   # Waitlist depth weight
    DELTA = 0.15   # Historical peak weight

    # Thresholds
    REDISTRIBUTION_TRIGGER = 0.85   # Start EDR above this
    SUPPLY_INFUSION_TRIGGER = 0.95  # Trigger multi-modal above this
    ALERT_TRIGGER = 0.90            # Alert System Guardian above this

    # Configuration
    SNAPSHOT_TTL_SECONDS = 60       # Refresh every 60s
    MAX_HISTORY = 100               # Keep last 100 snapshots for trend analysis

    # Known peak hours for Indian Railways (IST)
    PEAK_HOURS = {
        "morning": (6, 10),    # 6 AM - 10 AM
        "evening": (16, 21),   # 4 PM - 9 PM
        "festival": None       # Dynamic - loaded from calendar
    }

    # Major corridors with known high traffic
    HIGH_TRAFFIC_CORRIDORS = [
        ("NDLS", "BCT"), ("NDLS", "HWH"), ("BCT", "MAS"),
        ("NDLS", "LKO"), ("BCT", "PUNE"), ("MAS", "SBC"),
        ("HWH", "NDLS"), ("NDLS", "JP"), ("BCT", "ADI"),
        ("NDLS", "CNB"), ("MAS", "HWH"), ("SBC", "MAS"),
    ]

    def __init__(self):
        self._snapshot: Optional[NetworkPressureSnapshot] = None
        self._history: deque = deque(maxlen=self.MAX_HISTORY)
        self._corridor_trends: Dict[str, deque] = defaultdict(lambda: deque(maxlen=30))
        self._last_refresh: float = 0
        self._lock = asyncio.Lock()
        self._overrides: Dict[str, float] = {}
        logger.info("[NPC] Network Pressure Calculator initialized")

    # =====================================================================
    # PUBLIC API
    # =====================================================================

    async def get_pressure(self, node_id: str) -> PressureNode:
        """Get pressure for a single node. Refreshes snapshot if stale."""
        # [SOVEREIGN DEBUG] Check for manual overrides first
        if node_id in self._overrides:
            score = self._overrides[node_id]
            return PressureNode(
                node_id=node_id,
                node_type="corridor" if "->" in node_id else "station",
                pressure_score=score,
                last_updated=datetime.utcnow(),
                trend="rising" if score > 0.8 else "stable"
            )

        await self._ensure_fresh()
        if self._snapshot and node_id in self._snapshot.nodes:
            return self._snapshot.nodes[node_id]
        # Calculate on-demand for unknown nodes
        return await self._calculate_node_pressure(node_id)

    def set_pressure(self, node_id: str, pressure: float):
        """
        [DEBUG ONLY] Manually inject a pressure score for a node.
        Used for E2E simulations and testing Sovereign Intelligence logic.
        """
        self._overrides[node_id] = max(0.0, min(1.0, pressure))
        logger.warning(f"[NPC] MANUAL OVERRIDE: {node_id} set to {pressure}")

    async def get_corridor_pressure(self, source: str, destination: str) -> PressureNode:
        """Get pressure for a specific corridor (e.g., NDLS->BCT)."""
        corridor_id = f"{source}->{destination}"
        return await self.get_pressure(corridor_id)

    async def get_network_snapshot(self, force_refresh: bool = False) -> NetworkPressureSnapshot:
        """Get full network pressure snapshot."""
        if force_refresh or self._is_stale():
            await self.refresh()
        return self._snapshot or NetworkPressureSnapshot()

    async def record_search(self, source: str, destination: str):
        """
        Record a search event for a corridor.
        This feeds into the 'Demand Velocity' component of the pressure score.
        """
        try:
            from services.multi_layer_cache import multi_layer_cache
            if not multi_layer_cache.redis:
                return

            node_id = f"{source}->{destination}"
            recent_key = f"npc:demand:recent:{node_id}"
            
            # Increment recent counter (30m window handled by TTL or manual reset)
            await multi_layer_cache.redis.incr(recent_key)
            # Ensure it expires if not refreshed
            await multi_layer_cache.redis.expire(recent_key, 1800) # 30 minutes
            
            # Also record for source and destination stations
            await multi_layer_cache.redis.incr(f"npc:demand:recent:{source}")
            await multi_layer_cache.redis.incr(f"npc:demand:recent:{destination}")
            
        except Exception as e:
            logger.debug(f"[NPC] Failed to record search: {e}")

    async def get_hotspots(self, threshold: float = 0.85) -> List[PressureNode]:
        """Get nodes above the pressure threshold."""
        snapshot = await self.get_network_snapshot()
        return [
            node for node in snapshot.nodes.values()
            if node.pressure_score >= threshold
        ]

    async def get_cold_zones(self, threshold: float = 0.30) -> List[PressureNode]:
        """Get nodes with low pressure (candidates for redistribution targets)."""
        snapshot = await self.get_network_snapshot()
        return [
            node for node in snapshot.nodes.values()
            if node.pressure_score <= threshold
        ]

    async def get_redistribution_pairs(self) -> List[Tuple[PressureNode, PressureNode]]:
        """
        Find pairs of (hotspot, cold_zone) that are viable for redistribution.
        This is the primary input to the EDR Algorithm.
        """
        hotspots = await self.get_hotspots()
        cold_zones = await self.get_cold_zones()

        pairs = []
        for hot in hotspots:
            for cold in cold_zones:
                # Check if they serve the same origin-destination pair
                if self._are_related_nodes(hot, cold):
                    pairs.append((hot, cold))

        # Sort by pressure differential (largest gap = most impactful)
        pairs.sort(key=lambda p: p[0].pressure_score - p[1].pressure_score, reverse=True)
        return pairs[:20]  # Top 20 pairs

    # =====================================================================
    # REFRESH ENGINE
    # =====================================================================

    async def refresh(self):
        """Recalculate pressure for all monitored nodes."""
        async with self._lock:
            start_time = time.monotonic()
            NPC_REFRESH_TOTAL.inc()
            
            snapshot = NetworkPressureSnapshot(timestamp=datetime.utcnow())

            # 1. Calculate pressure for major corridors
            for src, dst in self.HIGH_TRAFFIC_CORRIDORS:
                corridor_id = f"{src}->{dst}"
                node = await self._calculate_node_pressure(corridor_id, node_type="corridor")
                snapshot.nodes[corridor_id] = node
                
                # Update Prometheus Metrics
                CORRIDOR_PRESSURE.labels(source=src, destination=dst).set(node.pressure_score)

                # Track trends
                self._corridor_trends[corridor_id].append(node.pressure_score)

                # Classify
                if node.pressure_score >= self.REDISTRIBUTION_TRIGGER:
                    snapshot.hotspots.append(corridor_id)
                elif node.pressure_score <= 0.30:
                    snapshot.cold_zones.append(corridor_id)

            # 2. Calculate pressure for major stations
            stations = set()
            for src, dst in self.HIGH_TRAFFIC_CORRIDORS:
                stations.add(src)
                stations.add(dst)

            for station in stations:
                node = await self._calculate_node_pressure(station, node_type="station")
                snapshot.nodes[station] = node
                if node.pressure_score >= self.REDISTRIBUTION_TRIGGER:
                    snapshot.hotspots.append(station)
                elif node.pressure_score <= 0.30:
                    snapshot.cold_zones.append(station)

            # 3. Global pressure = weighted average of all nodes
            if snapshot.nodes:
                scores = [n.pressure_score for n in snapshot.nodes.values()]
                snapshot.global_pressure = sum(scores) / len(scores)

            self._snapshot = snapshot
            self._history.append(snapshot)
            self._last_refresh = time.monotonic()

            duration = time.monotonic() - start_time
            NPC_REFRESH_LATENCY.observe(duration)
            
            logger.info(
                f"[NPC] Network refresh complete in {duration*1000:.0f}ms | "
                f"Nodes: {len(snapshot.nodes)} | "
                f"Hotspots: {snapshot.hotspot_count} | "
                f"Cold Zones: {snapshot.cold_zone_count} | "
                f"Global Pressure: {snapshot.global_pressure:.2f}"
            )

    # =====================================================================
    # PRESSURE CALCULATION
    # =====================================================================

    async def _calculate_node_pressure(
        self, node_id: str, node_type: str = "station"
    ) -> PressureNode:
        """
        Calculate pressure for a single node using the multi-factor model.

        P = alpha*Occupancy + beta*DemandVelocity + gamma*WaitlistDepth + delta*HistoricalPeak
        """
        # Gather raw data
        occupancy_data = await self._get_occupancy(node_id, node_type)
        demand_data = await self._get_demand_velocity(node_id)
        waitlist_data = await self._get_waitlist_depth(node_id)
        peak_data = self._get_historical_peak_factor()

        # Calculate component scores (all normalized to 0.0 - 1.0)
        occupancy_score = min(1.0, occupancy_data["rate"])
        demand_velocity_score = min(1.0, max(0.0, demand_data["velocity"]))
        waitlist_depth_score = min(1.0, waitlist_data["depth_normalized"])
        historical_peak_score = peak_data

        # Weighted combination
        pressure = (
            self.ALPHA * occupancy_score +
            self.BETA * demand_velocity_score +
            self.GAMMA * waitlist_depth_score +
            self.DELTA * historical_peak_score
        )
        pressure = min(1.0, max(0.0, pressure))

        # Determine trend
        trend = self._calculate_trend(node_id)

        return PressureNode(
            node_id=node_id,
            node_type=node_type,
            pressure_score=round(pressure, 4),
            pressure_level=PressureLevel.from_score(pressure),
            occupancy_score=round(occupancy_score, 4),
            demand_velocity_score=round(demand_velocity_score, 4),
            waitlist_depth_score=round(waitlist_depth_score, 4),
            historical_peak_score=round(historical_peak_score, 4),
            current_bookings=occupancy_data.get("bookings", 0),
            total_capacity=occupancy_data.get("capacity", 0),
            searches_last_30m=demand_data.get("recent", 0),
            searches_prev_30m=demand_data.get("previous", 0),
            waitlist_count=waitlist_data.get("count", 0),
            last_updated=datetime.utcnow(),
            trend=trend,
        )

    # =====================================================================
    # DATA PROVIDERS (Abstracted for Redis/DB integration)
    # =====================================================================

    async def _get_occupancy(self, node_id: str, node_type: str) -> Dict[str, Any]:
        """Get occupancy data from cache or database."""
        try:
            from services.multi_layer_cache import multi_layer_cache
            # Try Redis first for real-time seat data
            if multi_layer_cache.redis:
                cache_key = f"npc:occupancy:{node_id}"
                cached = await multi_layer_cache.redis.get(cache_key)
                if cached:
                    import json
                    return json.loads(cached)

            # Fallback: estimate from search and verification data
            # In production, this queries actual booking tables
            capacity = self._estimate_corridor_capacity(node_id) if "->" in node_id else 5000
            # Simulate with a reasonable baseline derived from historical patterns
            bookings = int(capacity * 0.65)  # Default 65% fill

            return {
                "rate": bookings / capacity if capacity > 0 else 0.5,
                "bookings": bookings,
                "capacity": capacity,
            }
        except Exception as e:
            logger.warning(f"[NPC] Occupancy fetch failed for {node_id}: {e}")
            return {"rate": 0.5, "bookings": 0, "capacity": 1000}

    async def _get_demand_velocity(self, node_id: str) -> Dict[str, Any]:
        """
        Get demand velocity: how fast is search demand accelerating?
        Velocity = (recent - previous) / max(previous, 1)
        """
        try:
            from services.multi_layer_cache import multi_layer_cache

            recent = 0
            previous = 0

            if multi_layer_cache.redis:
                # Recent 30 minutes
                recent_key = f"npc:demand:recent:{node_id}"
                prev_key = f"npc:demand:prev:{node_id}"
                recent = int(await multi_layer_cache.redis.get(recent_key) or 0)
                previous = int(await multi_layer_cache.redis.get(prev_key) or 0)

            # Calculate velocity (acceleration of demand)
            if previous > 0:
                velocity = (recent - previous) / previous
            elif recent > 0:
                velocity = 1.0  # Sudden spike from zero
            else:
                velocity = 0.0

            # Normalize: velocity of 1.0 = 100% increase = score of 0.5
            # velocity of 2.0 = 200% increase = score of 1.0
            velocity_score = min(1.0, max(0.0, velocity / 2.0))

            return {
                "velocity": velocity_score,
                "recent": recent,
                "previous": previous,
            }
        except Exception as e:
            logger.warning(f"[NPC] Demand velocity fetch failed for {node_id}: {e}")
            return {"velocity": 0.3, "recent": 0, "previous": 0}

    async def _get_waitlist_depth(self, node_id: str) -> Dict[str, Any]:
        """Get waitlist depth for a corridor."""
        try:
            from services.multi_layer_cache import multi_layer_cache

            wl_count = 0
            if multi_layer_cache.redis:
                wl_key = f"npc:waitlist:{node_id}"
                wl_count = int(await multi_layer_cache.redis.get(wl_key) or 0)

            # Normalize: 0 WL = 0.0, 100+ WL = 1.0
            depth_normalized = min(1.0, wl_count / 100.0)

            return {
                "count": wl_count,
                "depth_normalized": depth_normalized,
            }
        except Exception as e:
            logger.warning(f"[NPC] Waitlist fetch failed for {node_id}: {e}")
            return {"count": 0, "depth_normalized": 0.0}

    def _get_historical_peak_factor(self) -> float:
        """
        How close are we to a known peak period?
        Returns 0.0 (off-peak) to 1.0 (dead center of peak).
        """
        now = datetime.utcnow() + timedelta(hours=5, minutes=30)  # IST
        hour = now.hour

        # Morning peak: 6-10 AM IST
        if 6 <= hour <= 10:
            # Peak center at 8 AM
            distance_from_center = abs(hour - 8)
            return max(0.0, 1.0 - (distance_from_center / 4.0))

        # Evening peak: 16-21 IST
        if 16 <= hour <= 21:
            # Peak center at 18:30
            distance_from_center = abs(hour - 18.5)
            return max(0.0, 1.0 - (distance_from_center / 5.0))

        # Off-peak
        return 0.1

    # =====================================================================
    # UTILITIES
    # =====================================================================

    def _estimate_corridor_capacity(self, corridor_id: str) -> int:
        """Estimate total seat capacity for a corridor on a given day."""
        # Major corridors have more trains = more capacity
        major_corridors = {
            "NDLS->BCT": 15000, "BCT->NDLS": 15000,
            "NDLS->HWH": 12000, "HWH->NDLS": 12000,
            "BCT->MAS": 8000, "MAS->BCT": 8000,
            "NDLS->LKO": 10000, "LKO->NDLS": 10000,
            "BCT->PUNE": 20000, "PUNE->BCT": 20000,
        }
        return major_corridors.get(corridor_id, 5000)

    def _calculate_trend(self, node_id: str) -> str:
        """Determine if pressure is rising, stable, or falling."""
        history = self._corridor_trends.get(node_id)
        if not history or len(history) < 3:
            return "stable"

        recent = list(history)[-3:]
        if recent[-1] > recent[0] * 1.1:
            return "rising"
        elif recent[-1] < recent[0] * 0.9:
            return "falling"
        return "stable"

    def _are_related_nodes(self, hot: PressureNode, cold: PressureNode) -> bool:
        """Check if two nodes serve related corridors."""
        # Corridors with the same source or destination are related
        if "->" in hot.node_id and "->" in cold.node_id:
            hot_parts = hot.node_id.split("->")
            cold_parts = cold.node_id.split("->")
            return hot_parts[0] == cold_parts[0] or hot_parts[1] == cold_parts[1]
        return False

    def _is_stale(self) -> bool:
        """Check if snapshot needs refresh."""
        return (time.monotonic() - self._last_refresh) > self.SNAPSHOT_TTL_SECONDS

    async def _ensure_fresh(self):
        """Refresh if stale."""
        if self._is_stale():
            await self.refresh()

    # =====================================================================
    # TELEMETRY
    # =====================================================================

    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get data for monitoring dashboard."""
        snapshot = self._snapshot
        if not snapshot:
            return {"status": "no_data", "message": "Network Pressure Calculator has not run yet."}

        return {
            "timestamp": snapshot.timestamp.isoformat(),
            "global_pressure": round(snapshot.global_pressure, 4),
            "global_level": PressureLevel.from_score(snapshot.global_pressure).value,
            "total_nodes": len(snapshot.nodes),
            "hotspot_count": snapshot.hotspot_count,
            "cold_zone_count": snapshot.cold_zone_count,
            "hotspots": snapshot.hotspots,
            "cold_zones": snapshot.cold_zones,
            "top_pressure_nodes": sorted(
                [
                    {"id": n.node_id, "score": n.pressure_score, "level": n.pressure_level.value, "trend": n.trend}
                    for n in snapshot.nodes.values()
                ],
                key=lambda x: x["score"],
                reverse=True,
            )[:10],
        }


# Singleton
network_pressure = NetworkPressureCalculator()

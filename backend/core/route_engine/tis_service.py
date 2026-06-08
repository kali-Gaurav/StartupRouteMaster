"""
🧠 Transfer Intelligence Score (TIS) — Feature C
NOVA Implementation

Computes a data-driven reliability score for every transfer connection.
Based on:
  - Historical on-time arrival rates for the incoming train at the transfer station
  - Buffer time between arrival and next departure
  - Station congestion factor at the transfer hour
  - Known connection pair success rates (learned from booking completions)

Output:
  - TIS Score: 0.0 (unreliable) to 1.0 (rock-solid)
  - Risk Label: HIGH_RISK | MODERATE_RISK | LOW_RISK | RELIABLE

Integration:
  - FrontierRoute uses TIS as an additional scoring dimension
  - SSE stream includes tis_score and tis_risk in each route event
  - HIGH_RISK routes are flagged in UI with a caution badge
"""

import asyncio
import logging
import math
import time
from typing import Optional, Dict, Tuple, Any, List
from dataclasses import dataclass
from enum import Enum
from services.cache.multi_layer import multi_layer_cache

logger = logging.getLogger("core.tis")


class TransferRiskLevel(str, Enum):
    HIGH_RISK = "HIGH_RISK"         # TIS < 0.40 — connection likely to be missed
    MODERATE_RISK = "MODERATE_RISK" # TIS 0.40–0.65 — possible with care
    LOW_RISK = "LOW_RISK"           # TIS 0.65–0.85 — comfortable connection
    RELIABLE = "RELIABLE"           # TIS > 0.85 — highly dependable


@dataclass
class TISResult:
    """Full Transfer Intelligence Score result."""
    tis_score: float                    # 0.0 → 1.0
    risk_level: TransferRiskLevel
    buffer_minutes: float               # Actual buffer between trains
    ontime_probability: float           # P(incoming train arrives on time)
    congestion_factor: float            # Station busyness at transfer hour
    connection_success_rate: float      # Historical pair success (if available)
    reasoning: str                      # Human-readable explanation


# ── In-Memory L1 Caches ───────────────────────────────────────────────────────
# These act as a very fast local buffer before hitting Redis L2.
# train_id:station_code → (on_time_rate: float, last_update: float)
_ONTIME_LOCAL: Dict[str, Tuple[float, float]] = {}

# train_id:station_code → (success_rate: float, last_update: float)
_CONNECTION_LOCAL: Dict[str, Tuple[float, float]] = {}

# station_code → (congestion_base: float)
_STATION_CONGESTION: Dict[str, float] = {
    # Mega hubs — higher congestion baseline
    "NDLS": 0.7, "NZM": 0.65, "DEE": 0.6,
    "BCT": 0.65, "LTT": 0.6, "CSTM": 0.7,
    "MAS": 0.65, "MS": 0.6,
    "HWH": 0.7, "SDAH": 0.6, "KGP": 0.55,
    "SC": 0.6, "BZA": 0.55,
    # Major hubs
    "LKO": 0.5, "CNB": 0.45, "ALD": 0.5,
    "JP": 0.5, "ADI": 0.55, "BRC": 0.45,
    "PNBE": 0.55, "MGS": 0.5, "BSB": 0.5,
}

_PEAK_HOURS = set(range(6, 11)) | set(range(16, 22))
_CACHE_TTL = 3600  # 1 hour


class TransferIntelligenceService:
    """
    Computes Transfer Intelligence Scores for route connections.

    Called per-transfer during route scoring. Uses multi-factor analysis
    with graceful fallbacks when historical data is unavailable.
    Now upgraded with Redis L2 persistence.
    """

    def __init__(self):
        self._query_count = 0
        self._cache_hit_count = 0

    async def score_transfer(
        self,
        incoming_train_id: str,
        outgoing_train_id: str,
        transfer_station_code: str,
        arr_minutes: int,      # Arrival time at transfer (minutes from midnight)
        dep_minutes: int,      # Departure time of next train (minutes from midnight)
        db=None,
    ) -> TISResult:
        """
        Compute TIS for a single transfer connection.

        Args:
            incoming_train_id: Train ID of the arriving train
            transfer_station_code: Station where transfer happens
            arr_minutes: Arrival time mod 1440 (minutes from midnight)
            dep_minutes: Departure time mod 1440 (minutes from midnight)
            db: Optional DB session for historical data lookup

        Returns:
            TISResult with score, risk level, and reasoning
        """
        self._query_count += 1
        t_start = time.perf_counter()

        # ── 1. Buffer Time ────────────────────────────────────────────────────
        buffer_mins = (dep_minutes - arr_minutes) % 1440
        # Cap buffer consideration at 4 hours (240 min) — longer is not "safer" for TIS
        effective_buffer = min(buffer_mins, 240)

        # Buffer score: logistic curve
        # 0 min buffer → 0.0, 15 min → 0.3, 30 min → 0.6, 60 min → 0.85, 120+ min → 0.95
        buffer_score = 1.0 / (1.0 + math.exp(-0.08 * (effective_buffer - 30)))

        # ── 2. On-Time Rate for Incoming Train ────────────────────────────────
        ontime_prob = await self._get_ontime_rate(incoming_train_id, transfer_station_code, db)

        # ── 3. Station Congestion ─────────────────────────────────────────────
        arrival_hour = arr_minutes // 60
        congestion = self._get_congestion(transfer_station_code, arrival_hour)

        # Congestion penalty: high congestion reduces effective buffer
        # (hard to sprint across a packed NDLS to catch train)
        congestion_penalty = congestion * 0.2  # Max 20% reduction

        # ── 4. Connection Pair Success Rate ───────────────────────────────────
        pair_success = await self._get_pair_success_rate(
            incoming_train_id, outgoing_train_id, transfer_station_code, db
        )

        # ── 5. Composite TIS Score ────────────────────────────────────────────
        # Weighted formula:
        #   Buffer:       40% — most direct predictor of success
        #   On-time rate: 35% — historical train punctuality
        #   Pair success: 15% — learned from actual bookings
        #   Congestion:  -10% — penalty for busy stations
        raw_score = (
            buffer_score * 0.40
            + ontime_prob * 0.35
            + pair_success * 0.15
            - congestion_penalty * 0.10
        )
        tis_score = max(0.0, min(1.0, raw_score))

        # ── 6. Risk Classification ────────────────────────────────────────────
        risk = self._classify_risk(tis_score)

        reasoning = (
            f"Buffer={buffer_mins}min(score={buffer_score:.2f}), "
            f"OnTime={ontime_prob:.0%}, "
            f"PairSuccess={pair_success:.0%}, "
            f"Congestion={congestion:.2f}(penalty={congestion_penalty:.2f}), "
            f"TIS={tis_score:.2f}→{risk.value}"
        )

        elapsed = (time.perf_counter() - t_start) * 1000
        logger.debug(
            f"🧠 [TIS] Train={incoming_train_id} at {transfer_station_code}: "
            f"{reasoning} | Computed in {elapsed:.1f}ms"
        )

        return TISResult(
            tis_score=round(tis_score, 3),
            risk_level=risk,
            buffer_minutes=buffer_mins,
            ontime_probability=ontime_prob,
            congestion_factor=congestion,
            connection_success_rate=pair_success,
            reasoning=reasoning,
        )

    async def score_route_transfers(
        self,
        legs: list,
        db=None,
    ) -> Tuple[float, TransferRiskLevel]:
        """
        Score all transfers in a multi-leg route.
        Returns (worst_tis_score, worst_risk_level) — weakest link principle.

        Args:
            legs: List of leg dicts with keys: train_id, to_station, arr, dep
        """
        if len(legs) <= 1:
            return 1.0, TransferRiskLevel.RELIABLE

        worst_score = 1.0
        worst_risk = TransferRiskLevel.RELIABLE

        for i in range(len(legs) - 1):
            incoming_leg = legs[i]
            outgoing_leg = legs[i + 1]

            result = await self.score_transfer(
                incoming_train_id=str(incoming_leg.get("train", "")),
                outgoing_train_id=str(outgoing_leg.get("train", "")),
                transfer_station_code=str(incoming_leg.get("to", "")),
                arr_minutes=self._parse_time_to_min(incoming_leg.get("arr", "00:00:00")),
                dep_minutes=self._parse_time_to_min(outgoing_leg.get("dep", "00:00:00")),
                db=db,
            )

            if result.tis_score < worst_score:
                worst_score = result.tis_score
                worst_risk = result.risk_level

        return worst_score, worst_risk

    async def _get_ontime_rate(self, train_id: str, station_code: str, db) -> float:
        """
        Fetch historical on-time arrival rate for a train at a station.
        Falls back to 0.72 (Indian Railways national average ~72%).
        """
        cache_key = f"tis:ontime:{train_id}:{station_code}"
        
        # 1. Local Memory L1 Check
        cached = _ONTIME_LOCAL.get(cache_key)
        if cached and (time.time() - cached[1] < 300): # 5 min local cache
            self._cache_hit_count += 1
            return cached[0]

        # 2. Redis L2 Check
        try:
            l2_val = await multi_layer_cache.get(cache_key)
            if l2_val is not None:
                self._cache_hit_count += 1
                _ONTIME_LOCAL[cache_key] = (l2_val, time.time())
                return l2_val
        except Exception as e:
            logger.debug(f"[TIS] L2 cache lookup failed: {e}")

        rate = 0.72  # national average fallback

        if db:
            try:
                from sqlalchemy import text
                # We use a wrapper to handle synchronous DB calls if needed, 
                # but assuming this is called within an async context that can handle it
                # In production, we'd use an async session
                row = db.execute(
                    text("""
                        SELECT
                            COUNT(*) AS total,
                            SUM(CASE WHEN delay_minutes <= 5 THEN 1 ELSE 0 END) AS on_time
                        FROM train_delay_log
                        WHERE train_id = :tid AND station_code = :sc
                          AND recorded_at >= NOW() - INTERVAL '90 days'
                    """),
                    {"tid": train_id, "sc": station_code},
                ).fetchone()
                if row and row[0] and row[0] > 0:
                    rate = float(row[1]) / float(row[0])
            except Exception as e:
                logger.debug(f"[TIS] DB on-time lookup failed for {train_id}: {e}")

        # 3. Update both caches
        _ONTIME_LOCAL[cache_key] = (rate, time.time())
        try:
            await multi_layer_cache.put(cache_key, rate, ttl=_CACHE_TTL)
        except: pass
        
        return rate

    def _get_congestion(self, station_code: str, arrival_hour: int) -> float:
        """
        Station congestion factor at a given hour.
        Uses static baseline with peak-hour amplification.
        """
        base = _STATION_CONGESTION.get(station_code, 0.3)
        if arrival_hour in _PEAK_HOURS:
            return min(base * 1.4, 1.0)
        return base

    async def _get_pair_success_rate(self, in_id: str, out_id: str, station_code: str, db) -> float:
        """
        Historical success rate for this specific connection pair.
        "Success" = user completed booking AND journey was not cancelled/diverted.
        Falls back to 0.80 if no data.
        """
        cache_key = f"tis:pair:{in_id}:{out_id}:{station_code}"
        
        # 1. Local Memory L1 Check
        cached = _CONNECTION_LOCAL.get(cache_key)
        if cached and (time.time() - cached[1] < 300): # 5 min local cache
            self._cache_hit_count += 1
            return cached[0]

        # 2. Redis L2 Check
        try:
            l2_val = await multi_layer_cache.get(cache_key)
            if l2_val is not None:
                self._cache_hit_count += 1
                _CONNECTION_LOCAL[cache_key] = (l2_val, time.time())
                return l2_val
        except Exception as e:
            logger.debug(f"[TIS] L2 cache lookup failed: {e}")

        rate = 0.80  # optimistic fallback

        if db:
            try:
                from sqlalchemy import text
                row = db.execute(
                    text("""
                        SELECT
                            COUNT(*) AS total,
                            SUM(CASE WHEN status = 'COMPLETED' THEN 1 ELSE 0 END) AS success
                        FROM booking_transfer_log
                        WHERE incoming_train_id = :tid AND transfer_station = :sc
                          AND created_at >= NOW() - INTERVAL '60 days'
                    """),
                    {"tid": train_id, "sc": station_code},
                ).fetchone()
                if row and row[0] and row[0] >= 5:  # Need min 5 data points
                    rate = float(row[1]) / float(row[0])
            except Exception as e:
                logger.debug(f"[TIS] DB pair success lookup failed: {e}")

        # 3. Update both caches
        _CONNECTION_LOCAL[cache_key] = (rate, time.time())
        try:
            await multi_layer_cache.put(cache_key, rate, ttl=_CACHE_TTL)
        except: pass

        return rate

    def _classify_risk(self, score: float) -> TransferRiskLevel:
        if score < 0.40:
            return TransferRiskLevel.HIGH_RISK
        elif score < 0.65:
            return TransferRiskLevel.MODERATE_RISK
        elif score < 0.85:
            return TransferRiskLevel.LOW_RISK
        else:
            return TransferRiskLevel.RELIABLE

    def _parse_time_to_min(self, time_str: str) -> int:
        """Parse HH:MM:SS or HH:MM to minutes from midnight."""
        try:
            parts = time_str.split(":")
            h, m = int(parts[0]) % 24, int(parts[1])
            return h * 60 + m
        except Exception:
            return 0

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_queries": self._query_count,
            "cache_hits": self._cache_hit_count,
            "cache_hit_rate": (
                f"{self._cache_hit_count / self._query_count:.0%}"
                if self._query_count else "N/A"
            ),
            "ontime_l1_size": len(_ONTIME_LOCAL),
            "connection_l1_size": len(_CONNECTION_LOCAL),
        }


# Singleton instance — shared across all route engine calls
tis_service = TransferIntelligenceService()

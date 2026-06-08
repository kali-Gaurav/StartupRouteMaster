"""
📊 DEMAND FORECASTER — Patent-Level Demand Prediction Engine
Predicts passenger demand per segment/train using:
  1. Booking Velocity (real-time booking rate analysis)
  2. Historical Seasonality (day-of-week, month, festival patterns)
  3. Event-Aware Surge Detection (holidays, exam seasons, festivals)
  4. Corridor Popularity Indexing (O-D pair frequency heatmaps)
  5. Capacity Utilization Forecasting (fill-rate projection curves)
"""

import logging
import math
import time
import asyncio
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from collections import defaultdict, deque
from enum import Enum

logger = logging.getLogger(__name__)


# =========================================================================
# DOMAIN MODELS
# =========================================================================

class DemandLevel(Enum):
    DEAD = "DEAD"           # <10% fill
    LOW = "LOW"             # 10-30%
    MODERATE = "MODERATE"   # 30-60%
    HIGH = "HIGH"           # 60-85%
    SURGE = "SURGE"         # 85-100%
    OVERFLOW = "OVERFLOW"   # >100% (waitlist territory)


class SeasonType(Enum):
    REGULAR = "REGULAR"
    FESTIVAL = "FESTIVAL"       # Diwali, Holi, Eid, Christmas
    EXAM = "EXAM"               # Board exams, competitive exams
    VACATION = "VACATION"       # Summer, winter breaks
    LONG_WEEKEND = "LONG_WEEKEND"
    ELECTION = "ELECTION"


@dataclass(slots=True)
class DemandSignal:
    """Single demand observation for a segment."""
    train_number: str
    from_station: str
    to_station: str
    travel_date: date
    class_code: str
    timestamp: datetime
    bookings_count: int = 0
    cancellations_count: int = 0
    waitlist_count: int = 0
    available_seats: int = 0
    total_capacity: int = 0


@dataclass(slots=True)
class DemandForecast:
    """Forecast output for a specific segment."""
    train_number: str
    from_station: str
    to_station: str
    travel_date: date
    class_code: str
    # Core predictions
    predicted_demand: float          # Expected passengers
    predicted_fill_rate: float       # 0.0 - 1.0+
    demand_level: DemandLevel
    confidence: float                # 0.0 - 1.0
    # Velocity metrics
    booking_velocity: float          # Bookings per hour (current)
    velocity_trend: str              # ACCELERATING, STABLE, DECELERATING
    # Temporal factors
    season_multiplier: float
    day_of_week_factor: float
    days_until_travel: int
    # Actionable intelligence
    surge_probability: float         # P(demand > capacity)
    recommended_action: str          # HOLD, SURGE_PRICE, REDISTRIBUTE, OVERBOOK
    alternative_trains: List[str] = field(default_factory=list)


@dataclass(slots=True)
class CorridorProfile:
    """Historical demand profile for an O-D corridor."""
    from_station: str
    to_station: str
    avg_daily_demand: float
    peak_demand: float
    dow_factors: Dict[int, float] = field(default_factory=dict)  # 0=Mon..6=Sun
    monthly_factors: Dict[int, float] = field(default_factory=dict)  # 1=Jan..12=Dec
    popular_trains: List[str] = field(default_factory=list)
    last_updated: datetime = field(default_factory=datetime.utcnow)


# =========================================================================
# BOOKING VELOCITY TRACKER
# =========================================================================

class BookingVelocityTracker:
    """
    Real-time booking rate monitor using sliding window.
    Tracks bookings per hour with 5-minute granularity.
    """
    __slots__ = ('_windows', '_window_size', '_bucket_seconds')

    def __init__(self, window_minutes: int = 60, bucket_seconds: int = 300):
        self._windows: Dict[str, deque] = defaultdict(lambda: deque(maxlen=window_minutes * 60 // bucket_seconds))
        self._window_size = window_minutes * 60
        self._bucket_seconds = bucket_seconds

    def record_booking(self, segment_key: str, count: int = 1):
        now = time.time()
        bucket = int(now // self._bucket_seconds)
        window = self._windows[segment_key]
        if window and window[-1][0] == bucket:
            window[-1] = (bucket, window[-1][1] + count)
        else:
            window.append((bucket, count))

    def get_velocity(self, segment_key: str) -> float:
        """Returns bookings per hour for the segment."""
        now = time.time()
        cutoff_bucket = int((now - self._window_size) // self._bucket_seconds)
        window = self._windows.get(segment_key)
        if not window:
            return 0.0
        total = sum(count for bucket, count in window if bucket >= cutoff_bucket)
        hours = self._window_size / 3600.0
        return total / hours if hours > 0 else 0.0

    def get_trend(self, segment_key: str) -> str:
        """Compares recent half vs older half velocity to detect acceleration."""
        window = self._windows.get(segment_key)
        if not window or len(window) < 4:
            return "STABLE"
        mid = len(window) // 2
        old_half = sum(c for _, c in list(window)[:mid])
        new_half = sum(c for _, c in list(window)[mid:])
        if new_half > old_half * 1.3:
            return "ACCELERATING"
        elif new_half < old_half * 0.7:
            return "DECELERATING"
        return "STABLE"


# =========================================================================
# SEASONALITY ENGINE
# =========================================================================

# Indian railway calendar events (month, day ranges, type, multiplier)
INDIAN_CALENDAR_EVENTS = [
    # Festivals
    (10, 15, 11, 15, SeasonType.FESTIVAL, 1.8),    # Diwali/Dussehra window
    (3, 1, 3, 31, SeasonType.FESTIVAL, 1.5),        # Holi
    (12, 20, 1, 5, SeasonType.FESTIVAL, 1.6),       # Christmas/NY
    (8, 10, 8, 20, SeasonType.FESTIVAL, 1.4),       # Independence Day + Raksha Bandhan
    (1, 10, 1, 30, SeasonType.FESTIVAL, 1.3),       # Makar Sankranti / Pongal
    # Exam seasons
    (2, 1, 3, 15, SeasonType.EXAM, 1.25),           # Board exams
    (4, 1, 4, 30, SeasonType.EXAM, 1.3),            # Competitive exams (JEE/NEET)
    # Vacations
    (5, 1, 6, 30, SeasonType.VACATION, 1.5),        # Summer vacation
    (12, 15, 1, 10, SeasonType.VACATION, 1.4),      # Winter vacation
]

# Day-of-week base factors (Indian railway patterns)
DOW_BASE_FACTORS = {
    0: 0.95,   # Monday (slightly below avg)
    1: 0.90,   # Tuesday (lowest)
    2: 0.92,   # Wednesday
    3: 1.00,   # Thursday (pickup for weekend travel)
    4: 1.25,   # Friday (weekend rush)
    5: 1.15,   # Saturday
    6: 1.10,   # Sunday (return travel)
}


class SeasonalityEngine:
    """Calculates temporal demand multipliers from calendar patterns."""

    @staticmethod
    def get_season_type(d: date) -> Tuple[SeasonType, float]:
        month, day = d.month, d.day
        best_match = (SeasonType.REGULAR, 1.0)
        for m_start, d_start, m_end, d_end, season, mult in INDIAN_CALENDAR_EVENTS:
            in_range = False
            if m_start <= m_end:
                in_range = (m_start < month < m_end) or \
                           (month == m_start and day >= d_start) or \
                           (month == m_end and day <= d_end)
            else:  # Wraps around year (Dec -> Jan)
                in_range = (month > m_start or month < m_end) or \
                           (month == m_start and day >= d_start) or \
                           (month == m_end and day <= d_end)
            if in_range and mult > best_match[1]:
                best_match = (season, mult)
        return best_match

    @staticmethod
    def get_dow_factor(d: date) -> float:
        return DOW_BASE_FACTORS.get(d.weekday(), 1.0)

    @staticmethod
    def get_advance_booking_curve(days_until: int) -> float:
        """
        Models the typical Indian railway booking curve.
        Peak bookings happen at ARP opening (120 days) and 1-7 days before travel.
        """
        if days_until <= 0:
            return 0.3   # Same-day: mostly tatkal/current
        elif days_until <= 3:
            return 1.4   # Last-minute rush
        elif days_until <= 7:
            return 1.2   # Week-before spike
        elif days_until <= 14:
            return 0.9
        elif days_until <= 30:
            return 0.7
        elif days_until <= 60:
            return 0.5
        elif days_until <= 90:
            return 0.4
        elif 118 <= days_until <= 122:
            return 1.5   # ARP opening day rush
        else:
            return 0.3


# =========================================================================
# CORRIDOR DEMAND INDEX
# =========================================================================

class CorridorDemandIndex:
    """
    Maintains historical demand profiles per O-D corridor.
    Loaded from DB, refreshed periodically.
    """
    __slots__ = ('_profiles', '_last_refresh', '_refresh_interval')

    def __init__(self, refresh_interval_seconds: int = 3600):
        self._profiles: Dict[str, CorridorProfile] = {}
        self._last_refresh = 0.0
        self._refresh_interval = refresh_interval_seconds

    async def refresh_from_db(self, db):
        """Load corridor profiles from booking history aggregates."""
        now = time.time()
        if now - self._last_refresh < self._refresh_interval:
            return
        try:
            from sqlalchemy import text
            rows = db.execute(text("""
                SELECT from_station, to_station, 
                       AVG(passenger_count) as avg_demand,
                       MAX(passenger_count) as peak_demand,
                       COUNT(*) as sample_count
                FROM booking_demand_daily
                WHERE travel_date >= CURRENT_DATE - INTERVAL '90 days'
                GROUP BY from_station, to_station
                HAVING COUNT(*) >= 5
            """)).fetchall()

            for row in rows:
                key = f"{row[0]}:{row[1]}"
                self._profiles[key] = CorridorProfile(
                    from_station=row[0], to_station=row[1],
                    avg_daily_demand=float(row[2]),
                    peak_demand=float(row[3])
                )
            self._last_refresh = now
            logger.info(f"📊 [DEMAND:INDEX] Loaded {len(self._profiles)} corridor profiles.")
        except Exception as e:
            logger.warning(f"Corridor index refresh failed: {e}")

    def get_profile(self, from_station: str, to_station: str) -> Optional[CorridorProfile]:
        return self._profiles.get(f"{from_station}:{to_station}")

    def get_corridor_popularity(self, from_station: str, to_station: str) -> float:
        """Returns a 0-1 popularity score for the corridor."""
        profile = self.get_profile(from_station, to_station)
        if not profile:
            return 0.5  # Unknown = moderate assumption
        if profile.peak_demand <= 0:
            return 0.3
        return min(1.0, profile.avg_daily_demand / profile.peak_demand)


# =========================================================================
# CAPACITY REGISTRY
# =========================================================================

# Standard Indian Railways coach capacities
COACH_CAPACITIES = {
    "1A": 18, "2A": 46, "3A": 64, "SL": 72,
    "CC": 78, "2S": 108, "FC": 18, "3E": 72,
    "EA": 18, "EC": 56,
}

# Default train compositions (coaches per class)
DEFAULT_COMPOSITIONS = {
    "rajdhani": {"1A": 1, "2A": 4, "3A": 6},
    "shatabdi": {"CC": 8, "EC": 2, "EA": 1},
    "duronto":  {"1A": 1, "2A": 3, "3A": 5, "SL": 4},
    "superfast": {"2A": 2, "3A": 4, "SL": 8, "2S": 2},
    "express":  {"2A": 1, "3A": 3, "SL": 10, "2S": 3},
    "default":  {"3A": 3, "SL": 8, "2S": 4},
}


def get_train_capacity(train_number: str, class_code: str) -> int:
    """Estimate total capacity for a train+class combination."""
    t = str(train_number)
    if t.startswith("120") or t.startswith("220"):
        comp = DEFAULT_COMPOSITIONS["rajdhani"]
    elif t.startswith("121") or t.startswith("200"):
        comp = DEFAULT_COMPOSITIONS["shatabdi"]
    elif t.startswith("122"):
        comp = DEFAULT_COMPOSITIONS["duronto"]
    elif t.startswith("12") or t.startswith("22"):
        comp = DEFAULT_COMPOSITIONS["superfast"]
    elif t.startswith("1"):
        comp = DEFAULT_COMPOSITIONS["express"]
    else:
        comp = DEFAULT_COMPOSITIONS["default"]

    coaches = comp.get(class_code, 0)
    per_coach = COACH_CAPACITIES.get(class_code, 72)
    return coaches * per_coach


# =========================================================================
# MAIN FORECASTER
# =========================================================================

class DemandForecaster:
    """
    Patent-Level Demand Prediction Engine.
    Combines real-time velocity, historical patterns, and calendar intelligence
    to produce actionable demand forecasts per segment.
    """

    def __init__(self):
        self.velocity_tracker = BookingVelocityTracker()
        self.seasonality = SeasonalityEngine()
        self.corridor_index = CorridorDemandIndex()
        self._forecast_cache: Dict[str, Tuple[DemandForecast, float]] = {}
        self._cache_ttl = 300  # 5 minutes

    # --- Public API ---

    async def forecast_segment(
        self, train_number: str, from_station: str, to_station: str,
        travel_date: date, class_code: str = "SL", db=None
    ) -> DemandForecast:
        """Generate demand forecast for a specific segment."""
        cache_key = f"{train_number}:{from_station}:{to_station}:{travel_date}:{class_code}"
        cached = self._forecast_cache.get(cache_key)
        if cached and (time.time() - cached[1]) < self._cache_ttl:
            return cached[0]

        # Refresh corridor index if needed
        if db:
            await self.corridor_index.refresh_from_db(db)

        # 1. Temporal factors
        season_type, season_mult = self.seasonality.get_season_type(travel_date)
        dow_factor = self.seasonality.get_dow_factor(travel_date)
        days_until = (travel_date - date.today()).days
        advance_factor = self.seasonality.get_advance_booking_curve(days_until)

        # 2. Corridor baseline
        corridor_pop = self.corridor_index.get_corridor_popularity(from_station, to_station)
        corridor_profile = self.corridor_index.get_profile(from_station, to_station)
        base_demand = corridor_profile.avg_daily_demand if corridor_profile else 50.0

        # 3. Real-time velocity
        seg_key = f"{train_number}:{from_station}:{to_station}:{travel_date}"
        velocity = self.velocity_tracker.get_velocity(seg_key)
        trend = self.velocity_tracker.get_trend(seg_key)

        # 4. Capacity
        capacity = get_train_capacity(train_number, class_code)
        if capacity <= 0:
            capacity = 72  # Safe default

        # 5. Composite demand prediction
        # Base prediction from historical corridor data
        predicted = base_demand * season_mult * dow_factor * advance_factor
        # Blend with velocity signal (if we have real-time data)
        if velocity > 0:
            velocity_projected = velocity * max(1, days_until) * 24
            # Weighted blend: 60% historical, 40% velocity
            predicted = (predicted * 0.6) + (velocity_projected * 0.4)

        fill_rate = predicted / capacity if capacity > 0 else 0.0

        # 6. Demand level classification
        demand_level = self._classify_demand(fill_rate)

        # 7. Surge probability (logistic curve)
        surge_prob = 1.0 / (1.0 + math.exp(-5 * (fill_rate - 0.85)))

        # 8. Confidence calculation
        confidence = self._calculate_confidence(
            has_history=corridor_profile is not None,
            has_velocity=velocity > 0,
            days_until=days_until,
            sample_size=getattr(corridor_profile, 'avg_daily_demand', 0)
        )

        # 9. Recommended action
        action = self._recommend_action(demand_level, fill_rate, surge_prob, days_until)

        forecast = DemandForecast(
            train_number=train_number, from_station=from_station,
            to_station=to_station, travel_date=travel_date,
            class_code=class_code, predicted_demand=round(predicted, 1),
            predicted_fill_rate=round(fill_rate, 3),
            demand_level=demand_level, confidence=round(confidence, 2),
            booking_velocity=round(velocity, 2), velocity_trend=trend,
            season_multiplier=round(season_mult, 2),
            day_of_week_factor=round(dow_factor, 2),
            days_until_travel=days_until,
            surge_probability=round(surge_prob, 3),
            recommended_action=action
        )

        self._forecast_cache[cache_key] = (forecast, time.time())
        return forecast

    async def forecast_route(self, route, class_code: str = "SL", db=None) -> List[DemandForecast]:
        """Forecast demand for all segments in a route."""
        forecasts = []
        for seg in route.segments:
            travel_date = seg.departure_time.date() if hasattr(seg.departure_time, 'date') else date.today()
            f = await self.forecast_segment(
                train_number=str(seg.train_number),
                from_station=getattr(seg, 'departure_code', ''),
                to_station=getattr(seg, 'arrival_code', ''),
                travel_date=travel_date,
                class_code=class_code, db=db
            )
            forecasts.append(f)
        return forecasts

    async def get_corridor_heatmap(
        self, from_station: str, to_station: str,
        start_date: date, days: int = 7, class_code: str = "SL"
    ) -> List[Dict[str, Any]]:
        """Generate a demand heatmap for the next N days on a corridor."""
        heatmap = []
        for d in range(days):
            travel_date = start_date + timedelta(days=d)
            season_type, season_mult = self.seasonality.get_season_type(travel_date)
            dow_factor = self.seasonality.get_dow_factor(travel_date)
            days_until = (travel_date - date.today()).days
            advance = self.seasonality.get_advance_booking_curve(days_until)
            composite = season_mult * dow_factor * advance
            heatmap.append({
                "date": travel_date.isoformat(),
                "day": travel_date.strftime("%A"),
                "season": season_type.value,
                "demand_index": round(composite, 2),
                "demand_level": self._classify_demand(composite * 0.6).value,
                "recommended": "BOOK_NOW" if composite > 1.3 else ("WAIT" if composite < 0.7 else "FLEXIBLE")
            })
        return heatmap

    def record_booking_event(self, train_number: str, from_station: str,
                             to_station: str, travel_date: date, count: int = 1):
        """Record a booking event for velocity tracking."""
        seg_key = f"{train_number}:{from_station}:{to_station}:{travel_date}"
        self.velocity_tracker.record_booking(seg_key, count)

    # --- Internal Methods ---

    @staticmethod
    def _classify_demand(fill_rate: float) -> DemandLevel:
        if fill_rate < 0.10: return DemandLevel.DEAD
        if fill_rate < 0.30: return DemandLevel.LOW
        if fill_rate < 0.60: return DemandLevel.MODERATE
        if fill_rate < 0.85: return DemandLevel.HIGH
        if fill_rate <= 1.00: return DemandLevel.SURGE
        return DemandLevel.OVERFLOW

    @staticmethod
    def _calculate_confidence(has_history: bool, has_velocity: bool,
                              days_until: int, sample_size: float) -> float:
        conf = 0.3  # Base
        if has_history: conf += 0.25
        if has_velocity: conf += 0.25
        if sample_size > 30: conf += 0.1
        # Confidence decays with distance from travel date
        if days_until <= 3: conf += 0.1
        elif days_until > 60: conf -= 0.15
        return max(0.1, min(1.0, conf))

    @staticmethod
    def _recommend_action(level: DemandLevel, fill_rate: float,
                          surge_prob: float, days_until: int) -> str:
        if level == DemandLevel.OVERFLOW:
            return "REDISTRIBUTE"
        if level == DemandLevel.SURGE and days_until > 3:
            return "SURGE_PRICE"
        if level == DemandLevel.SURGE and days_until <= 3:
            return "OVERBOOK"
        if level == DemandLevel.DEAD and days_until > 7:
            return "DISCOUNT"
        if level == DemandLevel.LOW:
            return "PROMOTE"
        return "HOLD"


# Singleton
demand_forecaster = DemandForecaster()

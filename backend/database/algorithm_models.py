"""
Algorithm MVP Database Models
Extends existing models.py with knowledge graph, demand redistribution, and pricing models.
Optimized for memory efficiency and API usage.
"""
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, date, timedelta
from uuid import uuid4

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Date, 
    ForeignKey, JSON, Index, Text, Enum as SQLEnum
)
from sqlalchemy.orm import relationship, Session
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON

from database.base import UserBase, Base
from database.config import Config

logger = logging.getLogger(__name__)

# Use JSONB for PostgreSQL, JSON for SQLite
if Config.DATABASE_URL and "postgresql" in Config.DATABASE_URL.lower():
    JSON_TYPE = JSONB
else:
    JSON_TYPE = SQLiteJSON


# =============================================================================
# KNOWLEDGE GRAPH MODELS
# =============================================================================

class StationKnowledge(UserBase):
    """
    Stores learned knowledge about stations for the knowledge graph.
    Optimized for quick lookups with minimal memory footprint.
    """
    __tablename__ = "station_knowledge"
    
    # Primary key - station code
    station_code = Column(String(10), primary_key=True)
    station_name = Column(String(255), nullable=False)
    region = Column(String(50), nullable=True)
    zone = Column(String(20), nullable=True)
    
    # Connectivity metrics
    connectivity_score = Column(Float, default=0.5)  # 0-1
    route_count = Column(Integer, default=0)
    daily_departures = Column(Integer, default=0)
    
    # Learned patterns (JSON for flexibility)
    peak_hours = Column(JSON_TYPE, default=list)  # [7, 8, 9, 17, 18, 19, 20]
    popular_routes = Column(JSON_TYPE, default=list)  # List of route codes
    
    # Performance metrics
    avg_delay_minutes = Column(Float, default=0.0)
    cancellation_rate = Column(Float, default=0.0)  # 0-1
    
    # Metadata
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    version = Column(Integer, default=1)
    
    __table_args__ = (
        Index('idx_station_region', 'region'),
        Index('idx_station_connectivity', 'connectivity_score'),
    )


class RouteKnowledge(UserBase):
    """
    Stores learned knowledge about routes for the knowledge graph.
    """
    __tablename__ = "route_knowledge"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    source_code = Column(String(10), ForeignKey("station_knowledge.station_code"), nullable=False)
    destination_code = Column(String(10), ForeignKey("station_knowledge.station_code"), nullable=False)
    
    # Route characteristics
    duration_minutes = Column(Integer, nullable=False)
    distance_km = Column(Float, nullable=True)
    frequency_daily = Column(Integer, default=0)
    
    # Reliability metrics
    reliability_score = Column(Float, default=0.9)  # 0-1
    avg_delay_minutes = Column(Float, default=0.0)
    on_time_percentage = Column(Float, default=85.0)
    
    # Demand patterns (stored as JSON for efficiency)
    seasonal_demand = Column(JSON_TYPE, default=dict)  # {"jan": 0.8, "feb": 0.7, ...}
    weekly_demand = Column(JSON_TYPE, default=dict)  # {"mon": 0.7, "tue": 0.6, ...}
    peak_hour_demand = Column(JSON_TYPE, default=dict)  # {"07": 0.9, "08": 0.95, ...}
    
    # Popularity metrics
    search_count = Column(Integer, default=0)
    booking_count = Column(Integer, default=0)
    conversion_rate = Column(Float, default=0.0)  # bookings/searches
    
    # Fare intelligence
    avg_fare = Column(Float, default=0.0)
    fare_range_low = Column(Float, default=0.0)
    fare_range_high = Column(Float, default=0.0)
    
    # Metadata
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_route_source_dest', 'source_code', 'destination_code'),
        Index('idx_route_popularity', 'booking_count'),
    )


class UserTravelPreference(UserBase):
    """
    Learned user preferences for personalized recommendations.
    Stored efficiently with sparse updates.
    """
    __tablename__ = "user_travel_preferences"
    
    user_id = Column(String(36), ForeignKey("users.id"), primary_key=True)
    
    # Preferred stations (ordered by frequency)
    preferred_sources = Column(JSON_TYPE, default=list)  # [{"code": "NDLS", "count": 50}]
    preferred_destinations = Column(JSON_TYPE, default=list)
    
    # Preferred routes
    preferred_routes = Column(JSON_TYPE, default=list)  # [{"source": "NDLS", "dest": "BCT", "count": 30}]
    
    # Time preferences
    preferred_departure_hours = Column(JSON_TYPE, default=list)  # [6, 7, 8, 18, 19, 20]
    preferred_travel_days = Column(JSON_TYPE, default=list)  # [5, 6] for weekends
    
    # Class preferences
    preferred_class = Column(String(5), default="SL")
    class_flexibility = Column(Float, default=0.5)  # 0=strict, 1=flexible
    
    # Booking behavior
    avg_booking_advance_days = Column(Integer, default=7)
    cancellation_rate = Column(Float, default=0.0)
    no_show_rate = Column(Float, default=0.0)
    
    # Price sensitivity (0 = not sensitive, 1 = very sensitive)
    price_sensitivity = Column(Float, default=0.5)
    
    # Pattern confidence
    preference_confidence = Column(Float, default=0.0)  # Based on interaction count
    total_interactions = Column(Integer, default=0)
    
    # Metadata
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    first_seen = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_user_preference_confidence', 'preference_confidence'),
    )


# =============================================================================
# DEMAND & PRICING MODELS
# =============================================================================

class DemandSnapshot(UserBase):
    """
    Stores periodic demand snapshots for network analysis.
    Used for demand-based redistribution and pricing.
    """
    __tablename__ = "demand_snapshots"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    
    # Route identification
    source_code = Column(String(10), nullable=False, index=True)
    destination_code = Column(String(10), nullable=False, index=True)
    travel_date = Column(Date, nullable=False, index=True)
    
    # Demand metrics
    search_count = Column(Integer, default=0)
    booking_count = Column(Integer, default=0)
    cancellation_count = Column(Integer, default=0)
    
    # Capacity info
    total_capacity = Column(Integer, default=0)
    available_seats = Column(Integer, default=0)
    
    # Calculated scores
    demand_score = Column(Float, default=0.0)  # 0-1
    occupancy_rate = Column(Float, default=0.0)  # 0-1
    
    # Price metrics
    avg_price = Column(Float, default=0.0)
    max_surge = Column(Float, default=1.0)
    
    # Metadata
    snapshot_time = Column(DateTime, default=datetime.utcnow, index=True)
    
    __table_args__ = (
        Index('idx_demand_route_date', 'source_code', 'destination_code', 'travel_date'),
        Index('idx_demand_time', 'snapshot_time'),
    )


class RedistributionOffer(UserBase):
    """
    Tracks redistribution offers sent to passengers.
    Part of Patent Innovation #1: Demand-Based Redistribution.
    """
    __tablename__ = "redistribution_offers"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    
    # Offer details
    passenger_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    original_route_id = Column(String(36), nullable=False)
    alternative_route_id = Column(String(36), nullable=False)
    
    # Offer terms
    original_price = Column(Float, nullable=False)
    alternative_price = Column(Float, nullable=False)
    incentive_amount = Column(Float, default=0.0)
    
    # Timing
    offer_sent_at = Column(DateTime, default=datetime.utcnow)
    offer_expires_at = Column(DateTime, nullable=False)
    responded_at = Column(DateTime, nullable=True)
    
    # Response
    response = Column(String(20), nullable=True)  # ACCEPTED, DECLINED, EXPIRED
    accepted_new_booking_id = Column(String(36), ForeignKey("bookings.id"), nullable=True)
    
    # Metadata
    utility_score = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_redistribution_passenger', 'passenger_id'),
        Index('idx_redistribution_status', 'response'),
    )


class PriceHistory(UserBase):
    """
    Tracks price history for fare intelligence and competitive pricing.
    """
    __tablename__ = "price_history"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    
    # Route
    source_code = Column(String(10), nullable=False, index=True)
    destination_code = Column(String(10), nullable=False, index=True)
    train_class = Column(String(5), nullable=False)
    
    # Date context
    travel_date = Column(Date, nullable=False, index=True)
    days_to_departure = Column(Integer, nullable=False)
    day_of_week = Column(Integer, nullable=False)  # 0-6
    
    # Price components
    base_fare = Column(Float, nullable=False)
    surge_multiplier = Column(Float, default=1.0)
    final_fare = Column(Float, nullable=False)
    
    # Demand context
    demand_score = Column(Float, default=0.5)
    availability_count = Column(Integer, default=0)
    
    # Metadata
    recorded_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    __table_args__ = (
        Index('idx_price_route_date', 'source_code', 'destination_code', 'travel_date'),
        Index('idx_price_time', 'recorded_at'),
    )


# =============================================================================
# PREDICTION MODELS
# =============================================================================

class DelayPrediction(UserBase):
    """
    Stores delay predictions for route optimization.
    """
    __tablename__ = "delay_predictions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    
    # Train/Route
    train_number = Column(String(20), nullable=False, index=True)
    source_code = Column(String(10), nullable=True)
    destination_code = Column(String(10), nullable=True)
    
    # Prediction context
    travel_date = Column(Date, nullable=False, index=True)
    scheduled_departure = Column(DateTime, nullable=False)
    
    # Prediction results
    predicted_delay_minutes = Column(Float, default=0.0)
    confidence_score = Column(Float, default=0.0)
    delay_category = Column(String(20), default="on_time")  # on_time, minor, major, cancelled
    
    # Actual (filled in later for training)
    actual_delay_minutes = Column(Float, nullable=True)
    prediction_error = Column(Float, nullable=True)
    
    # Metadata
    predicted_at = Column(DateTime, default=datetime.utcnow)
    model_version = Column(String(20), default="1.0")
    
    __table_args__ = (
        Index('idx_delay_train_date', 'train_number', 'travel_date'),
    )


class CancellationPrediction(UserBase):
    """
    Stores cancellation predictions for overbooking strategy.
    """
    __tablename__ = "cancellation_predictions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    
    # Booking reference
    booking_id = Column(String(36), ForeignKey("bookings.id"), nullable=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    
    # Route context
    source_code = Column(String(10), nullable=False)
    destination_code = Column(String(10), nullable=False)
    travel_date = Column(Date, nullable=False, index=True)
    
    # Prediction
    predicted_cancellation_rate = Column(Float, default=0.0)  # 0-1
    confidence_score = Column(Float, default=0.0)
    
    # Factors (JSON for flexibility)
    contributing_factors = Column(JSON_TYPE, default=dict)
    
    # Actual outcome
    was_cancelled = Column(Boolean, nullable=True)
    
    # Metadata
    predicted_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    
    __table_args__ = (
        Index('idx_cancellation_travel_date', 'travel_date'),
    )


# =============================================================================
# SEAT ALLOCATION MODELS
# =============================================================================

class SeatAllocationLog(UserBase):
    """
    Logs seat allocation decisions for optimization and auditing.
    """
    __tablename__ = "seat_allocation_logs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    
    # Booking reference
    booking_id = Column(String(36), ForeignKey("bookings.id"), nullable=False, index=True)
    passenger_id = Column(String(36), nullable=False)
    
    # Allocation details
    train_number = Column(String(20), nullable=False)
    coach_id = Column(String(10), nullable=False)
    seat_number = Column(String(10), nullable=False)
    berth_type = Column(String(10), nullable=True)  # LB, MB, UB, SL, SU
    
    # Preference matching
    preference_match_score = Column(Float, default=0.0)  # 0-1
    original_preference = Column(JSON_TYPE, default=dict)
    
    # Allocation method used
    allocation_method = Column(String(30), default="fair_distribution")  
    # fair_distribution, family_grouping, overbook, waitlist
    
    # Metadata
    allocated_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_seat_allocation_booking', 'booking_id'),
        Index('idx_seat_allocation_train', 'train_number'),
    )


# =============================================================================
# ANALYTICS & METRICS
# =============================================================================

class AlgorithmPerformanceMetric(UserBase):
    """
    Tracks algorithm performance for continuous improvement.
    """
    __tablename__ = "algorithm_performance_metrics"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    
    # Algorithm identification
    algorithm_name = Column(String(50), nullable=False, index=True)
    algorithm_version = Column(String(20), default="1.0")
    
    # Request context
    request_type = Column(String(30), nullable=False)  # search, booking, pricing, etc.
    
    # Performance metrics
    execution_time_ms = Column(Float, nullable=False)
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)
    
    # Result metrics
    results_count = Column(Integer, default=0)
    cache_hit = Column(Boolean, default=False)
    
    # Resource usage
    memory_used_mb = Column(Float, nullable=True)
    api_calls_made = Column(Integer, default=0)
    
    # Metadata
    recorded_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    __table_args__ = (
        Index('idx_algorithm_perf_name', 'algorithm_name', 'recorded_at'),
    )


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def update_station_knowledge(db: Session, station_code: str, **kwargs):
    """Update or create station knowledge entry."""
    station = db.query(StationKnowledge).filter(
        StationKnowledge.station_code == station_code
    ).first()
    
    if station:
        for key, value in kwargs.items():
            if hasattr(station, key):
                setattr(station, key, value)
        station.last_updated = datetime.utcnow()
    else:
        station = StationKnowledge(
            station_code=station_code,
            station_name=kwargs.get('station_name', station_code),
            **{k: v for k, v in kwargs.items() if k != 'station_name'}
        )
        db.add(station)
    
    db.commit()
    return station


def record_demand_snapshot(db: Session, source: str, dest: str, 
                           travel_date: date, **metrics):
    """Record a demand snapshot for analysis."""
    snapshot = DemandSnapshot(
        source_code=source,
        destination_code=dest,
        travel_date=travel_date,
        **metrics
    )
    db.add(snapshot)
    db.commit()
    return snapshot


def get_user_preference(db: Session, user_id: str) -> Optional[UserTravelPreference]:
    """Get or create user travel preference."""
    pref = db.query(UserTravelPreference).filter(
        UserTravelPreference.user_id == user_id
    ).first()
    
    if not pref:
        pref = UserTravelPreference(user_id=user_id)
        db.add(pref)
        db.commit()
    
    return pref


def update_user_preference_from_booking(db: Session, user_id: str, booking_data: dict):
    """Update user preferences based on booking behavior."""
    pref = get_user_preference(db, user_id)
    if not pref:
        return
    
    # Update interaction count
    pref.total_interactions += 1
    
    # Update source preferences
    source = booking_data.get('source_code')
    if source:
        sources = pref.preferred_sources or []
        found = False
        for s in sources:
            if s.get('code') == source:
                s['count'] = s.get('count', 0) + 1
                found = True
                break
        if not found:
            sources.append({'code': source, 'count': 1})
        # Keep top 10
        sources.sort(key=lambda x: x.get('count', 0), reverse=True)
        pref.preferred_sources = sources[:10]
    
    # Update destination preferences
    dest = booking_data.get('destination_code')
    if dest:
        dests = pref.preferred_destinations or []
        found = False
        for d in dests:
            if d.get('code') == dest:
                d['count'] = d.get('count', 0) + 1
                found = True
                break
        if not found:
            dests.append({'code': dest, 'count': 1})
        dests.sort(key=lambda x: x.get('count', 0), reverse=True)
        pref.preferred_destinations = dests[:10]
    
    # Update booking advance
    travel_date = booking_data.get('travel_date')
    if travel_date and booking_data.get('created_at'):
        days_advance = (travel_date - booking_data['created_at'].date()).days
        # Exponential moving average
        pref.avg_booking_advance_days = int(
            0.9 * pref.avg_booking_advance_days + 0.1 * days_advance
        )
    
    # Update confidence
    pref.preference_confidence = min(1.0, pref.total_interactions / 50)
    pref.last_updated = datetime.utcnow()
    
    db.commit()
    return pref
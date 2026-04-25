"""
Sync Service Database Models

Models for:
- Search events tracking
- Recommendation events
- Precalculated routes
- Station realtime heartbeats
"""

from database.base import UserBase, TransitBase
from sqlalchemy import Column, String, Integer, Float, DateTime, Date, Time, Text, JSON, Boolean, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid


class SearchEvent(UserBase):
    """
    Tracks user search events for analytics and hot zone detection.
    """
    __tablename__ = "search_events"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    session_id = Column(String(100), nullable=True, index=True)
    
    # Search parameters
    src = Column(String(20), nullable=False, index=True)
    dest = Column(String(20), nullable=False, index=True)
    travel_date = Column(Date, nullable=False, index=True)
    
    # Search context
    device_type = Column(String(50), nullable=True)  # mobile, desktop, tablet
    platform = Column(String(50), nullable=True)  # web, ios, android
    user_agent = Column(Text, nullable=True)
    
    # Results
    routes_found = Column(Integer, default=0)
    filters_applied = Column(JSON, nullable=True)
    
    # Timestamps
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    response_time_ms = Column(Integer, nullable=True)
    
    # Location (optional)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)


class RecommendationEvent(UserBase):
    """
    Tracks recommendation events and user responses.
    """
    __tablename__ = "recommendation_events"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    session_id = Column(String(100), nullable=True, index=True)
    
    # Recommendation context
    recommendation_type = Column(String(50), nullable=False)  # route, price, timing, etc.
    source_route = Column(String(20), nullable=True)
    destination_route = Column(String(20), nullable=True)
    
    # Recommendation details
    recommended_item = Column(JSON, nullable=True)  # The actual recommendation
    confidence_score = Column(Float, default=0.0)
    reasoning = Column(Text, nullable=True)  # Why this was recommended
    
    # User response
    was_clicked = Column(Boolean, default=False, index=True)
    was_booked = Column(Boolean, default=False, index=True)
    was_dismissed = Column(Boolean, default=False)
    
    # Timestamps
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    clicked_at = Column(DateTime, nullable=True)
    booked_at = Column(DateTime, nullable=True)


class PrecalculatedRoute(UserBase):
    """
    Stores precalculated routes for fast retrieval.
    """
    __tablename__ = "precalculated_routes"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Route parameters
    src = Column(String(20), nullable=False, index=True)
    dest = Column(String(20), nullable=False, index=True)
    travel_date = Column(Date, nullable=False, index=True)
    
    # Route details
    route_data = Column(JSON, nullable=False)  # Full route information
    total_duration_minutes = Column(Integer, nullable=True)
    total_distance_km = Column(Float, nullable=True)
    number_of_transfers = Column(Integer, default=0)
    
    # Quality metrics
    reliability_score = Column(Float, default=0.9)
    popularity_score = Column(Float, default=0.5)
    
    # Metadata
    calculated_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    last_accessed_at = Column(DateTime, nullable=True)
    access_count = Column(Integer, default=0)
    
    __table_args__ = (
        Index('ix_precalc_route_lookup', 'src', 'dest', 'travel_date'),
    )


class StationRealtimeHeartbeat(UserBase):
    """
    Stores real-time station status for hot zone detection.
    """
    __tablename__ = "station_realtime_heartbeats"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    station_code = Column(String(20), nullable=False, unique=True, index=True)
    
    # Status summary
    status_summary = Column(String(255), nullable=True)
    trains_json = Column(JSON, nullable=True)  # List of trains at station
    
    # Performance metrics
    sync_latency_ms = Column(Integer, nullable=True)
    last_updated_at = Column(DateTime, default=datetime.utcnow, index=True)
    last_updated_unix = Column(Integer, nullable=True)
    
    # Data integrity
    sync_hash = Column(String(64), nullable=True)  # SHA256 hash of data
    station_mode = Column(String(20), default="RAIL")  # RAIL, BUS, etc.
    
    # Expiration
    expires_at = Column(DateTime, nullable=True)
    
    # Additional data
    total_delayed = Column(Integer, default=0)
    total_cancelled = Column(Integer, default=0)
    data_source = Column(String(100), nullable=True)


class HotZoneThreshold(UserBase):
    """
    Configurable thresholds for hot zone detection.
    """
    __tablename__ = "hot_zone_thresholds"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Threshold configuration
    zone_type = Column(String(50), nullable=False)  # primary_hub, influencer, corridor
    station_code = Column(String(20), nullable=True)  # NULL for global thresholds
    
    # Time-based thresholds
    search_count_threshold = Column(Integer, default=100)
    time_window_minutes = Column(Integer, default=60)
    
    # TTL configuration
    hub_ttl_minutes = Column(Integer, default=2)
    influencer_ttl_minutes = Column(Integer, default=10)
    
    # Status
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SyncAuditLog(UserBase):
    """
    Audit log for sync operations.
    """
    __tablename__ = "sync_audit_logs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Operation details
    operation_type = Column(String(50), nullable=False)  # heartbeat, drift_analysis, etc.
    entity_type = Column(String(50), nullable=True)  # station, route, etc.
    entity_id = Column(String(100), nullable=True)
    
    # Operation results
    success = Column(Boolean, default=False)
    error_message = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    
    # Data snapshot
    data_before = Column(JSON, nullable=True)
    data_after = Column(JSON, nullable=True)
    
    # Metadata
    performed_by = Column(String(50), default="SYSTEM")
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
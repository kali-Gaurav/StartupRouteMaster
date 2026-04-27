"""
Knowledge Graph Database Models

Models for persisting knowledge graph data including:
- User preferences
- Route patterns
- Seasonal patterns
- Competitor prices
- User behavior matrix
"""

from database.base import UserBase, TransitBase
from sqlalchemy import Column, String, Integer, Float, DateTime, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid


class UserPreferenceModel(UserBase):
    """
    Stores learned user preferences for the knowledge graph.
    """
    __tablename__ = "knowledge_user_preferences"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), unique=True, nullable=False, index=True)
    
    # Travel preferences
    preferred_class = Column(String(10), default="SL")
    preferred_time_morning = Column(Integer, default=0)  # 0 = no preference, 1 = morning, 2 = evening
    class_flexibility = Column(Float, default=0.5)  # 0 = strict, 1 = flexible
    price_sensitivity = Column(Float, default=0.5)  # 0 = not sensitive, 1 = very sensitive
    
    # Learned patterns
    preferred_stations = Column(Text, default="")  # Comma-separated
    preferred_routes = Column(Text, default="")  # Comma-separated (e.g., "NDLS->BCT,MAS->HWH")
    preferred_times = Column(Text, default="")  # Comma-separated hours (e.g., "6,12,18")
    preferred_days = Column(Text, default="")  # Comma-separated days (0-6)
    
    # Booking behavior
    avg_booking_advance_days = Column(Integer, default=7)
    cancellation_rate = Column(Float, default=0.1)
    avg_trip_duration_hours = Column(Float, default=0.0)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    interaction_count = Column(Integer, default=0)
    
    def to_preference_dict(self):
        """Convert to dictionary for knowledge graph."""
        return {
            "user_id": self.user_id,
            "preferred_class": self.preferred_class,
            "preferred_time_morning": self.preferred_time_morning,
            "class_flexibility": self.class_flexibility,
            "price_sensitivity": self.price_sensitivity,
            "preferred_stations": self.preferred_stations.split(",") if self.preferred_stations else [],
            "preferred_routes": self.preferred_routes.split(",") if self.preferred_routes else [],
            "preferred_times": [int(t) for t in self.preferred_times.split(",")] if self.preferred_times else [],
            "preferred_days": [int(d) for d in self.preferred_days.split(",")] if self.preferred_days else [],
            "avg_booking_advance_days": self.avg_booking_advance_days,
            "cancellation_rate": self.cancellation_rate,
            "avg_trip_duration_hours": self.avg_trip_duration_hours
        }


class RoutePatternModel(UserBase):
    """
    Stores learned route patterns and statistics.
    """
    __tablename__ = "knowledge_route_patterns"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source = Column(String(20), nullable=False, index=True)
    destination = Column(String(20), nullable=False, index=True)
    
    # Popularity metrics
    searches = Column(Integer, default=0)
    bookings = Column(Integer, default=0)
    cancellations = Column(Integer, default=0)
    
    # Performance metrics
    success_rate = Column(Float, default=0.85)  # Booking success rate
    avg_booking_value = Column(Float, default=0.0)
    avg_booking_advance_days = Column(Float, default=0.0)
    
    # Time patterns
    peak_hours = Column(Text, default="")  # Comma-separated peak hours
    peak_days = Column(Text, default="")  # Comma-separated peak days (0-6)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @property
    def conversion_rate(self):
        """Calculate search to booking conversion rate."""
        return self.bookings / self.searches if self.searches > 0 else 0
    
    @property
    def route_key(self):
        """Get route key."""
        return f"{self.source}->{self.destination}"


class SeasonalPatternModel(UserBase):
    """
    Stores seasonal demand patterns for routes.
    """
    __tablename__ = "knowledge_seasonal_patterns"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source = Column(String(20), nullable=False, index=True)
    destination = Column(String(20), nullable=False, index=True)
    
    # Month (1-12)
    month = Column(Integer, nullable=False)
    
    # Demand metrics
    demand_score = Column(Float, default=0.5)  # 0-1 scale
    avg_price = Column(Float, default=0.0)
    availability_rate = Column(Float, default=1.0)  # Seat availability rate
    
    # Patterns
    demand_level = Column(String(20), default="medium")  # low, medium, high
    trend = Column(String(20), default="stable")  # increasing, stable, decreasing
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        # Unique constraint for source-destination-month
        {'sqlite_autoincrement': True},
    )


class CompetitorPriceModel(UserBase):
    """
    Stores competitor pricing information.
    """
    __tablename__ = "knowledge_competitor_prices"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source = Column(String(20), nullable=False, index=True)
    destination = Column(String(20), nullable=False, index=True)
    
    # Provider info
    provider_name = Column(String(100), nullable=False)  # e.g., "IRCTC", "MakeMyTrip", "RailYatri"
    provider_type = Column(String(50), default="aggregator")  # "official", "aggregator", "otc"
    
    # Price info
    price = Column(Float, nullable=False)
    currency = Column(String(3), default="INR")
    
    # Additional info
    service_class = Column(String(10), nullable=True)  # e.g., "SL", "2A", "3A"
    departure_time = Column(String(10), nullable=True)  # e.g., "06:00"
    journey_duration_minutes = Column(Integer, nullable=True)
    
    # Metadata
    collected_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)  # Price validity expiration
    url = Column(String(1024), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @property
    def route_key(self):
        """Get route key."""
        return f"{self.source}->{self.destination}"


class UserBehaviorModel(UserBase):
    """
    Stores user behavior data for collaborative filtering.
    """
    __tablename__ = "knowledge_user_behaviors"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=False, index=True)
    
    # Interaction type
    interaction_type = Column(String(50), nullable=False)  # "search", "booking", "view", "click"
    
    # Route info
    source = Column(String(20), nullable=False)
    destination = Column(String(20), nullable=False)
    
    # Score (implicit feedback strength)
    score = Column(Float, default=1.0)
    
    # Context
    device_type = Column(String(50), nullable=True)
    platform = Column(String(50), nullable=True)  # "web", "ios", "android"
    
    # Timestamps
    interaction_timestamp = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    @property
    def route_key(self):
        """Get route key."""
        return f"{self.source}->{self.destination}"


class StationPatternModel(UserBase):
    """
    Stores learned station patterns and characteristics.
    """
    __tablename__ = "knowledge_station_patterns"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    station_code = Column(String(20), unique=True, nullable=False, index=True)
    station_name = Column(String(255), nullable=True)
    
    # Location
    region = Column(String(100), nullable=True)
    zone = Column(String(50), nullable=True)
    city = Column(String(100), nullable=True)
    
    # Connectivity
    connectivity_score = Column(Float, default=0.5)
    route_count = Column(Integer, default=0)
    hub_score = Column(Float, default=0.0)  # How much of a hub this station is
    
    # Performance metrics
    avg_delay_minutes = Column(Float, default=0.0)
    cancellation_rate = Column(Float, default=0.0)
    on_time_rate = Column(Float, default=0.9)
    
    # Popular times
    peak_hours = Column(Text, default="")  # Comma-separated
    busy_days = Column(Text, default="")  # Comma-separated (0-6)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# KnowledgeGraphSnapshot is already defined in models.py
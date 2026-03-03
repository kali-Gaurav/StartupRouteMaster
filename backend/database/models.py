from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Boolean, ForeignKey, JSON, Text, 
    LargeBinary, CheckConstraint, UniqueConstraint, Date, Index, Time, Enum as SQLEnum
)
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from .session import UserBase, TransitBase

# ==============================================================================
# ENUMS
# ==============================================================================

class QuotaType(enum.Enum):
    GENERAL = "general"
    TATKAL = "tatkal"
    LADIES = "ladies"
    SENIOR_CITIZEN = "senior_citizen"
    DEFENCE = "defence"
    FOREIGN_TOURIST = "foreign_tourist"

class BookingStatus(enum.Enum):
    CONFIRMED = "confirmed"
    RAC = "rac"
    WAITLIST = "waitlist"
    CANCELLED = "cancelled"
    PENDING = "pending"

class CoachClass(enum.Enum):
    SL = "sl"
    AC3 = "ac3"
    AC2 = "ac2"
    AC1 = "ac1"
    CC = "cc"
    EC = "ec"

# ==============================================================================
# USER STORE MODELS (user_store.db) - Inherit from UserBase
# ==============================================================================

class User(UserBase):
    __tablename__ = "users"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=True, index=True)
    supabase_id = Column(String(255), unique=True, nullable=True, index=True)
    phone_number = Column(String(20), nullable=True)
    role = Column(String(50), default="user")
    created_at = Column(DateTime, default=datetime.utcnow)

    bookings = relationship("Booking", back_populates="user")
    profile = relationship("Profile", back_populates="user", uselist=False)
    reviews = relationship("Review", back_populates="user")

class Profile(UserBase):
    __tablename__ = "profiles"
    id = Column(String(255), primary_key=True) # Matches Supabase ID
    user_id = Column(String(36), ForeignKey("users.id"))
    name = Column(String(255), nullable=True)
    avatar_url = Column(String(1024), nullable=True)
    ai_memory = Column(JSON, default={}, nullable=False)
    user = relationship("User", back_populates="profile")

class Booking(UserBase):
    __tablename__ = "bookings"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    pnr_number = Column(String(10), unique=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id"))
    travel_date = Column(Date, index=True)
    booking_status = Column(String(50), default="pending")
    amount_paid = Column(Float, default=0.0)
    booking_details = Column(JSON, nullable=False)
    
    # We remove the physical FK to transit_graph.db since they are in different files.
    # We will use 'loose' IDs (logical FKs) for cross-db relations.
    route_id = Column(String(36), nullable=True)
    trip_id = Column(Integer, nullable=True)

    user = relationship("User", back_populates="bookings")

class Review(UserBase):
    __tablename__ = "reviews"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"))
    booking_id = Column(String(36), ForeignKey("bookings.id"))
    rating = Column(Integer, nullable=False)
    comment = Column(Text, nullable=True)
    user = relationship("User", back_populates="reviews")

class RouteSearchLog(UserBase):
    __tablename__ = "route_search_logs"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    src = Column(String(255), nullable=False)
    dst = Column(String(255), nullable=False)
    date = Column(Date, nullable=False)
    latency_ms = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="route_search_logs")

# ==============================================================================
# TRANSIT GRAPH MODELS (transit_graph.db) - Inherit from TransitBase
# ==============================================================================

class Agency(TransitBase):
    __tablename__ = "agency"
    id = Column(Integer, primary_key=True)
    agency_id = Column(String(100), unique=True, index=True)
    name = Column(String(255), nullable=False)
    timezone = Column(String(50), default="Asia/Kolkata")

class Stop(TransitBase):
    __tablename__ = "stops"
    id = Column(Integer, primary_key=True)
    stop_id = Column(String(100), unique=True, index=True)
    code = Column(String(100), index=True)
    name = Column(String(255), nullable=False, index=True)
    city = Column(String(255), index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    platform_count = Column(Integer, nullable=True)

class Route(TransitBase):
    __tablename__ = "gtfs_routes"
    id = Column(Integer, primary_key=True)
    route_id = Column(String(100), unique=True, index=True)
    short_name = Column(String(50))
    long_name = Column(String(255), nullable=False)
    route_type = Column(Integer, default=2)

class Calendar(TransitBase):
    __tablename__ = "calendar"
    id = Column(Integer, primary_key=True)
    service_id = Column(String(100), unique=True, index=True)
    monday = Column(Boolean, default=True)
    tuesday = Column(Boolean, default=True)
    wednesday = Column(Boolean, default=True)
    thursday = Column(Boolean, default=True)
    friday = Column(Boolean, default=True)
    saturday = Column(Boolean, default=True)
    sunday = Column(Boolean, default=True)
    start_date = Column(Date)
    end_date = Column(Date)

class CalendarDate(TransitBase):
    __tablename__ = "calendar_dates"
    id = Column(Integer, primary_key=True)
    service_id = Column(String(100), index=True)
    date = Column(Date, index=True)
    exception_type = Column(Integer)

class Trip(TransitBase):
    __tablename__ = "trips"
    id = Column(Integer, primary_key=True)
    trip_id = Column(String(255), unique=True, index=True)
    route_id = Column(Integer, ForeignKey("gtfs_routes.id"))
    service_id = Column(String(100), ForeignKey("calendar.service_id"))

class StopTime(TransitBase):
    __tablename__ = "stop_times"
    id = Column(Integer, primary_key=True)
    trip_id = Column(Integer, ForeignKey("trips.id"))
    stop_id = Column(Integer, ForeignKey("stops.id"))
    arrival_time = Column(Time, nullable=False)
    departure_time = Column(Time, nullable=False)
    stop_sequence = Column(Integer, nullable=False)

class Segment(TransitBase):
    __tablename__ = "segments"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_station_id = Column(Integer, ForeignKey("stops.id"))
    dest_station_id = Column(Integer, ForeignKey("stops.id"))
    trip_id = Column(Integer, ForeignKey("trips.id"))
    transport_mode = Column(String(50), default="train")
    departure_time = Column(Time)
    arrival_time = Column(Time)
    duration_minutes = Column(Integer)
    distance_km = Column(Float)
    cost = Column(Float)

class Transfer(TransitBase):
    __tablename__ = "transfers"
    id = Column(Integer, primary_key=True)
    from_stop_id = Column(Integer, ForeignKey("stops.id"))
    to_stop_id = Column(Integer, ForeignKey("stops.id"))
    min_transfer_time = Column(Integer, default=15)

class StationRank(TransitBase):
    __tablename__ = "station_rank"
    id = Column(Integer, primary_key=True)
    station_id = Column(Integer, ForeignKey("stops.id"), unique=True)
    connectivity_score = Column(Float, default=0.0)
    hub_type = Column(String(50), default="regular")

class StationHealthIndex(TransitBase):
    __tablename__ = "station_health_index"
    id = Column(Integer, primary_key=True)
    station_id = Column(Integer, ForeignKey("stops.id"))
    date = Column(Date)
    dep_count = Column(Integer, default=0)
    health_score = Column(Float, default=100.0)

class StationTransitIndex(TransitBase):
    __tablename__ = "station_transit_index"
    station_code = Column(String(20), primary_key=True)
    station_name = Column(String(255))
    trains_map = Column(Text)

class StationSchedule(TransitBase):
    __tablename__ = "station_schedule"
    station_id = Column(Integer, ForeignKey("stops.id"), primary_key=True)
    trip_id = Column(Integer, ForeignKey("trips.id"), primary_key=True)
    arrival = Column(Time)
    departure = Column(Time)
    day_of_week = Column(String(9), primary_key=True)
    stop_seq = Column(Integer, primary_key=True)

class TrainPath(TransitBase):
    __tablename__ = "train_path"
    trip_id = Column(Integer, ForeignKey("trips.id"), primary_key=True)
    station_id = Column(Integer, ForeignKey("stops.id"), nullable=False)
    arrival = Column(Time)
    departure = Column(Time)
    stop_seq = Column(Integer, primary_key=True)
    day_of_week = Column(String(9), primary_key=True)

class ETLMetadata(TransitBase):
    __tablename__ = "etl_metadata"
    id = Column(Integer, primary_key=True)
    run_id = Column(String(50), unique=True)
    status = Column(String(20))
    trips_synced = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow)

class ZeroRouteDiagnostic(TransitBase):
    __tablename__ = "zero_route_diagnostics"
    id = Column(Integer, primary_key=True)
    source_station = Column(String(20))
    dest_station = Column(String(20))
    search_date = Column(Date)
    source_departures = Column(Integer, default=0)
    dest_arrivals = Column(Integer, default=0)
    intersecting_trips = Column(Integer, default=0)

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
# USER STORE MODELS (user_store.db)
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
    commission_tracks = relationship("CommissionTracking", back_populates="user")
    unlocked_routes = relationship("UnlockedRoute", back_populates="user")
    subscription = relationship("Subscription", back_populates="user", uselist=False)

class Profile(UserBase):
    __tablename__ = "profiles"
    id = Column(String(255), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id"))
    name = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
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
    
    # Suggestion #19: Compact Binary Storage for large details
    booking_details_blob = Column(LargeBinary, nullable=True)
    
    route_id = Column(String(36), nullable=True)
    trip_id = Column(Integer, nullable=True)

    user = relationship("User", back_populates="bookings")
    passenger_details = relationship("PassengerDetails", back_populates="booking")

class PassengerDetails(UserBase):
    __tablename__ = "passenger_details"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    booking_id = Column(String(36), ForeignKey("bookings.id"))
    full_name = Column(String(255), nullable=False)
    age = Column(Integer, nullable=False)
    gender = Column(String(10), nullable=False)
    booking = relationship("Booking", back_populates="passenger_details")

class Payment(UserBase):
    __tablename__ = "payments"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    booking_id = Column(String(36), ForeignKey("bookings.id"), nullable=True)
    status = Column(String(50), default="CREATED")
    amount = Column(Float, nullable=False)

class Subscription(UserBase):
    __tablename__ = "subscriptions"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"))
    is_pro = Column(Boolean, default=False)
    user = relationship("User", back_populates="subscription")

class UnlockedRoute(UserBase):
    __tablename__ = "unlocked_routes"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"))
    payment_id = Column(String(36), ForeignKey("payments.id"), nullable=True)
    user = relationship("User", back_populates="unlocked_routes")

class Review(UserBase):
    __tablename__ = "reviews"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"))
    booking_id = Column(String(36), ForeignKey("bookings.id"))
    rating = Column(Integer, nullable=False)
    comment = Column(Text, nullable=True)
    user = relationship("User", back_populates="reviews")

class CommissionTracking(UserBase):
    __tablename__ = "commission_tracking"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey('users.id'))
    tracking_id = Column(String(64), unique=True, index=True)
    user = relationship("User", back_populates="commission_tracks")

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
# TRANSIT GRAPH MODELS (transit_graph.db)
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
    state = Column(String(255))
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    platform_count = Column(Integer, nullable=True)
    
    stop_times = relationship("StopTime", back_populates="stop")
    facilities = relationship("StationFacilities", back_populates="stop", uselist=False)

class Route(TransitBase):
    __tablename__ = "gtfs_routes"
    id = Column(Integer, primary_key=True)
    route_id = Column(String(100), unique=True, nullable=False, index=True)
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

class Trip(TransitBase):
    __tablename__ = "trips"
    id = Column(Integer, primary_key=True)
    trip_id = Column(String(255), unique=True, index=True)
    route_id = Column(Integer, ForeignKey("gtfs_routes.id"))
    service_id = Column(String(100), ForeignKey("calendar.service_id"))
    stop_times = relationship("StopTime", back_populates="trip")

class StopTime(TransitBase):
    __tablename__ = "stop_times"
    id = Column(Integer, primary_key=True)
    trip_id = Column(Integer, ForeignKey("trips.id"))
    stop_id = Column(Integer, ForeignKey("stops.id"))
    arrival_time = Column(Time, nullable=False)
    departure_time = Column(Time, nullable=False)
    stop_sequence = Column(Integer, nullable=False)
    trip = relationship("Trip", back_populates="stop_times")
    stop = relationship("Stop", back_populates="stop_times")

class StationFacilities(TransitBase):
    __tablename__ = "station_facilities"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    stop_id = Column(Integer, ForeignKey("stops.id"), unique=True)
    stop = relationship("Stop", back_populates="facilities")

class TrainMaster(TransitBase):
    __tablename__ = "trains_master"
    train_number = Column(String(50), primary_key=True)
    train_name = Column(String(255))

class TrainState(TransitBase):
    __tablename__ = "train_states"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    trip_id = Column(Integer, index=True)
    train_number = Column(String(50), index=True)
    status = Column(String(20), default="on_time")
    delay_minutes = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.utcnow)

class ETLMetadata(TransitBase):
    __tablename__ = "etl_metadata"
    id = Column(Integer, primary_key=True)
    run_id = Column(String(50), unique=True)
    status = Column(String(20))
    trips_synced = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow)
    source_version = Column(String(50), nullable=True)

class StationRank(TransitBase):
    __tablename__ = "station_rank"
    id = Column(Integer, primary_key=True)
    station_id = Column(Integer, ForeignKey("stops.id"), unique=True)
    connectivity_score = Column(Float, default=0.0)
    hub_type = Column(String(50), default="regular")

class StationTransitIndex(TransitBase):
    __tablename__ = "station_transit_index"
    station_code = Column(String(20), primary_key=True)
    station_name = Column(String(255))
    trains_map = Column(Text)

class RealtimeData(TransitBase):
    __tablename__ = "realtime_data"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_type = Column(String(50))
    entity_type = Column(String(50))
    entity_id = Column(String(100))
    data = Column(JSON)
    timestamp = Column(DateTime)
    source = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)

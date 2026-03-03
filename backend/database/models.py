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
    disruptions_created = relationship("Disruption", back_populates="creator")

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
    booking_details = Column(JSON, nullable=False)
    route_id = Column(String(36), nullable=True)
    trip_id = Column(Integer, nullable=True)

    user = relationship("User", back_populates="bookings")
    payment = relationship("Payment", back_populates="booking", uselist=False)
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
    booking = relationship("Booking", back_populates="payment")
    unlocked_route = relationship("UnlockedRoute", back_populates="payment")

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
    payment = relationship("Payment", back_populates="unlocked_route")

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

class WebhookEvent(UserBase):
    __tablename__ = "webhook_events"
    id = Column(String(100), primary_key=True)
    event_type = Column(String(100))
    processed_at = Column(DateTime, default=datetime.utcnow)

class RLFeedbackLog(UserBase):
    __tablename__ = "rl_feedback_logs"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"))
    session_id = Column(String(36))
    action = Column(String(100))
    context = Column(JSON)
    reward = Column(Float)
    timestamp = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

class Disruption(UserBase):
    __tablename__ = "disruptions"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    disruption_type = Column(String(50))
    created_by_id = Column(String(36), ForeignKey('users.id'))
    creator = relationship("User", back_populates="disruptions_created")

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
    stop_times = relationship("StopTime", back_populates="trip")
    coaches = relationship("Coach", back_populates="train")

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
    inventory = relationship("SeatInventory", back_populates="stop_time", uselist=False)

class Coach(TransitBase):
    __tablename__ = "coaches"
    id = Column(Integer, primary_key=True)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=False)
    coach_number = Column(String(10), nullable=False)
    class_type = Column(String(50), nullable=False)
    train = relationship("Trip", back_populates="coaches")
    seats = relationship("Seat", back_populates="coach")

class Seat(TransitBase):
    __tablename__ = "seats"
    id = Column(Integer, primary_key=True)
    coach_id = Column(Integer, ForeignKey("coaches.id"), nullable=False)
    seat_number = Column(String(10), nullable=False)
    is_available = Column(Boolean, default=True)
    coach = relationship("Coach", back_populates="seats")

class SeatInventory(TransitBase):
    __tablename__ = "seat_inventory"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    travel_date = Column(Date, index=True)
    stop_time_id = Column(Integer, ForeignKey('stop_times.id'))
    stop_time = relationship("StopTime", back_populates="inventory")

class Fare(TransitBase):
    __tablename__ = "fares"
    id = Column(Integer, primary_key=True)
    segment_id = Column(String(36), index=True)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=True)
    class_type = Column(String(50), nullable=False)
    amount = Column(Float, nullable=False)

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
    source_version = Column(String(50), nullable=True) # Added

class ZeroRouteDiagnostic(TransitBase):
    __tablename__ = "zero_route_diagnostics"
    id = Column(Integer, primary_key=True)
    source_station = Column(String(20))
    dest_station = Column(String(20))
    search_date = Column(Date)
    source_departures = Column(Integer, default=0)
    dest_arrivals = Column(Integer, default=0)
    intersecting_trips = Column(Integer, default=0)

class StationFacilities(TransitBase):
    __tablename__ = "station_facilities"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    stop_id = Column(Integer, ForeignKey("stops.id"), unique=True)
    stop = relationship("Stop", back_populates="facilities")

class TrainLiveUpdate(TransitBase):
    __tablename__ = "train_live_updates"
    id = Column(Integer, primary_key=True, autoincrement=True)
    train_number = Column(String(50), index=True)
    station_code = Column(String(100), index=True)
    recorded_at = Column(DateTime, default=datetime.utcnow, index=True)
    delay_minutes = Column(Integer, default=0)

class StationTrainHistory(TransitBase):
    __tablename__ = "station_train_history"
    id = Column(Integer, primary_key=True)
    station_id = Column(Integer, ForeignKey('stops.id'), nullable=False)
    trip_id = Column(Integer, ForeignKey('trips.id'), nullable=False)
    date = Column(Date, nullable=False)
    delay_minutes = Column(Integer, default=0)
    is_cancelled = Column(Boolean, default=False)

class TrainStation(TransitBase):
    __tablename__ = "train_stations"
    id = Column(Integer, primary_key=True, autoincrement=True)
    train_number = Column(String(50), ForeignKey("trains_master.train_number"))
    sequence = Column(Integer)

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

class Vehicle(TransitBase):
    __tablename__ = "vehicles"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    vehicle_number = Column(String(50))
    type = Column(String(50))
    operator = Column(String(255))

class StationHealthIndex(TransitBase):
    __tablename__ = "station_health_index"
    id = Column(Integer, primary_key=True)
    station_id = Column(Integer, ForeignKey("stops.id"))
    date = Column(Date)
    dep_count = Column(Integer, default=0)
    health_score = Column(Float, default=100.0)

class SnapshotDiffLog(TransitBase):
    __tablename__ = "snapshot_diff_log"
    id = Column(Integer, primary_key=True)
    date = Column(Date)
    trains_added = Column(Integer, default=0)
    trains_removed = Column(Integer, default=0)
    time_changes = Column(Integer, default=0)

class TrainAvailabilityCache(TransitBase):
    __tablename__ = "train_availability_cache"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    train_number = Column(String(20), index=True)
    journey_date = Column(Date, index=True)

class SeatAvailability(TransitBase):
    __tablename__ = "seat_availability"
    id = Column(Integer, primary_key=True, autoincrement=True)
    train_number = Column(String(50), index=True)
    travel_date = Column(DateTime, index=True)
    availability_status = Column(String(100))

class PrecalculatedRoute(TransitBase):
    __tablename__ = "precalculated_routes"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source = Column(String(255), nullable=False)
    destination = Column(String(255), nullable=False)

from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    DateTime,
    Boolean,
    ForeignKey,
    JSON,
    Text,
    LargeBinary,
    CheckConstraint,
    UniqueConstraint,
    Date,
    Index,
    Time,
) 
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from geoalchemy2 import Geometry, func
import enum

from .session import Base


# ==============================================================================
# ENUMS AND CONSTANTS
# ==============================================================================

class QuotaType(enum.Enum):
    """Seat quota types (IRCTC standard)"""
    GENERAL = "general"
    TATKAL = "tatkal"
    LADIES = "ladies"
    SENIOR_CITIZEN = "senior_citizen"
    DEFENCE = "defence"
    FOREIGN_TOURIST = "foreign_tourist"

class BookingStatus(enum.Enum):
    """Booking status"""
    CONFIRMED = "confirmed"
    RAC = "rac"
    WAITLIST = "waitlist"
    CANCELLED = "cancelled"
    PENDING = "pending"

class SeatType(enum.Enum):
    """Seat types"""
    LOWER = "lower"
    MIDDLE = "middle"
    UPPER = "upper"
    SIDE_LOWER = "side_lower"
    SIDE_UPPER = "side_upper"
    WINDOW = "window"
    AISLE = "aisle"

class CoachClass(enum.Enum):
    """Coach classes"""
    SL = "sl"
    AC3 = "ac3"
    AC2 = "ac2"
    AC1 = "ac1"
    CC = "cc"
    EC = "ec"

# ==============================================================================
# CORE USER AND UTILITY MODELS (Largely Unchanged)
# ==============================================================================

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    phone_number = Column(String(20), nullable=True)
    role = Column(String(50), default="user", index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    bookings = relationship("Booking", back_populates="user")
    reviews = relationship("Review", back_populates="user")
    unlocked_routes = relationship("UnlockedRoute", back_populates="user")
    commission_tracks = relationship("CommissionTracking", back_populates="user")
    disruptions_created = relationship("Disruption", back_populates="creator")
    route_search_logs = relationship("RouteSearchLog", back_populates="user")

# ==============================================================================
# NEW GTFS-INSPIRED TRANSIT MODELS
# ==============================================================================

class Agency(Base):
    """Represents a transit agency or operator."""
    __tablename__ = "agency"

    id = Column(Integer, primary_key=True)
    agency_id = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    url = Column(String(255), nullable=False)
    timezone = Column(String(50), nullable=False)
    # Optional language code (GTFS 'agency_lang')
    language = Column(String(10), nullable=True)

    routes = relationship("Route", back_populates="agency")

class Stop(Base):
    """Consolidated and enhanced model for all stops/stations."""
    __tablename__ = "stops"
    __table_args__ = (
        Index("idx_stops_geom", "geom", postgresql_using="gist"),
        Index("idx_stops_name_trgm", "name", postgresql_ops={"name": "gin_trgm_ops"}, postgresql_using="gin"),
    )

    id = Column(Integer, primary_key=True)
    stop_id = Column(String(100), unique=True, nullable=False, index=True) # Public-facing ID
    code = Column(String(100), index=True) # e.g., platform code
    name = Column(String(255), nullable=False, index=True)
    city = Column(String(255), index=True)
    state = Column(String(255))
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    geom = Column(String, nullable=True)  # Changed from Geometry for SQLite compatibility
    
    location_type = Column(Integer, default=0) # 0 for stop, 1 for station
    parent_station_id = Column(Integer, ForeignKey("stops.id"), nullable=True)
    
    # NEW FIELDS FOR ADVANCED FEATURES
    safety_score = Column(Float, default=50.0, nullable=False)  # 0-100 scale, default neutral
    is_major_junction = Column(Boolean, default=False, nullable=False)  # Major transfer point
    facilities_json = Column(JSON, default={}, nullable=False)  # {wifi: bool, lounge: bool, food: bool, accessible: bool, etc.}
    wheelchair_accessible = Column(Boolean, default=False, nullable=False)
    platform_count = Column(Integer, nullable=True)
    distance_to_city_center_km = Column(Float, nullable=True)  # For travel time estimation

    parent_station = relationship("Stop", remote_side=[id])
    child_stops = relationship("Stop", back_populates="parent_station")
    stop_times = relationship("StopTime", back_populates="stop")
    facilities = relationship("StationFacilities", back_populates="stop", uselist=False)
    departure_buckets = relationship("StopDepartureBucket", back_populates="stop", cascade="all, delete-orphan")

class Route(Base):
    """Represents a single transit route in the GTFS sense (e.g., 'Blue Line')."""
    __tablename__ = "gtfs_routes"

    id = Column(Integer, primary_key=True)
    route_id = Column(String(100), unique=True, nullable=False, index=True)
    agency_id = Column(Integer, ForeignKey("agency.id"), nullable=False, index=True)
    short_name = Column(String(50))
    long_name = Column(String(255), nullable=False)
    # Optional descriptive fields used by tests and UI
    description = Column(String(512), nullable=True)
    url = Column(String(255), nullable=True)
    route_type = Column(Integer, nullable=False, index=True) # 0: Tram, 1: Subway, 2: Rail, 3: Bus

    agency = relationship("Agency", back_populates="routes")
    trips = relationship("Trip", back_populates="route")

class Calendar(Base):
    """Defines service patterns for routes (e.g., weekday service)."""
    __tablename__ = "calendar"

    id = Column(Integer, primary_key=True)
    service_id = Column(String(100), unique=True, nullable=False, index=True)  # FIXED: make this unique for FK reference
    monday = Column(Boolean, nullable=False)
    tuesday = Column(Boolean, nullable=False)
    wednesday = Column(Boolean, nullable=False)
    thursday = Column(Boolean, nullable=False)
    friday = Column(Boolean, nullable=False)
    saturday = Column(Boolean, nullable=False)
    sunday = Column(Boolean, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)

    trips = relationship("Trip", back_populates="service")

class CalendarDate(Base):
    """Defines exceptions to the service patterns in Calendar."""
    __tablename__ = "calendar_dates"
    __table_args__ = (
        UniqueConstraint('service_id', 'date', name='uq_service_date'),
    )
    id = Column(Integer, primary_key=True)
    service_id = Column(String(100), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    exception_type = Column(Integer, nullable=False) # 1 for added, 2 for removed

class Trip(Base):
    """A single journey along a route at a specific time."""
    __tablename__ = "trips"

    id = Column(Integer, primary_key=True)
    trip_id = Column(String(255), unique=True, nullable=False, index=True)
    route_id = Column(Integer, ForeignKey("gtfs_routes.id"), nullable=False, index=True)
    service_id = Column(String(100), ForeignKey("calendar.service_id"), nullable=False, index=True)  # FIXED: string FK
    headsign = Column(String(255))
    direction_id = Column(Integer, index=True)
    
    # NEW FIELDS FOR ACCESSIBILITY & AMENITIES
    bike_allowed = Column(Boolean, default=False, nullable=False)
    wheelchair_accessible = Column(Boolean, default=False, nullable=False)
    trip_headsign = Column(String(255), nullable=True)  # Alternative destination name shown to passengers

    route = relationship("Route", back_populates="trips")
    service = relationship("Calendar", back_populates="trips")
    stop_times = relationship("StopTime", back_populates="trip", cascade="all, delete-orphan")
    coaches = relationship("Coach", back_populates="train", cascade="all, delete-orphan")
    # Back-reference for legacy/denormalized segments (kept for compatibility / ETL checks)
    segments = relationship("Segment", back_populates="trip")
    
class StopTime(Base):
    """The arrival and departure of a trip at a specific stop."""
    __tablename__ = "stop_times"
    __table_args__ = (
        UniqueConstraint('trip_id', 'stop_sequence', name='uq_trip_stop_sequence'),
        Index("idx_stop_times_stop_id", "stop_id"),
        Index("idx_stop_times_trip_id", "trip_id"),
        CheckConstraint("arrival_time <= departure_time", name="arrival_before_departure"),
    )

    id = Column(Integer, primary_key=True)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=False)
    stop_id = Column(Integer, ForeignKey("stops.id"), nullable=False)
    arrival_time = Column(Time, nullable=False)
    departure_time = Column(Time, nullable=False)
    stop_sequence = Column(Integer, nullable=False)
    cost = Column(Float, nullable=False, default=0.0)  # Cost from previous stop (required for fare calculation)
    
    # NEW FIELDS FOR BOARDING RULES
    pickup_type = Column(Integer, default=0, nullable=False)  # 0: Regular, 1: No pickup, 2: Phone arrange, 3: Coordinate with driver
    drop_off_type = Column(Integer, default=0, nullable=False)  # 0: Regular, 1: No dropoff, 2: Phone arrange, 3: Coordinate with driver
    
    # Platform info
    platform_number = Column(String(10), nullable=True)
    
    trip = relationship("Trip", back_populates="stop_times")
    stop = relationship("Stop", back_populates="stop_times")
    inventory = relationship("SeatInventory", back_populates="stop_time", uselist=False)

class Coach(Base):
    """Coach details for each train."""
    __tablename__ = "coaches"
    id = Column(Integer, primary_key=True)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=False)
    coach_number = Column(String(10), nullable=False)
    class_type = Column(String(50), nullable=False, default="AC_2")
    total_seats = Column(Integer, default=48)
    
    train = relationship("Trip", back_populates="coaches")
    seats = relationship("Seat", back_populates="coach", cascade="all, delete-orphan")

class Seat(Base):
    """Individual seat within a coach."""
    __tablename__ = "seats"
    id = Column(Integer, primary_key=True)
    coach_id = Column(Integer, ForeignKey("coaches.id"), nullable=False)
    seat_number = Column(String(10), nullable=False)
    is_available = Column(Boolean, default=True)
    
    coach = relationship("Coach", back_populates="seats")

class Fare(Base):
    """Fare information for segments."""
    __tablename__ = "fares"
    id = Column(Integer, primary_key=True)
    segment_id = Column(Integer, index=True) # Linked to segment logic
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=True)
    class_type = Column(String(50), nullable=False) # AC_1, AC_2, SL, etc.
    amount = Column(Float, nullable=False)

class Transfer(Base):
    """Defines transfer rules between stops."""
    __tablename__ = "transfers"
    __table_args__ = (
        UniqueConstraint("from_stop_id", "to_stop_id", "route_id", name="uq_transfer_route"),
    )

    id = Column(Integer, primary_key=True)
    from_stop_id = Column(Integer, ForeignKey("stops.id"), nullable=False)
    to_stop_id = Column(Integer, ForeignKey("stops.id"), nullable=False)
    route_id = Column(Integer, ForeignKey("gtfs_routes.id"), nullable=True)  # NEW: Optional specific route
    transfer_type = Column(Integer, nullable=False, default=0) # 0: Recommended, 1: Timed, 2: Minimum required
    min_transfer_time = Column(Integer, nullable=False) # In seconds
    walking_time_minutes = Column(Integer, default=5, nullable=False) # Additional field for Phase 4

    from_stop = relationship("Stop", foreign_keys=[from_stop_id])
    to_stop = relationship("Stop", foreign_keys=[to_stop_id])
    route = relationship("Route")

# ==============================================================================
# MODELS REQUIRING ADAPTATION
# ==============================================================================

class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        Index("idx_bookings_pnr", "pnr_number"),
        Index("idx_bookings_user_travel", "user_id", "travel_date"),
        Index("idx_bookings_status", "booking_status"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    pnr_number = Column(String(10), unique=True, nullable=False, index=True)  # NEW: 6-10 digit PNR
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    travel_date = Column(Date, nullable=False, index=True)
    
    # Booking Status (NEW: enum-like validation)
    booking_status = Column(String(50), default="pending", nullable=False, index=True)
    # Valid states: pending, confirmed, waiting_list, cancelled (no lowercase 'payment_status')
    
    amount_paid = Column(Float, default=0.0, nullable=False)
    booking_details = Column(JSON, nullable=False)  # Store segments JSON
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Deprecated fields (for backward compatibility only, will be removed)
    route_id = Column(String(36), ForeignKey("precalculated_routes.id"), nullable=True)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=True)
    payment_status = Column(String(50), nullable=True)  # DEPRECATED: use payment relationship instead

    user = relationship("User", back_populates="bookings")
    payment = relationship("Payment", back_populates="booking", uselist=False)
    review = relationship("Review", back_populates="booking", uselist=False)
    passenger_details = relationship("PassengerDetails", back_populates="booking", cascade="all, delete-orphan")
    route = relationship("PrecalculatedRoute", back_populates="bookings")
    trip = relationship("Trip")

    def validate_status_transition(self, new_status: str) -> bool:
        """Validate state machine transitions."""
        valid_transitions = {
            "pending": ["confirmed", "waiting_list", "cancelled"],
            "confirmed": ["cancelled"],
            "waiting_list": ["confirmed", "cancelled"],
            "cancelled": []
        }
        return new_status in valid_transitions.get(self.booking_status, [])


class PassengerDetails(Base):
    """NEW: Stores passenger details for a booking (required for train tickets)."""
    __tablename__ = "passenger_details"
    __table_args__ = (
        Index("idx_passenger_booking", "booking_id"),
        {"extend_existing": True}
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    booking_id = Column(String(36), ForeignKey("bookings.id"), nullable=False, index=True)
    
    # Passenger info
    full_name = Column(String(255), nullable=False)
    age = Column(Integer, nullable=False)
    gender = Column(String(10), nullable=False)  # M, F, O (Other)
    phone_number = Column(String(20), nullable=True)
    email = Column(String(255), nullable=True)
    
    # Identity document
    document_type = Column(String(50), nullable=True)  # Aadhar, PAN, Passport, etc.
    document_number = Column(String(50), nullable=True)
    
    # Seat assignment
    coach_number = Column(String(10), nullable=True)
    seat_number = Column(String(10), nullable=True)
    berth_type = Column(String(20), nullable=True)  # Upper, Middle, Lower, Side, Center
    
    # Concessions
    concession_type = Column(String(50), nullable=True)  # Defence, StudentDiscount, SeniorCitizen, etc.
    concession_discount = Column(Float, default=0.0, nullable=False)
    
    # Meal preferences
    meal_preference = Column(String(20), nullable=True)  # Veg, NonVeg, Jain
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    booking = relationship("Booking", back_populates="passenger_details")

class UnlockedRoute(Base):
    __tablename__ = "unlocked_routes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    payment_id = Column(String(36), ForeignKey("payments.id"), nullable=True, index=True)
    unlocked_at = Column(DateTime, default=datetime.utcnow)
    
    # --- Deprecated / Transitional Fields ---
    route_id = Column(String(36), ForeignKey("precalculated_routes.id"), nullable=True, index=True)

    user = relationship("User", back_populates="unlocked_routes")
    payment = relationship("Payment", back_populates="unlocked_route", uselist=False)
    route = relationship("PrecalculatedRoute") # Points to deprecated table

class Disruption(Base):
    __tablename__ = "disruptions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    disruption_type = Column(String(50), nullable=False) # delay, cancellation, diversion
    description = Column(Text, nullable=True)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    status = Column(String(50), default="active", index=True) # active, resolved
    created_by_id = Column(String(36), ForeignKey('users.id'), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # --- New fields to link disruption to the GTFS model ---
    gtfs_route_id = Column(Integer, ForeignKey('gtfs_routes.id'), nullable=True, index=True)
    trip_id = Column(Integer, ForeignKey('trips.id'), nullable=True, index=True)
    stop_id = Column(Integer, ForeignKey('stops.id'), nullable=True, index=True)

    creator = relationship("User", back_populates="disruptions_created")
    gtfs_route = relationship("Route")
    trip = relationship("Trip")
    stop = relationship("Stop")

class SeatInventory(Base):
    __tablename__ = 'seat_inventory'
    __table_args__ = {'extend_existing': True}
    # Unique constraint needs to be updated
    # __table_args__ = (
    #     UniqueConstraint('segment_id', 'travel_date', name='uq_segment_travel_date'),
    # )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    travel_date = Column(Date, nullable=False, index=True)
    coach_type = Column(String(50), nullable=True, index=True) # NEW: Coach type (AC_1, AC_2, etc)
    seats_available = Column(Integer, nullable=False)
    last_reconciled_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # --- Updated Foreign Key ---
    stop_time_id = Column(Integer, ForeignKey('stop_times.id'), nullable=False, index=True)
    
    stop_time = relationship("StopTime", back_populates="inventory")

class CommissionTracking(Base):
    __tablename__ = "commission_tracking"
    # ... (rest of the fields are mostly ok, but route_id needs to be handled)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey('users.id'), nullable=False, index=True)
    source = Column(String(255), nullable=False)
    destination = Column(String(255), nullable=False)
    travel_date = Column(Date, nullable=True)
    partner = Column(String(100), nullable=False, index=True)
    commission_rate = Column(Float, nullable=False)
    tracking_id = Column(String(64), nullable=False, unique=True, index=True)
    redirect_url = Column(Text, nullable=False)
    status = Column(String(50), default="redirected", index=True)
    redirected_at = Column(DateTime, default=datetime.utcnow, index=True)
    # ... other fields
    
    # --- Deprecated / Transitional Field ---
    route_id = Column(String(36), nullable=True)  # Was never a FK, just a reference

    user = relationship("User", back_populates="commission_tracks")


# ==============================================================================
# UNCHANGED SUPPORTING MODELS (Review, Payment)
# ==============================================================================

class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        CheckConstraint("rating >= 1 AND rating <= 5", name="review_rating_check"),
        UniqueConstraint('user_id', 'booking_id', name='uq_user_booking_review'),
    )
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    booking_id = Column(String(36), ForeignKey("bookings.id"), unique=True, nullable=False, index=True)
    rating = Column(Integer, nullable=False)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="reviews")
    booking = relationship("Booking", back_populates="review")

class Payment(Base):
    __tablename__ = "payments"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    booking_id = Column(String(36), ForeignKey("bookings.id"), nullable=True, index=True)
    razorpay_order_id = Column(String(255), nullable=True, index=True)
    razorpay_payment_id = Column(String(255), nullable=True, index=True)
    status = Column(String(50), default="pending")
    amount = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    booking = relationship("Booking", back_populates="payment")
    unlocked_route = relationship("UnlockedRoute", back_populates="payment")


# ==============================================================================
# NEW TABLES FOR ADVANCED FEATURES
# ==============================================================================

class RealtimeData(Base):
    """For dynamic updates like train locations, delays, cancellations."""
    __tablename__ = "realtime_data"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_type = Column(String(50), nullable=False, index=True)  # e.g., 'delay', 'cancellation', 'location_update'
    entity_type = Column(String(50), nullable=False)  # e.g., 'trip', 'stop', 'route'
    entity_id = Column(String(100), nullable=False, index=True)  # ID of the affected entity
    data = Column(JSON, nullable=False)  # Flexible JSON for event-specific data
    timestamp = Column(DateTime, nullable=False, index=True)
    source = Column(String(100), nullable=False)  # e.g., 'api', 'web_scraper', 'iot_sensor'
    created_at = Column(DateTime, default=datetime.utcnow)

class RLFeedbackLog(Base):
    """Logs for Reinforcement Learning feedback."""
    __tablename__ = "rl_feedback_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    session_id = Column(String(36), nullable=False, index=True)
    action = Column(String(100), nullable=False)  # e.g., 'route_selected', 'booking_completed'
    context = Column(JSON, nullable=False)  # User context, search params, etc.
    reward = Column(Float, nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")


# ==============================================================================
# NEW MISSING MODELS (ESSENTIAL FOR ADVANCED FEATURES)
# ==============================================================================

class RouteShape(Base):
    """NEW: Defines the actual track geometry/path for a route."""
    __tablename__ = "route_shapes"
    __table_args__ = (
        Index("idx_route_shapes_route", "route_id"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    route_id = Column(Integer, ForeignKey("gtfs_routes.id"), nullable=False, index=True)
    shape_id = Column(String(100), nullable=False, unique=True)
    
    # Geometry path (line string)
    geometry = Column(String, nullable=True)  # Changed from Geometry for SQLite compatibility
    
    # Sequence for multiple segments
    sequence = Column(Integer, default=0, nullable=False)
    distance_traveled = Column(Float, nullable=False)  # Cumulative distance from start
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    route = relationship("Route")


class Frequency(Base):
    """NEW: For routes that don't have fixed schedules (high-frequency service)."""
    __tablename__ = "frequencies"
    __table_args__ = (
        UniqueConstraint("trip_id", "start_time", name="uq_trip_start_time"),
        Index("idx_frequencies_trip", "trip_id"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=False, index=True)
    
    start_time = Column(Time, nullable=False)  # Service starts at this time
    end_time = Column(Time, nullable=False)    # Service ends at this time
    headway_secs = Column(Integer, nullable=False)  # Seconds between departures
    exact_times = Column(Boolean, default=False)  # If False, times are approximate
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    trip = relationship("Trip")


class StationFacilities(Base):
    """NEW: Detailed facilities available at each station."""
    __tablename__ = "station_facilities"
    __table_args__ = (
        Index("idx_station_facilities_stop", "stop_id"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    stop_id = Column(Integer, ForeignKey("stops.id"), nullable=False, unique=True, index=True)
    
    # Facilities
    wifi_available = Column(Boolean, default=False)
    lounge_available = Column(Boolean, default=False)
    food_available = Column(Boolean, default=False)
    wheelchair_accessible = Column(Boolean, default=False)
    parking_available = Column(Boolean, default=False)
    baby_care = Column(Boolean, default=False)
    medical_clinic = Column(Boolean, default=False)
    lost_found = Column(Boolean, default=False)
    cloakroom = Column(Boolean, default=False)
    
    # Operating hours
    opening_time = Column(Time, nullable=True)
    closing_time = Column(Time, nullable=True)
    
    # Safety & security
    cctv_available = Column(Boolean, default=False)
    police_presence = Column(Boolean, default=False)
    women_waiting_room = Column(Boolean, default=False)
    
    # Contact
    emergency_contact = Column(String(20), nullable=True)
    contact_email = Column(String(255), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    stop = relationship("Stop", back_populates="facilities")


# ==============================================================================
# NEW MODELS FOR BOOKING WORKFLOW
# ==============================================================================

class CancellationRule(Base):
    """NEW: Defines cancellation charges for different routes/timeframes."""
    __tablename__ = "cancellation_rules"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    route_id = Column(Integer, ForeignKey("gtfs_routes.id"), nullable=True)  # NULL = apply to all routes
    
    # Hours before departure
    hours_before_departure = Column(Integer, nullable=False)  # e.g., 48 hours
    
    # Refund percentage
    refund_percentage = Column(Float, nullable=False)  # 0.0 to 100.0
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    route = relationship("Route")


class WaitingListRequest(Base):
    """NEW: Waiting list management when route is fully booked."""
    __tablename__ = "waiting_list"
    __table_args__ = (
        Index("idx_waiting_list_booking", "booking_id"),
        Index("idx_waiting_list_status", "status"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    booking_id = Column(String(36), ForeignKey("bookings.id"), nullable=False, unique=True)
    
    # Waiting list position (lower = higher priority)
    position = Column(Integer, nullable=False)
    
    # Status
    status = Column(String(50), default="waiting", nullable=False)  # waiting, confirmed, expired, cancelled
    
    # Notification
    notification_sent = Column(Boolean, default=False)
    confirmed_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    booking = relationship("Booking")


# ==============================================================================
# DEPRECATED MODELS (To be removed after migration)
# ==============================================================================

class PrecalculatedRoute(Base):
    """DEPRECATED: This table stores pre-calculated routes and is architecturally flawed."""
    __tablename__ = "precalculated_routes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source = Column(String(255), nullable=False, index=True)
    destination = Column(String(255), nullable=False, index=True)
    segments = Column(JSON, nullable=False)
    total_duration = Column(String(50), nullable=False)
    total_cost = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    bookings = relationship("Booking", back_populates="route")


# Note: The original 'routes' table was renamed to 'precalculated_routes' to make its purpose clear.
# The following models are now obsolete due to the new GTFS structure.

class Vehicle(Base):
    __tablename__ = "vehicles"
    __table_args__ = (
        CheckConstraint("type IN ('train', 'bus', 'flight')", name="vehicle_type_check"),
    )
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    vehicle_number = Column(String(50), nullable=False)
    type = Column(String(50), nullable=False)
    operator = Column(String(255), nullable=False)
    capacity = Column(Integer, nullable=True)
    segments = relationship("Segment", back_populates="vehicle")

class Station(Base):
    __tablename__ = "stations"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False, index=True)
    city = Column(String(255), nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    geom = Column(String, nullable=True)  # Changed from Geometry for SQLite compatibility
    created_at = Column(DateTime, default=datetime.utcnow)
    segments_from = relationship("Segment", foreign_keys="Segment.source_station_id", back_populates="source_station")
    segments_to = relationship("Segment", foreign_keys="Segment.dest_station_id", back_populates="dest_station")
    departure_buckets = relationship("StationDepartureBucket", back_populates="station", cascade="all, delete-orphan")

class Segment(Base):
    __tablename__ = "segments"
    __table_args__ = (
        Index("idx_segments_src_dest_dep", "source_station_id", "dest_station_id", "departure_time"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_station_id = Column(String(36), ForeignKey("stations.id"), nullable=False, index=True)
    dest_station_id = Column(String(36), ForeignKey("stations.id"), nullable=False, index=True)
    vehicle_id = Column(String(36), ForeignKey("vehicles.id"), nullable=True, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=True, index=True)

    transport_mode = Column(String(50), nullable=False)
    departure_time = Column(Time, nullable=False)
    arrival_time = Column(Time, nullable=False)
    arrival_day_offset = Column(Integer, nullable=True)

    duration_minutes = Column(Integer, nullable=False)
    distance_km = Column(Float, nullable=True)
    cost = Column(Float, nullable=False)
    operating_days = Column(String(7), nullable=False, default="1111111")

    source_station = relationship("Station", foreign_keys=[source_station_id], back_populates="segments_from")
    dest_station = relationship("Station", foreign_keys=[dest_station_id], back_populates="segments_to")
    vehicle = relationship("Vehicle", back_populates="segments")
    trip = relationship("Trip", back_populates="segments", lazy='joined')
    # SeatInventory now references `stop_time_id`; remove direct Segment->SeatInventory relationship to avoid FK mismatch in tests

class StationDeparture(Base):
    """
    Optimized station-centric departure table (Phase 1).
    Explicitly stores departures for fast lookup without complex joins.
    """
    __tablename__ = "station_departures_indexed"
    __table_args__ = (
        Index("idx_station_dep_time", "station_id", "departure_time"),
        Index("idx_station_dep_day", "station_id", "operating_days"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    station_id = Column(Integer, ForeignKey("stops.id"), nullable=False, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=False, index=True)
    departure_time = Column(Time, nullable=False, index=True)
    arrival_time_at_next = Column(Time, nullable=True)
    next_station_id = Column(Integer, ForeignKey("stops.id"), nullable=True)
    operating_days = Column(String(7), nullable=False, default="1111111") # MTWTFSS
    train_number = Column(String(50), nullable=True)
    distance_to_next = Column(Float, nullable=True)

    station = relationship("Stop", foreign_keys=[station_id])
    next_station = relationship("Stop", foreign_keys=[next_station_id])
    trip = relationship("Trip")


class TimeIndexKey(Base):
    """Maps entity (trip/vehicle/segment) -> integer key used inside time-index bitsets."""
    __tablename__ = "time_index_keys"
    __table_args__ = (
        UniqueConstraint('entity_type', 'entity_id', name='uq_time_index_key'),
        Index("idx_time_index_entity", "entity_type", "entity_id"),
    )

    id = Column(Integer, primary_key=True)
    entity_type = Column(String(50), nullable=False, index=True)  # 'trip' | 'vehicle' | 'segment'
    entity_id = Column(String(255), nullable=False, index=True)   # actual id (trip.id or vehicle.uuid)


class StationDepartureBucket(Base):
    """Station-centric time buckets containing a compact bitset of available trips/vehicles.

    - bucket_start_minute: minutes since midnight floored to bucket interval (e.g. 08:00 -> 480)
    - bitmap: serialized Roaring bitmap (stored as BYTEA/LargeBinary)
    """
    __tablename__ = "station_departures"
    __table_args__ = (
        UniqueConstraint('station_id', 'bucket_start_minute', name='uq_station_bucket'),
        Index("idx_station_departures_station_bucket", "station_id", "bucket_start_minute"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    station_id = Column(String(36), ForeignKey("stations.id"), nullable=False, index=True)
    bucket_start_minute = Column(Integer, nullable=False, index=True)
    bitmap = Column(LargeBinary, nullable=False, default=b"")
    trips_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    station = relationship("Station", back_populates="departure_buckets")


class StopDepartureBucket(Base):
    """Stop-centric time buckets keyed by GTFS `stops.id` (integer).

    This is the lookup table the route engine will use for memory-backed
    earliest-departure queries.
    """
    __tablename__ = "stop_departures"
    __table_args__ = (
        UniqueConstraint('stop_id', 'bucket_start_minute', name='uq_stop_bucket'),
        Index("idx_stop_departures_stop_bucket", "stop_id", "bucket_start_minute"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    stop_id = Column(Integer, ForeignKey("stops.id"), nullable=False, index=True)
    bucket_start_minute = Column(Integer, nullable=False, index=True)
    bitmap = Column(LargeBinary, nullable=False, default=b"")
    trips_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    stop = relationship("Stop", back_populates="departure_buckets")


class StationMaster(Base):
    __tablename__ = "stations_master"
    station_code = Column(String(10), primary_key=True)
    station_name = Column(String(255), nullable=False, index=True)
    city = Column(String(255), nullable=True, index=True)
    state = Column(String(255), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    is_junction = Column(Boolean, default=False)
    # keep a minimal legacy model used by seed scripts and older APIs

# ==============================================================================
# ML AND INTELLIGENCE MODELS
# ==============================================================================

class RouteSearchLog(Base):
    """Logs route searches for ML training and analytics."""
    __tablename__ = "route_search_logs"
    __table_args__ = (
        Index("idx_route_search_logs_user_id", "user_id"),
        Index("idx_route_search_logs_src_dst", "src", "dst"),
        Index("idx_route_search_logs_date", "date"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)  # Nullable for anonymous searches
    src = Column(String(255), nullable=False)
    dst = Column(String(255), nullable=False)
    date = Column(Date, nullable=False)
    routes_shown = Column(JSON, nullable=False)  # List of route summaries shown to user
    route_clicked = Column(String(36), nullable=True)  # ID of the route clicked (if any)
    booking_success = Column(Boolean, nullable=True)  # Whether a booking was completed
    latency_ms = Column(Float, nullable=False)  # Search latency in milliseconds
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="route_search_logs")  # Assuming we add this to User model

# ==============================================================================
# REAL-TIME GRAPH MUTATION MODELS
# ==============================================================================

class TrainState(Base):
    """Real-time state of trains for graph mutation engine"""
    __tablename__ = "train_states"
    __table_args__ = (
        Index("idx_train_states_trip_id", "trip_id"),
        Index("idx_train_states_status", "status"),
        Index("idx_train_states_last_updated", "last_updated"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    trip_id = Column(Integer, nullable=False, unique=True, index=True)  # References trips.id
    train_number = Column(String(50), nullable=False, index=True)
    current_station_id = Column(Integer, ForeignKey("stops.id"), nullable=True)
    next_station_id = Column(Integer, ForeignKey("stops.id"), nullable=True)
    delay_minutes = Column(Integer, default=0, nullable=False)
    status = Column(String(20), default="on_time", nullable=False)  # on_time, delayed, cancelled, running_late
    platform_number = Column(String(10), nullable=True)
    last_updated = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    estimated_arrival = Column(DateTime, nullable=True)
    estimated_departure = Column(DateTime, nullable=True)
    occupancy_rate = Column(Float, default=0.0, nullable=False)  # 0.0 to 1.0
    cancelled_stations = Column(JSON, default=list, nullable=False)  # List of cancelled stop IDs
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    current_station = relationship("Stop", foreign_keys=[current_station_id])
    next_station = relationship("Stop", foreign_keys=[next_station_id])

    def __repr__(self):
        return f"<TrainState(trip_id={self.trip_id}, status={self.status}, delay={self.delay_minutes})>"

class SeatAvailability(Base):
    """Logs seat availability for ML training and capacity prediction (Phase 8)."""
    __tablename__ = "seat_availability"
    __table_args__ = (
        Index("idx_seat_avail_train_date", "train_number", "travel_date"),
        Index("idx_seat_avail_check_date", "check_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    train_number = Column(String(50), nullable=False, index=True)
    class_code = Column(String(10), nullable=False)  # SL, 3A, 2A, CC, etc.
    quota = Column(String(10), default="GN", nullable=False)
    availability_status = Column(String(100), nullable=False)  # AVAILABLE-0020, RLWL/150, etc.
    waiting_list_number = Column(Integer, nullable=True)
    fare = Column(Float, nullable=True)
    travel_date = Column(DateTime, nullable=False, index=True)
    check_date = Column(DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<SeatAvailability(train={self.train_number}, date={self.travel_date}, status={self.availability_status})>"

class TrainMaster(Base):
    """Minimal train metadata used for capacity baseline predictions."""
    __tablename__ = "trains_master"
    train_number = Column(String(50), primary_key=True)
    train_name = Column(String(255))
    source = Column(String(100))
    destination = Column(String(100))
    days_of_run = Column(JSON)  # Stores ["Mon", "Tue"]
    type = Column(String(100))
    updated_at = Column(DateTime, default=datetime.utcnow)



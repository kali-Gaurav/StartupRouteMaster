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

from backend.database import Base


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

    routes = relationship("Route", back_populates="agency")

class Stop(Base):
    """Consolidated and enhanced model for all stops/stations."""
    __tablename__ = "stops"
    __table_args__ = (
        Index("idx_stops_geom", "geom", postgresql_using="gist"),
        Index("idx_stops_name_trgm", func.lower(Column("name")), postgresql_ops={"name": "gin_trgm_ops"}, postgresql_using="gin"),
    )

    id = Column(Integer, primary_key=True)
    stop_id = Column(String(100), unique=True, nullable=False, index=True) # Public-facing ID
    code = Column(String(100), index=True) # e.g., platform code
    name = Column(String(255), nullable=False, index=True)
    city = Column(String(255), index=True)
    state = Column(String(255))
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    geom = Column(Geometry("POINT", srid=4326), nullable=False)
    location_type = Column(Integer, default=0) # 0 for stop, 1 for station
    parent_station_id = Column(Integer, ForeignKey("stops.id"), nullable=True)

    parent_station = relationship("Stop", remote_side=[id])
    child_stops = relationship("Stop", back_populates="parent_station")
    stop_times = relationship("StopTime", back_populates="stop")

class Route(Base):
    """Represents a single transit route in the GTFS sense (e.g., 'Blue Line')."""
    __tablename__ = "gtfs_routes"

    id = Column(Integer, primary_key=True)
    route_id = Column(String(100), unique=True, nullable=False, index=True)
    agency_id = Column(Integer, ForeignKey("agency.id"), nullable=False, index=True)
    short_name = Column(String(50))
    long_name = Column(String(255), nullable=False)
    route_type = Column(Integer, nullable=False, index=True) # 0: Tram, 1: Subway, 2: Rail, 3: Bus

    agency = relationship("Agency", back_populates="routes")
    trips = relationship("Trip", back_populates="route")

class Calendar(Base):
    """Defines service patterns for routes (e.g., weekday service)."""
    __tablename__ = "calendar"

    id = Column(Integer, primary_key=True)
    service_id = Column(String(100), unique=True, nullable=False, index=True)
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
    service_id = Column(Integer, ForeignKey("calendar.id"), nullable=False, index=True)
    headsign = Column(String(255))
    direction_id = Column(Integer, index=True)

    route = relationship("Route", back_populates="trips")
    service = relationship("Calendar", back_populates="trips")
    stop_times = relationship("StopTime", back_populates="trip", cascade="all, delete-orphan")
    
class StopTime(Base):
    """The arrival and departure of a trip at a specific stop."""
    __tablename__ = "stop_times"
    __table_args__ = (
        UniqueConstraint('trip_id', 'stop_sequence', name='uq_trip_stop_sequence'),
        Index("idx_stop_times_stop_id", "stop_id"),
        Index("idx_stop_times_trip_id", "trip_id"),
    )

    id = Column(Integer, primary_key=True)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=False)
    stop_id = Column(Integer, ForeignKey("stops.id"), nullable=False)
    arrival_time = Column(Time, nullable=False)
    departure_time = Column(Time, nullable=False)
    stop_sequence = Column(Integer, nullable=False)
    cost = Column(Float, nullable=True) # Cost to travel from previous stop to this one
    
    trip = relationship("Trip", back_populates="stop_times")
    stop = relationship("Stop", back_populates="stop_times")
    inventory = relationship("SeatInventory", back_populates="stop_time", uselist=False)

class Transfer(Base):
    """Defines transfer rules between stops."""
    __tablename__ = "transfers"

    id = Column(Integer, primary_key=True)
    from_stop_id = Column(Integer, ForeignKey("stops.id"), nullable=False)
    to_stop_id = Column(Integer, ForeignKey("stops.id"), nullable=False)
    transfer_type = Column(Integer, nullable=False, default=0) # 0: Recommended, 2: Timed transfer
    min_transfer_time = Column(Integer, nullable=False) # In seconds

    from_stop = relationship("Stop", foreign_keys=[from_stop_id])
    to_stop = relationship("Stop", foreign_keys=[to_stop_id])

# ==============================================================================
# MODELS REQUIRING ADAPTATION
# ==============================================================================

class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        # Original constraint is now problematic, needs re-evaluation
        # UniqueConstraint("user_id", "route_id", "travel_date", name="uq_user_route_travel_date"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    travel_date = Column(Date, nullable=False) # Corrected data type from String
    payment_status = Column(String(50), default="pending")
    amount_paid = Column(Float, default=39.0)
    booking_details = Column(JSON, nullable=False) # May store summary of the booked path
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # --- Deprecated / Transitional Fields ---
    route_id = Column(String(36), ForeignKey("precalculated_routes.id"), nullable=True) # FK to old, deprecated table
    
    # --- New Fields ---
    # A booking could be for one or more trips
    # For now, this is a placeholder. A real implementation might need a many-to-many table.
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=True)

    user = relationship("User", back_populates="bookings")
    payment = relationship("Payment", back_populates="booking", uselist=False)
    review = relationship("Review", back_populates="booking", uselist=False)

    # Relationships to be carefully managed during transition
    route = relationship("PrecalculatedRoute", back_populates="bookings")
    trip = relationship("Trip")

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
    # Unique constraint needs to be updated
    # __table_args__ = (
    #     UniqueConstraint('segment_id', 'travel_date', name='uq_segment_travel_date'),
    # )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    travel_date = Column(Date, nullable=False, index=True)
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

# class Vehicle(Base):
#     __tablename__ = "vehicles"
#     __table_args__ = (
#         CheckConstraint("type IN ('train', 'bus', 'flight')", name="vehicle_type_check"),
#     )
#     id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
#     vehicle_number = Column(String(50), nullable=False)
#     type = Column(String(50), nullable=False)
#     operator = Column(String(255), nullable=False)
#     capacity = Column(Integer, nullable=True)
#     segments = relationship("Segment", back_populates="vehicle")

# class Station(Base):
#     __tablename__ = "stations"
#     id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
#     name = Column(String(255), nullable=False, index=True)
#     city = Column(String(255), nullable=False, index=True)
#     latitude = Column(Float, nullable=False)
#     longitude = Column(Float, nullable=False)
#     geom = Column(Geometry("POINT", srid=4326), nullable=True)
#     created_at = Column(DateTime, default=datetime.utcnow)
#     segments_from = relationship("Segment", foreign_keys="Segment.source_station_id", back_populates="source_station")
#     segments_to = relationship("Segment", foreign_keys="Segment.dest_station_id", back_populates="dest_station")

# class Segment(Base):
#     __tablename__ = "segments"
#     id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
#     source_station_id = Column(String(36), ForeignKey("stations.id"), nullable=False, index=True)
#     dest_station_id = Column(String(36), ForeignKey("stations.id"), nullable=False, index=True)
#     vehicle_id = Column(String(36), ForeignKey("vehicles.id"), nullable=True, index=True)
#     transport_mode = Column(String(50), nullable=False)
#     departure_time = Column(String(8), nullable=False)
#     arrival_time = Column(String(8), nullable=False)
#     duration_minutes = Column(Integer, nullable=False)
#     cost = Column(Float, nullable=False)
#     operating_days = Column(String(7), nullable=False, default="1111111")
#     source_station = relationship("Station", foreign_keys=[source_station_id], back_populates="segments_from")
#     dest_station = relationship("Station", foreign_keys=[dest_station_id], back_populates="segments_to")
#     vehicle = relationship("Vehicle", back_populates="segments")
#     inventories = relationship("SeatInventory", back_populates="segment")

# class StationMaster(Base):
#     __tablename__ = "stations_master"
#     station_code = Column(String(10), primary_key=True)
#     station_name = Column(String(255), nullable=False, index=True)
#     # ... other fields

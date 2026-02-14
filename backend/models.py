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
    Index, # Import Index
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from geoalchemy2 import Geometry, func # Import Geometry and func

from backend.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    phone_number = Column(String(20), nullable=True)
    role = Column(String(50), default="user", index=True)  # Add role for RBAC
    created_at = Column(DateTime, default=datetime.utcnow)

    bookings = relationship("Booking", back_populates="user")
    reviews = relationship("Review", back_populates="user")
    unlocked_routes = relationship("UnlockedRoute", back_populates="user") # New: relationship to unlocked routes


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
    __table_args__ = (
        Index("idx_stations_geom", "geom", postgresql_using="gist"),
        Index("idx_stations_name_trgm", func.lower(Column("name")), postgresql_ops={"lower_name": "gin_trgm_ops"}, postgresql_using="gin"),
        Index("idx_stations_city_trgm", func.lower(Column("city")), postgresql_ops={"lower_city": "gin_trgm_ops"}, postgresql_using="gin"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False, index=True)
    city = Column(String(255), nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    geom = Column(Geometry("POINT", srid=4326), nullable=True) # New: Geospatial column
    created_at = Column(DateTime, default=datetime.utcnow)

    segments_from = relationship(
        "Segment", foreign_keys="Segment.source_station_id", back_populates="source_station"
    )
    segments_to = relationship(
        "Segment", foreign_keys="Segment.dest_station_id", back_populates="dest_station"
    )


class Segment(Base):
    __tablename__ = "segments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_station_id = Column(
        String(36), ForeignKey("stations.id"), nullable=False, index=True
    )
    dest_station_id = Column(
        String(36), ForeignKey("stations.id"), nullable=False, index=True
    )
    vehicle_id = Column(String(36), ForeignKey("vehicles.id"), nullable=True, index=True)

    transport_mode = Column(String(50), nullable=False)
    departure_time = Column(String(8), nullable=False)
    arrival_time = Column(String(8), nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    distance_km = Column(Float, nullable=True)
    arrival_day_offset = Column(Integer, default=0) # Day offset from the start of the segment
    cost = Column(Float, nullable=False)
    operating_days = Column(String(7), nullable=False, default="1111111")
    created_at = Column(DateTime, default=datetime.utcnow)

    source_station = relationship(
        "Station", foreign_keys=[source_station_id], back_populates="segments_from"
    )
    dest_station = relationship(
        "Station", foreign_keys=[dest_station_id], back_populates="segments_to"
    )
    vehicle = relationship("Vehicle", back_populates="segments")
    inventories = relationship("SeatInventory", back_populates="segment")


class Route(Base):
    __tablename__ = "routes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source = Column(String(255), nullable=False, index=True)
    destination = Column(String(255), nullable=False, index=True)
    segments = Column(JSON, nullable=False)
    total_duration = Column(String(50), nullable=False)
    total_cost = Column(Float, nullable=False)
    budget_category = Column(String(50), nullable=False)
    num_transfers = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    bookings = relationship("Booking", back_populates="route")


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        UniqueConstraint("user_id", "route_id", "travel_date", name="uq_user_route_travel_date"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    route_id = Column(String(36), ForeignKey("routes.id"), nullable=False)
    travel_date = Column(String(10), nullable=False)
    payment_status = Column(String(50), default="pending")
    amount_paid = Column(Float, default=39.0)
    booking_details = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User", back_populates="bookings")
    route = relationship("Route", back_populates="bookings")
    # payment relationship is defined on Payment.booking (Payment.booking_id)
    payment = relationship("Payment", back_populates="booking", uselist=False)
    review = relationship("Review", back_populates="booking", uselist=False)

class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        CheckConstraint("rating >= 1 AND rating <= 5", name="review_rating_check"),
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
    booking_id = Column(String(36), ForeignKey("bookings.id"), nullable=True, index=True) # Changed to nullable
    razorpay_order_id = Column(String(255), nullable=True, index=True)
    razorpay_payment_id = Column(String(255), nullable=True, index=True)
    status = Column(String(50), default="pending")
    amount = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    booking = relationship("Booking", back_populates="payment")
    # unlocked_route relationship is defined on UnlockedRoute.payment_id
    unlocked_route = relationship("UnlockedRoute", back_populates="payment")


class UnlockedRoute(Base):
    __tablename__ = "unlocked_routes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    route_id = Column(String(36), ForeignKey("routes.id"), nullable=False, index=True)
    payment_id = Column(String(36), ForeignKey("payments.id"), nullable=True, index=True)
    unlocked_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="unlocked_routes")
    route = relationship("Route")
    payment = relationship("Payment", back_populates="unlocked_route", uselist=False)


class StationMaster(Base):
    __tablename__ = "stations_master"
    __table_args__ = (
        Index("idx_stations_master_name_trgm", func.lower(Column("station_name")), postgresql_ops={"lower_station_name": "gin_trgm_ops"}, postgresql_using="gin"),
        Index("idx_stations_master_city_trgm", func.lower(Column("city")), postgresql_ops={"lower_city": "gin_trgm_ops"}, postgresql_using="gin"),
    )

    station_code = Column(String(10), primary_key=True)
    station_name = Column(String(255), nullable=False, index=True)
    city = Column(String(255), nullable=False, index=True)
    state = Column(String(255), nullable=False)
    is_junction = Column(Boolean, default=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    geo_hash = Column(String(12), nullable=True)

class SeatInventory(Base):
    __tablename__ = 'seat_inventory'
    __table_args__ = (
        UniqueConstraint('segment_id', 'travel_date', name='uq_segment_travel_date'),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    segment_id = Column(String(36), ForeignKey('segments.id'), nullable=False, index=True)
    travel_date = Column(Date, nullable=False, index=True)
    seats_available = Column(Integer, nullable=False)
    last_reconciled_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    segment = relationship("Segment", back_populates="inventories")

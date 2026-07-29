"""
Feature #5: Database Optimization Models
New tables for user preference learning and data retention
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Date,
    ForeignKey, Index, Text
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON

from database.infrastructure.base import UserBase, Base
from database.infrastructure.config import Config

logger = logging.getLogger(__name__)

# Use JSONB for PostgreSQL, JSON for SQLite
if Config.DATABASE_URL and "postgresql" in Config.DATABASE_URL.lower():
    JSON_TYPE = JSONB
else:
    JSON_TYPE = SQLiteJSON


# ============================================================================
# USER BOOKING HISTORY - Track every booking for preference learning
# ============================================================================

class UserBookingHistory(UserBase):
    """
    Tracks every booking made by a user for preference learning.
    Used to understand user travel patterns and update preferences.

    Attributes:
        user_id: Reference to user
        booking_id: Reference to booking
        route_id: Reference to route taken
        source_code: Origin station
        destination_code: Destination station
        persona: User persona at time of booking
        fare: Fare paid
        booking_status: Status of booking (confirmed, cancelled, completed)
        travel_date: Date of travel
        created_at: When booking was made
    """
    __tablename__ = "user_booking_history"
    __table_args__ = (
        Index('idx_user_booking_history_user_id', 'user_id', 'created_at'),
        Index('idx_user_booking_history_route', 'route_id', 'booking_status'),
        Index('idx_user_booking_history_travel_date', 'travel_date'),
        {"extend_existing": True}
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    booking_id = Column(String(36), nullable=False, index=True)
    route_id = Column(String(36), nullable=True)
    source_code = Column(String(10), nullable=True)
    destination_code = Column(String(10), nullable=True)
    persona = Column(String(20), nullable=True)  # ECONOMY, COMFORT, PREMIUM, etc.
    fare = Column(Float, nullable=True)
    booking_status = Column(String(20), default="CONFIRMED")  # CONFIRMED, CANCELLED, COMPLETED
    travel_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", foreign_keys=[user_id], backref="booking_history")


# ============================================================================
# USER PREFERENCE UPDATE - Audit trail for preference changes
# ============================================================================

class UserPreferenceUpdate(UserBase):
    """
    Audit trail for user preference changes.
    Tracks what changed, when, why, and the previous value.

    Attributes:
        user_id: User whose preferences changed
        field_name: Which preference field changed
        old_value: Previous value
        new_value: New value
        change_reason: Why it changed (auto, user, system)
        created_at: When change occurred
    """
    __tablename__ = "user_preference_updates"
    __table_args__ = (
        Index('idx_user_preference_updates_user_id', 'user_id', 'created_at'),
        {"extend_existing": True}
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    field_name = Column(String(100), nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    change_reason = Column(String(100), nullable=True)  # "auto_learned", "user_edit", "admin"
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", foreign_keys=[user_id], backref="preference_updates")


# ============================================================================
# MATERIALIZED VIEWS (as Python classes for ORM access)
# ============================================================================

class TrendingRoute(Base):
    """
    Materialized view of trending routes.
    Combined ranking: search_count (30%) + booking_count (30%) + reliability (20%) + conversion (20%)
    """
    __tablename__ = "trending_routes"
    __table_args__ = {"extend_existing": True}

    id = Column(String(36), primary_key=True)
    source_code = Column(String(10), nullable=False)
    destination_code = Column(String(10), nullable=False)
    search_count = Column(Integer, default=0)
    booking_count = Column(Integer, default=0)
    reliability_score = Column(Float, default=0.0)
    avg_fare = Column(Float, default=0.0)
    conversion_rate = Column(Float, default=0.0)
    trending_score = Column(Float, default=0.0)
    last_updated = Column(DateTime)


class UserSegmentation(Base):
    """
    Materialized view of user segmentation.
    Groups users by: price sensitivity, booking pattern, user type
    """
    __tablename__ = "user_segmentation"
    __table_args__ = {"extend_existing": True}

    user_id = Column(String(36), primary_key=True)
    price_segment = Column(String(20))  # PRICE_SENSITIVE, PRICE_INSENSITIVE, BALANCED
    booking_pattern = Column(String(20))  # PLANNER, LAST_MINUTE, REGULAR
    user_type = Column(String(20))  # POWER_USER, REGULAR_USER, NEW_USER
    preference_confidence = Column(Float, default=0.0)
    total_interactions = Column(Integer, default=0)
    cancellation_rate = Column(Float, default=0.0)
    no_show_rate = Column(Float, default=0.0)


class RouteQualityScore(Base):
    """
    Materialized view of pre-computed route quality scores.
    Used for quick ranking: reliability (40%) + on-time (30%) + performance (30%)
    """
    __tablename__ = "route_quality_scores"
    __table_args__ = {"extend_existing": True}

    id = Column(String(36), primary_key=True)
    source_code = Column(String(10), nullable=False)
    destination_code = Column(String(10), nullable=False)
    duration_minutes = Column(Integer)
    reliability_score = Column(Float, default=0.0)
    on_time_percentage = Column(Float, default=0.0)
    avg_delay_minutes = Column(Float, default=0.0)
    quality_score = Column(Float, default=0.0)
    last_updated = Column(DateTime)


# ============================================================================
# HELPER FUNCTIONS FOR PREFERENCE LEARNING
# ============================================================================

def record_booking(db_session, user_id: str, booking_id: str, route_id: str,
                   source_code: str, destination_code: str, persona: str,
                   fare: float, travel_date: str):
    """
    Record a booking in the user booking history.
    Called after a successful booking.
    """
    try:
        booking_history = UserBookingHistory(
            user_id=user_id,
            booking_id=booking_id,
            route_id=route_id,
            source_code=source_code,
            destination_code=destination_code,
            persona=persona,
            fare=fare,
            booking_status="CONFIRMED",
            travel_date=datetime.strptime(travel_date, "%Y-%m-%d").date() if travel_date else None
        )
        db_session.add(booking_history)
        db_session.commit()
        logger.info(f"Recorded booking {booking_id} for user {user_id}")
    except Exception as e:
        logger.error(f"Failed to record booking history: {e}")
        db_session.rollback()


def record_preference_update(db_session, user_id: str, field_name: str,
                            old_value: str, new_value: str, reason: str = "auto_learned"):
    """
    Record a preference update in the audit trail.
    Called when user preferences are automatically updated based on behavior.
    """
    try:
        update = UserPreferenceUpdate(
            user_id=user_id,
            field_name=field_name,
            old_value=old_value,
            new_value=new_value,
            change_reason=reason
        )
        db_session.add(update)
        db_session.commit()
        logger.info(f"Recorded preference update for user {user_id}: {field_name}")
    except Exception as e:
        logger.error(f"Failed to record preference update: {e}")
        db_session.rollback()


def get_user_segment(db_session, user_id: str) -> Optional[Dict[str, Any]]:
    """
    Get the user's segment from the materialized view.
    """
    try:
        segment = db_session.query(UserSegmentation).filter(
            UserSegmentation.user_id == user_id
        ).first()

        if segment:
            return {
                "price_segment": segment.price_segment,
                "booking_pattern": segment.booking_pattern,
                "user_type": segment.user_type,
                "preference_confidence": segment.preference_confidence
            }
        return None
    except Exception as e:
        logger.error(f"Failed to get user segment: {e}")
        return None

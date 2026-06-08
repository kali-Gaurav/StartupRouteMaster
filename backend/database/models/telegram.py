"""
Telegram Bot Database Models
Stores messages, bookings, SOS events, and analytics for Telegram bot.
Core user and session models are maintained in core.py.
"""

from database.infrastructure.base import UserBase
from sqlalchemy import Column, String, Integer, DateTime, Text, Boolean, ForeignKey, JSON, Float
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from .core import TelegramUser, TelegramSession


class TelegramMessage(UserBase):
    __table_args__ = {"extend_existing": True}
    """
    Stores all messages for analytics and training.
    Enables message history and context.
    """
    __tablename__ = "telegram_messages"
    __table_args__ = {"extend_existing": True}

    
    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(String(50), nullable=False, index=True)
    
    # User reference
    telegram_user_id = Column(Integer, ForeignKey("telegram_users.id"), nullable=False, index=True)
    
    # Message details
    direction = Column(String(10), nullable=False)  # INBOUND or OUTBOUND
    message_type = Column(String(30), default="text")  # text, callback, command, media
    content = Column(Text, nullable=True)
    content_hash = Column(String(64), nullable=True)
    
    # Intent classification
    intent = Column(String(50), nullable=True)
    intent_confidence = Column(Float, nullable=True)
    entities = Column(JSON, nullable=True)
    
    # Response
    response_text = Column(Text, nullable=True)
    response_time_ms = Column(Integer, nullable=True)
    
    # Metadata
    message_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    telegram_user = relationship("TelegramUser", back_populates="messages")
    
    def __repr__(self):
        return f"<TelegramMessage(user={self.telegram_user_id}, type={self.message_type})>"


class TelegramBookingLink(UserBase):
    __table_args__ = {"extend_existing": True}
    """
    Tracks booking links created via Telegram.
    Enables deep linking and conversion tracking.
    """
    __tablename__ = "telegram_booking_links"
    __table_args__ = {"extend_existing": True}

    
    id = Column(Integer, primary_key=True, autoincrement=True)
    link_token = Column(String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    
    # User reference
    telegram_user_id = Column(Integer, ForeignKey("telegram_users.id"), nullable=False, index=True)
    
    # Booking details
    train_number = Column(String(20), nullable=True)
    source = Column(String(10), nullable=True)
    destination = Column(String(10), nullable=True)
    travel_date = Column(String(10), nullable=True)
    train_class = Column(String(10), nullable=True)
    
    # Status
    is_used = Column(Boolean, default=False)
    used_at = Column(DateTime, nullable=True)
    booking_id = Column(String(36), nullable=True)
    
    # Expiry
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    telegram_user = relationship("TelegramUser", back_populates="bookings")
    
    def __repr__(self):
        return f"<TelegramBookingLink(user={self.telegram_user_id}, train={self.train_number})>"


class TelegramSOSEvent(UserBase):
    __table_args__ = {"extend_existing": True}
    """
    Tracks SOS events triggered via Telegram.
    Enables emergency response and analytics.
    """
    __tablename__ = "telegram_sos_events"
    __table_args__ = {"extend_existing": True}

    
    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    
    # User reference
    telegram_user_id = Column(Integer, ForeignKey("telegram_users.id"), nullable=False, index=True)
    
    # Location (optional)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    location_shared = Column(Boolean, default=False)
    
    # Status
    status = Column(String(20), default="PENDING")  # PENDING, ACKNOWLEDGED, RESOLVED, CANCELLED
    priority = Column(String(10), default="NORMAL")  # LOW, NORMAL, HIGH, CRITICAL
    
    # Response tracking
    acknowledged_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    responder_notes = Column(Text, nullable=True)
    
    # Notifications sent
    notifications_sent = Column(Integer, default=0)
    contacts_notified = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    telegram_user = relationship("TelegramUser", back_populates="sos_events")
    
    def __repr__(self):
        return f"<TelegramSOSEvent(user={self.telegram_user_id}, status={self.status})>"


class TelegramAnalytics(UserBase):
    __table_args__ = {"extend_existing": True}
    """
    Daily analytics for Telegram bot performance.
    Enables monitoring and optimization.
    """
    __tablename__ = "telegram_analytics"
    __table_args__ = {"extend_existing": True}

    
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(DateTime, nullable=False, index=True)
    
    # User metrics
    new_users = Column(Integer, default=0)
    active_users = Column(Integer, default=0)
    total_users = Column(Integer, default=0)
    
    # Message metrics
    total_messages = Column(Integer, default=0)
    inbound_messages = Column(Integer, default=0)
    outbound_messages = Column(Integer, default=0)
    
    # Intent distribution
    intent_distribution = Column(JSON, nullable=True)
    
    # Feature usage
    search_count = Column(Integer, default=0)
    booking_count = Column(Integer, default=0)
    pnr_count = Column(Integer, default=0)
    sos_count = Column(Integer, default=0)
    
    # Performance
    avg_response_time_ms = Column(Float, default=0.0)
    success_rate = Column(Float, default=100.0)
    
    # Errors
    error_count = Column(Integer, default=0)
    error_types = Column(JSON, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<TelegramAnalytics(date={self.date.date()}, users={self.active_users})>"


class TelegramNotificationTemplate(UserBase):
    __table_args__ = {"extend_existing": True}
    """
    Stores notification templates for consistent messaging.
    Enables localization and A/B testing.
    """
    __tablename__ = "telegram_notification_templates"
    __table_args__ = {"extend_existing": True}

    
    id = Column(Integer, primary_key=True, autoincrement=True)
    template_id = Column(String(50), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    category = Column(String(50), nullable=False)  # booking, sos, search, general
    
    # Content
    content = Column(Text, nullable=False)
    parse_mode = Column(String(10), default="HTML")  # HTML, Markdown
    
    # Variants for A/B testing
    variants = Column(JSON, nullable=True)
    active_variant = Column(String(50), nullable=True)
    
    # Metadata
    language = Column(String(10), default="en")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<TelegramNotificationTemplate(id={self.template_id}, name={self.name})>"


# Export for easy importing
__all__ = [
    'TelegramUser',
    'TelegramSession', 
    'TelegramMessage',
    'TelegramBookingLink',
    'TelegramSOSEvent',
    'TelegramAnalytics',
    'TelegramNotificationTemplate'
]

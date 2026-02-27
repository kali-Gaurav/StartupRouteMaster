from sqlalchemy import Column, Integer, String, DateTime, Enum, Text, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum
from datetime import datetime

Base = declarative_base()

class NotificationType(str, enum.Enum):
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"

class NotificationStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    DELIVERED = "delivered"

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    type = Column(Enum(NotificationType), nullable=False)
    subject = Column(String(255))
    message = Column(Text, nullable=False)
    recipient = Column(String(255), nullable=False)  # email or phone
    status = Column(Enum(NotificationStatus), default=NotificationStatus.PENDING)
    external_id = Column(String(255))  # Twilio/SendGrid message ID
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    sent_at = Column(DateTime)
    booking_id = Column(Integer, ForeignKey("bookings.id"))

    booking = relationship("Booking", back_populates="notifications")

class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    route_id = Column(String(50), nullable=False)
    train_number = Column(String(20))
    departure_station = Column(String(100))
    arrival_station = Column(String(100))
    departure_time = Column(DateTime)
    arrival_time = Column(DateTime)
    passenger_count = Column(Integer, default=1)
    total_amount = Column(Float, nullable=False)
    status = Column(String(50), default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    notifications = relationship("Notification", back_populates="booking")

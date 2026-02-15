from sqlalchemy import Column, String, Integer, DateTime, JSON, Float, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class TrainMaster(Base):
    __tablename__ = "trains_master"
    train_number = Column(String, primary_key=True)
    train_name = Column(String)
    source = Column(String)
    destination = Column(String)
    days_of_run = Column(JSON)  # Stores ["Mon", "Tue"]
    type = Column(String)
    updated_at = Column(DateTime, default=datetime.utcnow)

class TrainStation(Base):
    __tablename__ = "train_stations"
    id = Column(Integer, primary_key=True, autoincrement=True)
    train_number = Column(String, ForeignKey("trains_master.train_number"))
    station_code = Column(String)
    station_name = Column(String)
    sequence = Column(Integer)
    arrival = Column(String)
    departure = Column(String)
    halt_minutes = Column(Integer)
    distance_km = Column(Float)
    day_count = Column(Integer)

    __table_args__ = (UniqueConstraint('train_number', 'sequence', name='uix_train_seq'),)

class LiveStatus(Base):
    __tablename__ = "train_live_status"
    train_number = Column(String, primary_key=True)
    current_station = Column(String)
    status = Column(String)  # On Time, Delayed
    delay_minutes = Column(Integer)
    next_station = Column(String)
    eta_next = Column(String)
    last_updated_ts = Column(DateTime, default=datetime.utcnow)

class SeatAvailability(Base):
    __tablename__ = "seat_availability"
    id = Column(Integer, primary_key=True, autoincrement=True)
    train_number = Column(String)
    class_code = Column(String)  # SL, 3A, 2A
    quota = Column(String)
    availability_status = Column(String)  # AVAILABLE-20, WL10
    fare = Column(Float)
    check_date = Column(DateTime, default=datetime.utcnow)

class ScheduleChangeLog(Base):
    """Records differences detected between a newly extracted schedule and the DB snapshot."""
    __tablename__ = "schedule_change_log"
    id = Column(Integer, primary_key=True, autoincrement=True)
    train_number = Column(String, index=True)
    detected_at = Column(DateTime, default=datetime.utcnow)
    diff = Column(JSON)  # JSON describing changes
    resolved = Column(Boolean, default=False)
    notes = Column(String, nullable=True)
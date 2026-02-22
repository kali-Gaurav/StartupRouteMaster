# compatibility stub for legacy imports
# Many modules used to import seat_inventory_models directly from backend.
# The relevant models have since been consolidated into backend.database.models.
# This file ensures those imports continue to work during tests and at runtime.

from .database.models import *  # noqa: F401,F403

# Define any legacy classes that are still referenced but not present in
# database.models. These are minimal SQLAlchemy models that allow the
# import to succeed and create the corresponding tables during tests.

from .database.session import Base
from sqlalchemy import Column, String, Integer, ForeignKey, Boolean, JSON


class QuotaInventory(Base):
    __tablename__ = "quota_inventory"
    __table_args__ = {"extend_existing": True}
    id = Column(String(36), primary_key=True)
    inventory_id = Column(String(36), ForeignKey("seat_inventory.id"))
    quota_type = Column(String(50))
    allocated_seats = Column(Integer, default=0)
    available_seats = Column(Integer, default=0)
    max_allocation = Column(Integer, default=0)


class WaitlistQueue(Base):
    __tablename__ = "waitlist_queue"
    __table_args__ = {"extend_existing": True}
    id = Column(String(36), primary_key=True)
    inventory_id = Column(String(36))
    user_id = Column(String(36))
    waitlist_position = Column(Integer)
    passengers_json = Column(JSON)
    preferences_json = Column(JSON)
    status = Column(String(50))


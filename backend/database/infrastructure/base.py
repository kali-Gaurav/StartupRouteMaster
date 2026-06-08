from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import DateTime, Integer, MetaData
from datetime import datetime

class Base(DeclarativeBase):
    """The base class for all SQLAlchemy models."""
    pass

class TimestampMixin:
    """[Industrial Rigor] Automatically track creation and modification times."""
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class AuditMixin:
    """[Industrial Rigor] Provides optimistic locking and record versioning."""
    version_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    
    __mapper_args__ = {
        "version_id_col": version_id
    }

class UserBase(Base):
    __abstract__ = True
    __table_args__ = {"extend_existing": True}

class TransitBase(Base):
    __abstract__ = True
    __table_args__ = {"extend_existing": True}



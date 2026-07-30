"""Audit log database models."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Index
from sqlalchemy.orm import declarative_base
from sqlalchemy.dialects.postgresql import JSON

Base = declarative_base()


class AuditLog(Base):
    """Immutable audit log of all database mutations."""

    __tablename__ = "audit_log"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # What changed
    table_name = Column(String(255), nullable=False, index=True)
    operation = Column(String(10), nullable=False, index=True)  # INSERT, UPDATE, DELETE
    record_id = Column(String(255), nullable=True, index=True)  # ID of changed record

    # Who changed it
    user_id = Column(String(255), nullable=True, index=True)
    timestamp = Column(DateTime, nullable=False, index=True, default=datetime.utcnow)
    ip_address = Column(String(45), nullable=True)  # IPv4 or IPv6
    session_id = Column(String(255), nullable=True)

    # What the values were
    before_values = Column(JSON, nullable=True)  # Old values for UPDATE/DELETE
    after_values = Column(JSON, nullable=True)   # New values for INSERT/UPDATE

    # Retention policy
    retention_days = Column(Integer, nullable=False, default=30)

    # Indexes for common queries
    __table_args__ = (
        Index("idx_audit_table_timestamp", "table_name", "timestamp"),
        Index("idx_audit_user_timestamp", "user_id", "timestamp"),
        Index("idx_audit_operation", "operation"),
        Index("idx_audit_record_id", "record_id"),
    )

    def __repr__(self):
        return (
            f"<AuditLog(id={self.id}, table={self.table_name}, "
            f"op={self.operation}, user={self.user_id}, "
            f"timestamp={self.timestamp})>"
        )

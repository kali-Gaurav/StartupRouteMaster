"""
Database Audit Logging

Captures all INSERT/UPDATE/DELETE operations with user context (who, when, what changed).
Provides queryable audit trail for compliance, forensics, and debugging.
"""

import logging
import json
from contextvars import ContextVar
from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy import event, inspect
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger("db-audit")

# Context variable to store current request info (user_id, IP, etc.)
_request_context: ContextVar[Dict[str, Any]] = ContextVar("request_context", default={})


def set_request_context(user_id: Optional[str] = None, ip_address: Optional[str] = None,
                       session_id: Optional[str] = None):
    """Set request context for audit logging."""
    context = {
        "user_id": user_id,
        "ip_address": ip_address,
        "session_id": session_id,
    }
    _request_context.set(context)


def get_request_context() -> Dict[str, Any]:
    """Get current request context."""
    return _request_context.get({})


class AuditLogger:
    """Captures database mutations and stores in audit log."""

    # Tables to exclude from audit logging (audit tables themselves)
    EXCLUDED_TABLES = {"audit_log", "audit_logs", "alembic_version"}

    @staticmethod
    def should_audit_table(table_name: str) -> bool:
        """Check if table should be audited."""
        return table_name.lower() not in AuditLogger.EXCLUDED_TABLES

    @staticmethod
    def get_record_values(mapper, instance) -> Dict[str, Any]:
        """Extract all column values from a mapped instance."""
        values = {}
        for column in mapper.columns:
            value = getattr(instance, column.name, None)
            # Convert to JSON-serializable format
            if value is None:
                values[column.name] = None
            elif isinstance(value, (str, int, float, bool)):
                values[column.name] = value
            elif isinstance(value, datetime):
                values[column.name] = value.isoformat()
            else:
                values[column.name] = str(value)
        return values

    @staticmethod
    def create_audit_entry(table_name: str, operation: str, record_id: Any,
                          before_values: Optional[Dict] = None,
                          after_values: Optional[Dict] = None) -> Dict[str, Any]:
        """Create an audit log entry."""
        context = get_request_context()

        entry = {
            "table_name": table_name,
            "operation": operation,  # INSERT, UPDATE, DELETE
            "record_id": str(record_id) if record_id else None,
            "user_id": context.get("user_id"),
            "timestamp": datetime.utcnow().isoformat(),
            "ip_address": context.get("ip_address"),
            "session_id": context.get("session_id"),
            "before_values": before_values,
            "after_values": after_values,
        }
        return entry

    @staticmethod
    def log_insert(mapper, connection, target):
        """Log INSERT operation."""
        if not AuditLogger.should_audit_table(mapper.class_.__tablename__):
            return

        table_name = mapper.class_.__tablename__
        after_values = AuditLogger.get_record_values(mapper, target)

        # Try to get primary key value
        pk_value = None
        pk_cols = mapper.primary_key
        if pk_cols:
            pk_value = getattr(target, pk_cols[0].name, None)

        entry = AuditLogger.create_audit_entry(
            table_name=table_name,
            operation="INSERT",
            record_id=pk_value,
            after_values=after_values
        )

        try:
            AuditLogger._write_audit_entry(connection, entry)
            logger.debug(f"Audited INSERT on {table_name} (id={pk_value})")
        except Exception as e:
            logger.error(f"Failed to audit INSERT on {table_name}: {e}")

    @staticmethod
    def log_update(mapper, connection, target):
        """Log UPDATE operation."""
        if not AuditLogger.should_audit_table(mapper.class_.__tablename__):
            return

        table_name = mapper.class_.__tablename__

        # Get changed attributes
        hist = inspect(target).attrs
        before_values = {}
        after_values = {}

        for attr in hist:
            if attr.history.has_changes():
                old_value = attr.history.deleted[0] if attr.history.deleted else None
                new_value = attr.history.added[0] if attr.history.added else None

                # Convert to JSON-serializable
                before_values[attr.key] = old_value if old_value is None else (
                    old_value.isoformat() if isinstance(old_value, datetime) else str(old_value)
                )
                after_values[attr.key] = new_value if new_value is None else (
                    new_value.isoformat() if isinstance(new_value, datetime) else str(new_value)
                )

        # Get primary key
        pk_value = None
        pk_cols = mapper.primary_key
        if pk_cols:
            pk_value = getattr(target, pk_cols[0].name, None)

        entry = AuditLogger.create_audit_entry(
            table_name=table_name,
            operation="UPDATE",
            record_id=pk_value,
            before_values=before_values,
            after_values=after_values
        )

        try:
            AuditLogger._write_audit_entry(connection, entry)
            logger.debug(f"Audited UPDATE on {table_name} (id={pk_value})")
        except Exception as e:
            logger.error(f"Failed to audit UPDATE on {table_name}: {e}")

    @staticmethod
    def log_delete(mapper, connection, target):
        """Log DELETE operation."""
        if not AuditLogger.should_audit_table(mapper.class_.__tablename__):
            return

        table_name = mapper.class_.__tablename__
        before_values = AuditLogger.get_record_values(mapper, target)

        # Get primary key
        pk_value = None
        pk_cols = mapper.primary_key
        if pk_cols:
            pk_value = getattr(target, pk_cols[0].name, None)

        entry = AuditLogger.create_audit_entry(
            table_name=table_name,
            operation="DELETE",
            record_id=pk_value,
            before_values=before_values
        )

        try:
            AuditLogger._write_audit_entry(connection, entry)
            logger.debug(f"Audited DELETE on {table_name} (id={pk_value})")
        except Exception as e:
            logger.error(f"Failed to audit DELETE on {table_name}: {e}")

    @staticmethod
    def _write_audit_entry(connection, entry: Dict[str, Any]):
        """Write audit entry to database."""
        # Convert entry to JSON string for storage
        entry_json = json.dumps(entry, default=str)

        # Use raw SQL to insert audit entry
        # Note: This assumes audit_log table exists
        sql = """
            INSERT INTO audit_log
            (table_name, operation, record_id, user_id, timestamp, ip_address, session_id,
             before_values, after_values)
            VALUES (%(table_name)s, %(operation)s, %(record_id)s, %(user_id)s, %(timestamp)s,
                    %(ip_address)s, %(session_id)s, %(before_values)s, %(after_values)s)
        """

        try:
            connection.execute(
                sql,
                {
                    "table_name": entry.get("table_name"),
                    "operation": entry.get("operation"),
                    "record_id": entry.get("record_id"),
                    "user_id": entry.get("user_id"),
                    "timestamp": entry.get("timestamp"),
                    "ip_address": entry.get("ip_address"),
                    "session_id": entry.get("session_id"),
                    "before_values": json.dumps(entry.get("before_values")) if entry.get("before_values") else None,
                    "after_values": json.dumps(entry.get("after_values")) if entry.get("after_values") else None,
                }
            )
        except SQLAlchemyError as e:
            logger.warning(f"Could not write audit entry (audit table may not exist yet): {e}")


def initialize_audit_logging(engine):
    """Register audit event listeners on engine."""
    # Register event listeners for all mapped classes
    event.listen(engine, "after_insert", AuditLogger.log_insert, propagate=True)
    event.listen(engine, "after_update", AuditLogger.log_update, propagate=True)
    event.listen(engine, "after_delete", AuditLogger.log_delete, propagate=True)

    logger.info("✅ Audit logging initialized")

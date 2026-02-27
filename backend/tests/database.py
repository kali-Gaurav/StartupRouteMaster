"""Backward-compatible exports needed by the tests under `backend.tests`."""

from database import Base, get_db, SessionLocal

__all__ = ["Base", "get_db", "SessionLocal"]

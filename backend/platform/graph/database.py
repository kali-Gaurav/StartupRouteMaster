"""Graph-specific helpers that delegate to the main database package."""

from backend.database import SessionLocal

__all__ = ["SessionLocal"]
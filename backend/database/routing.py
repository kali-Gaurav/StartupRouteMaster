"""
Query Routing & Load Balancing

Routes SELECT queries to replicas and INSERT/UPDATE/DELETE queries to primary.
Provides session wrapper that automatically selects the correct database connection.
"""

import logging
from typing import Optional, Any
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from .replication import ReplicationManager, get_transit_replication_manager

logger = logging.getLogger("db-routing")


class ReadWriteRouter:
    """
    Routes queries to primary or replica based on operation type.
    Synchronous version for sync code.
    """

    def __init__(self, replication_manager: ReplicationManager):
        self.manager = replication_manager

    def get_session(self, is_write: bool = False) -> Session:
        """
        Get a database session for read or write operations.

        Args:
            is_write: True for INSERT/UPDATE/DELETE, False for SELECT

        Returns:
            SQLAlchemy Session connected to appropriate database
        """
        if is_write:
            engine = self.manager.get_primary_engine()
        else:
            engine = self.manager.get_replica_engine_sync(fallback_to_primary=True)

        return Session(engine)


class AsyncReadWriteRouter:
    """
    Routes queries to primary or replica based on operation type.
    Asynchronous version for async code.
    """

    def __init__(self, replication_manager: ReplicationManager):
        self.manager = replication_manager

    async def get_session(self, is_write: bool = False) -> AsyncSession:
        """
        Get an async database session for read or write operations.

        Args:
            is_write: True for INSERT/UPDATE/DELETE, False for SELECT

        Returns:
            SQLAlchemy AsyncSession connected to appropriate database
        """
        if is_write:
            engine = self.manager.get_primary_engine()
        else:
            engine = await self.manager.get_replica_engine(fallback_to_primary=True)

        return AsyncSession(engine)

    async def execute_read(self, statement):
        """Execute a read-only query on replica."""
        session = await self.get_session(is_write=False)
        try:
            result = await session.execute(statement)
            return result
        finally:
            await session.close()

    async def execute_write(self, statement):
        """Execute a write query on primary."""
        session = await self.get_session(is_write=True)
        try:
            result = await session.execute(statement)
            await session.commit()
            return result
        finally:
            await session.close()


class RouteAnalyzer:
    """
    Analyzes SQLAlchemy statements to determine if they're reads or writes.
    """

    @staticmethod
    def is_write_operation(statement) -> bool:
        """
        Determine if a statement is a write operation.

        Args:
            statement: SQLAlchemy statement object

        Returns:
            True if statement is INSERT/UPDATE/DELETE, False if SELECT
        """
        stmt_str = str(statement).upper()

        # Check for DML statements
        if any(stmt_str.startswith(op) for op in ["INSERT", "UPDATE", "DELETE", "TRUNCATE"]):
            return True

        # Check SQLAlchemy statement types
        statement_type = type(statement).__name__
        if statement_type in ("Insert", "Update", "Delete"):
            return True

        return False

    @staticmethod
    def is_read_operation(statement) -> bool:
        """Determine if a statement is a read (SELECT) operation."""
        return not RouteAnalyzer.is_write_operation(statement)


class SmartSession:
    """
    Wrapper around Session that automatically routes queries.
    USE WITH CAUTION: This works for most cases but may miss edge cases.
    For explicit control, use AsyncReadWriteRouter directly.
    """

    def __init__(self, router: AsyncReadWriteRouter):
        self.router = router
        self._primary_session: Optional[AsyncSession] = None
        self._replica_session: Optional[AsyncSession] = None
        self._engine_primary: Optional[Any] = None
        self._engine_replica: Optional[Any] = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._primary_session:
            await self._primary_session.close()
        if self._replica_session:
            await self._replica_session.close()

    async def execute(self, statement):
        """Execute a statement, routing to primary or replica automatically."""
        is_write = RouteAnalyzer.is_write_operation(statement)

        if is_write:
            if not self._primary_session:
                self._primary_session = await self.router.get_session(is_write=True)
            session = self._primary_session
        else:
            if not self._replica_session:
                self._replica_session = await self.router.get_session(is_write=False)
            session = self._replica_session

        return await session.execute(statement)

    async def commit(self):
        """Commit primary session (writes)."""
        if self._primary_session:
            await self._primary_session.commit()


def get_transit_router() -> Optional[AsyncReadWriteRouter]:
    """Get the transit database read-write router."""
    manager = get_transit_replication_manager()
    if manager is None:
        return None
    return AsyncReadWriteRouter(manager)


async def get_smart_session() -> Optional[SmartSession]:
    """Get a smart session that auto-routes queries."""
    router = get_transit_router()
    if router is None:
        return None
    return SmartSession(router)

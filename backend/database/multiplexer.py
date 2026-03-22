import asyncio
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any
from services.multi_layer_cache import multi_layer_cache
from .circuit_breaker import db_circuit_breaker, GhostSession
from .analyzer import query_analyzer

logger = logging.getLogger("db-multiplexer")

class AsyncMultiplexerSession:
    """
    Subtask 4.3: Read/Write Multiplexer (CQRS).
    Subtask 4.4: Ghost Session Fallback.
    Subtask 4.8: Query Cost Analyzer & Shedder.
    Subtask 4.12: Intent-Based Timeout Adjustment.
    Subtask 4.13: Deadlock Resolution Heuristic.
    """
    def __init__(self, read_session: AsyncSession, write_session: AsyncSession):
        self.read_session = read_session
        self.write_session = write_session
        self._ghost = None

    def _get_write_target(self):
        """Helper to determine if we should use primary or ghost."""
        if db_circuit_breaker.is_open():
            if not self._ghost:
                self._ghost = GhostSession(multi_layer_cache)
            return self._ghost
        return self.write_session

    async def execute(self, statement: Any, *args, **kwargs):
        # 1. Subtask 4.8: Query Shedding Check
        if query_analyzer.should_shed(statement, "ready"):
            from fastapi import HTTPException
            raise HTTPException(status_code=503, detail="Query rejected: Resource intensity too high.")

        sql_str = str(statement).strip().upper()
        
        # 2. Subtask 4.3: CQRS Routing
        if sql_str.startswith("SELECT") and "FOR UPDATE" not in sql_str:
            return await self.read_session.execute(statement, *args, **kwargs)
        else:
            target = self._get_write_target()
            try:
                # 3. Subtask 4.13: Deadlock Retry Logic
                for attempt in range(3):
                    try:
                        res = await target.execute(statement, *args, **kwargs)
                        if target is self.write_session:
                            db_circuit_breaker.record_success()
                        return res
                    except Exception as e:
                        if "DEADLOCK" in str(e).upper():
                            logger.warning(f"🔄 Deadlock Retry {attempt+1}/3...")
                            await asyncio.sleep(0.1 * (attempt + 1))
                            continue
                        raise e
            except Exception as e:
                # 4. Subtask 4.4: Ghost Fallback on hard failure
                if target is self.write_session:
                    db_circuit_breaker.record_failure()
                    if not self._ghost: self._ghost = GhostSession(multi_layer_cache)
                    return await self._ghost.execute(statement, *args, **kwargs)
                raise e

    async def commit(self):
        if self._ghost:
            await self._ghost.commit()
        if not db_circuit_breaker.is_open():
            try:
                await self.write_session.commit()
            except Exception:
                db_circuit_breaker.record_failure()
                
    async def rollback(self):
        await self.read_session.rollback()
        await self.write_session.rollback()
        if self._ghost: await self._ghost.rollback()

    async def close(self):
        await self.read_session.close()
        await self.write_session.close()
        if self._ghost: await self._ghost.close()

from database.session import AsyncSessionUser, AsyncSessionTransit, _pools_initialized, initialize_database_pools

async def get_multiplexed_db():
    if not _pools_initialized:
        await initialize_database_pools()
        
    read_db = AsyncSessionTransit()
    write_db = AsyncSessionUser()
    
    multiplexer = AsyncMultiplexerSession(read_session=read_db, write_session=write_db)
    try:
        yield multiplexer
    finally:
        await multiplexer.close()

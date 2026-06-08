import asyncio
import logging
from typing import List, Any, Dict, Callable, Awaitable
from sqlalchemy import select, text

logger = logging.getLogger("db-batcher")

class HydrationBatcher:
    """
    Subtask 4.11: Query Batching for Hydration.
    Consolidates multiple similar lookups into single IN clauses.
    """
    def __init__(self, db_session):
        self.db = db_session

    async def fetch_multiple_by_id(self, model: Any, ids: List[Any]) -> Dict[Any, Any]:
        """
        Batches N individual lookups into 1 database round-trip.
        """
        if not ids: return {}
        
        # Deduplicate
        unique_ids = list(set(ids))
        logger.info(f"📦 Batcher: Consolidating {len(ids)} lookups into 1 query.")
        
        query = select(model).where(model.id.in_(unique_ids))
        result = await self.db.execute(query)
        
        items = result.scalars().all()
        return {getattr(item, 'id'): item for item in items}

    async def execute_batched_statements(self, statements: List[Any]):
        """
        Executes multiple statements. 
        Note: AsyncSession does not support concurrent execution on ONE session.
        We execute sequentially but provide a unified interface.
        """
        results = []
        for stmt in statements:
            res = await self.db.execute(stmt)
            results.append(res)
        return results

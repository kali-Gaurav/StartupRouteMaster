"""
Database Agent
==============
Handles database migrations, integrity checks, and cleanup.
"""
import logging
import asyncio
from typing import Dict, Any
from services.agents.base_agent import BaseAgent

logger = logging.getLogger("agent.database")

class DatabaseAgent(BaseAgent):
    """Handles database operations"""
    
    def __init__(self):
        super().__init__(
            name="DatabaseAgent",
            description="Manages database migrations, integrity checks, and cleanup",
            category="database"
        )
    
    async def on_start(self):
        """Initialize database agent"""
        logger.info("🗄️ DatabaseAgent starting...")
        return True
    
    async def execute_migration(self, **kwargs) -> Dict[str, Any]:
        """Execute database migrations"""
        try:
            from database.session import get_db
            from alembic import command
            from alembic.config import Config
            import os
            
            # Get alembic config
            alembic_cfg = Config(os.path.join(os.path.dirname(__file__), "../../alembic.ini"))
            
            # Run migrations
            command.upgrade(alembic_cfg, "head")
            
            return {
                "operation": "migration",
                "status": "completed",
                "message": "Database migrations applied successfully"
            }
        except Exception as e:
            logger.error(f"❌ Migration failed: {e}")
            return {
                "operation": "migration",
                "status": "failed",
                "error": str(e)
            }
    
    async def execute_integrity_check(self, **kwargs) -> Dict[str, Any]:
        """Check database integrity"""
        try:
            from database.session import get_db
            from sqlalchemy import text
            
            async with get_db() as db:
                # Check database connection
                result = await db.execute(text("SELECT 1"))
                connection_ok = result.scalar() == 1
                
                # Check table counts
                tables_result = await db.execute(text(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
                ))
                tables = [row[0] for row in tables_result.fetchall()]
                
                return {
                    "operation": "integrity_check",
                    "status": "completed",
                    "connection": "healthy" if connection_ok else "failed",
                    "tables": tables,
                    "table_count": len(tables)
                }
        except Exception as e:
            logger.error(f"❌ Integrity check failed: {e}")
            return {
                "operation": "integrity_check",
                "status": "failed",
                "error": str(e)
            }
    
    async def execute_cleanup(self, **kwargs) -> Dict[str, Any]:
        """Clean up old data"""
        try:
            from database.session import get_db
            from sqlalchemy import text
            import datetime
            
            async with get_db() as db:
                # Delete old sessions (older than 30 days)
                cutoff_date = datetime.datetime.now() - datetime.timedelta(days=30)
                result = await db.execute(
                    text("DELETE FROM sessions WHERE created_at < :cutoff"),
                    {"cutoff": cutoff_date}
                )
                deleted_count = result.rowcount
                
                return {
                    "operation": "cleanup",
                    "status": "completed",
                    "deleted_sessions": deleted_count,
                    "message": f"Cleaned up {deleted_count} old sessions"
                }
        except Exception as e:
            logger.error(f"❌ Cleanup failed: {e}")
            return {
                "operation": "cleanup",
                "status": "failed",
                "error": str(e)
            }
    
    async def execute(self, task: str, **kwargs) -> Dict[str, Any]:
        """Execute database task"""
        task_lower = task.lower()
        
        if "migration" in task_lower or "migrate" in task_lower:
            return await self.execute_migration(**kwargs)
        elif "integrity" in task_lower or "check" in task_lower:
            return await self.execute_integrity_check(**kwargs)
        elif "cleanup" in task_lower or "clean" in task_lower:
            return await self.execute_cleanup(**kwargs)
        else:
            return {
                "operation": "unknown",
                "status": "failed",
                "error": f"Unknown database task: {task}"
            }

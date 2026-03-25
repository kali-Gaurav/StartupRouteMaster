import logging
import asyncio
from sqlalchemy.orm import Session
from database.session import SessionLocal
from database.models import User, CommissionTracking
from services.commission_service import commission_service

logger = logging.getLogger("settlement-job")

async def run_settlement_cycle():
    """
    [Task 44.5] Daily Cron to settle all pending agent commissions.
    """
    logger.info("📅 Starting Daily Commission Settlement Cycle...")
    db = SessionLocal()
    try:
        # Find all agents with pending commissions
        agents = db.query(CommissionTracking.user_id).filter(
            CommissionTracking.status == "PENDING"
        ).distinct().all()
        
        agent_ids = [a.user_id for a in agents]
        logger.info(f"Found {len(agent_ids)} agents with pending earnings.")
        
        for agent_id in agent_ids:
            try:
                commission_service.settle_batch(db, agent_id)
            except Exception as e:
                logger.error(f"❌ Failed to settle for agent {agent_id}: {e}")
                db.rollback()
                
        logger.info("✅ Settlement Cycle Completed Successfully.")
    finally:
        db.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_settlement_cycle())

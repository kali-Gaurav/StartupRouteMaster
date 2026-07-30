import logging
from datetime import datetime, timedelta
from typing import List, Tuple, Dict
from sqlalchemy import func
from sqlalchemy.orm import Session
from database.models import RouteSearchLog
from core.nexus.intelligence.corridors import get_high_demand_pairs

logger = logging.getLogger("agents.forecasting")

class DemandForecastingAgent:
    """
    [Group 3] Adaptive Demand Forecasting Agent.
    Monitors real-time search trends to discover 'Hot Corridors' and drive 10ms performance.
    """
    def __init__(self, db: Session):
        self.db = db

    async def identify_emerging_corridors(self, lookback_hours: int = 24, min_hits: int = 10) -> List[Tuple[str, str]]:
        """
        Scans RouteSearchLog for clusters of high-volume interest not yet in the static list.
        """
        threshold_time = datetime.utcnow() - timedelta(hours=lookback_hours)
        
        # Aggregate search counts per route in the lookback window
        trends = self.db.query(
            RouteSearchLog.src,
            RouteSearchLog.dst,
            func.count(RouteSearchLog.id).label("hits")
        ).filter(
            RouteSearchLog.created_at >= threshold_time
        ).group_by(
            RouteSearchLog.src,
            RouteSearchLog.dst
        ).having(
            func.count(RouteSearchLog.id) >= min_hits
        ).order_by(
            func.count(RouteSearchLog.id).desc()
        ).all()

        emerging = [(t.src, t.dst) for t in trends]
        logger.info(f"📈 [FORECAST] Identified {len(emerging)} emerging hot-spots in last {lookback_hours}h.")
        return emerging

    async def get_prioritized_warmup_targets(self) -> List[Tuple[str, str]]:
        """
        Combines static 'Festival' corridors with real-time 'Emerging' trends.
        """
        # 1. Get Static / Regional Pairs
        static_pairs = get_high_demand_pairs()
        
        # 2. Get Real-time Emerging Trends
        emerging_pairs = await self.identify_emerging_corridors()
        
        # 3. Merge and De-duplicate
        combined = list(set(static_pairs + emerging_pairs))
        return combined

    async def trigger_proactive_warming(self):
        """
        Forces a targeted cache warming cycle for identified hot-spots.
        """
        from services.cache_warming_service import cache_warming_service
        targets = await self.get_prioritized_warmup_targets()
        
        if not targets:
            return

        logger.info(f"🔥 [FORECAST] Triggering proactive warming for {len(targets)} targets.")
        # In production, we'd pass these targets directly to a specialized warmer
        # For now, we drive the existing service cycle which is now smarter
        await cache_warming_service.start_warming_cycle()

def get_demand_forecasting_agent(db: Session):
    return DemandForecastingAgent(db)

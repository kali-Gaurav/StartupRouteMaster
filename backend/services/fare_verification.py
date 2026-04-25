import logging
from typing import Dict, Any, List
from datetime import datetime
from collections import deque
import asyncio

from core.route_engine.data_provider import DataProvider

logger = logging.getLogger(__name__)

class FareVerificationService:
    """
    Service for verifying journey fares.
    
    With metrics tracking for verification operations.
    """
    
    def __init__(self):
        self.data_provider = DataProvider()
        
        # Metrics tracking
        self._metrics: deque = deque(maxlen=1000)
        self._metrics_lock = asyncio.Lock()
        
        logger.info("FareVerificationService initialized with metrics tracking")

    async def verify_journey_fares(self, journey: Dict[str, Any], coach_preference: str = "AC_THREE_TIER") -> Dict[str, Any]:
        """
        Verify fares for all legs of a journey concurrently.
        """
        import asyncio
        tasks = []
        
        # Journey has 'legs' or 'segments'
        legs = journey.get('legs', [])
        
        for leg in legs:
            tasks.append(self.data_provider.verify_fare_unified(
                segment_id=None, # Use train/station codes
                coach_preference=coach_preference,
                train_number=leg.get('train_number'),
                from_station=leg.get('from'),
                to_station=leg.get('to')
            ))
            
        if not tasks:
            return {"total_fare": journey.get('total_cost', 0), "verified": True}
            
        results = await asyncio.gather(*tasks)
        
        total_fare = sum(float(r.get('total_fare', 0)) for r in results)
        
        return {
            "total_fare": total_fare,
            "leg_details": results,
            "verified": all(r.get('status') == 'verified' for r in results)
        }

    # =========================================================================
    # METRICS TRACKING
    # =========================================================================

    async def _record_metrics(self, operation_type: str, success: bool, error: str = None):
        """Record metrics for verification operations."""
        async with self._metrics_lock:
            self._metrics.append({
                "timestamp": datetime.utcnow(),
                "operation_type": operation_type,
                "success": success,
                "error": error
            })

    def get_metrics(self) -> dict:
        """Get service metrics."""
        if not self._metrics:
            return {"total_operations": 0, "success_rate": 0.0}
        
        total = len(self._metrics)
        successful = sum(1 for m in self._metrics if m["success"])
        by_type = {}
        for m in self._metrics:
            op_type = m.get("operation_type", "unknown")
            if op_type not in by_type:
                by_type[op_type] = {"total": 0, "success": 0}
            by_type[op_type]["total"] += 1
            if m["success"]:
                by_type[op_type]["success"] += 1
        
        return {
            "total_operations": total,
            "successful_operations": successful,
            "success_rate": successful / total if total > 0 else 0.0,
            "operation_breakdown": by_type
        }

    def health_check(self) -> dict:
        """Health check endpoint."""
        return {
            "status": "healthy",
            "metrics": self.get_metrics()
        }

import logging
from datetime import datetime
from database.models import Stop

logger = logging.getLogger(__name__)

class BufferOptimizationManager:
    """
    Task 7: Layover Buffer Optimization.
    Calculates dynamic safety buffers for transfers.
    """
    
    BASE_BUFFER = 30 # minutes
    HUB_ADDITIONAL_BUFFER = 60 # +1 hour for major junctions
    WINTER_BUFFER = 45 # +45 mins during fog season (Dec-Feb)

    def calculate_required_buffer(self, stop_id: int, graph_stop_cache: dict, travel_date: datetime) -> int:
        """Determines the minimum minutes required for a safe transfer."""
        buffer = self.BASE_BUFFER
        
        # 1. Station Importance
        stop = graph_stop_cache.get(stop_id)
        if stop and getattr(stop, 'is_major_junction', False):
            buffer += self.HUB_ADDITIONAL_BUFFER
            
        # 2. Fog/Winter Season (Task 7.15)
        if travel_date.month in [12, 1, 2]:
            buffer += self.WINTER_BUFFER
            
        return buffer

buffer_optimizer = BufferOptimizationManager()

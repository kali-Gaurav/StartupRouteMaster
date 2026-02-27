from core.celery_app import celery
from core.redis import redis_client
from services.enhanced_pricing_service import enhanced_pricing_service
import json
import logging

logger = logging.getLogger(__name__)

@celery.task(name="predict_route_price")
def predict_route_price(route_id, base_cost, travel_date_str, occupancy_rate=0.5):
    """
    Background task to predict dynamic price for a route using ML models.
    Stores the result in Redis for quick access by the search service.
    """
    try:
        logger.info(f"Predicting price for route {route_id}, base_cost: {base_cost}")
        
        # Mocking a Route object for the service
        class MockRoute:
            def __init__(self, rid, cost, dt_str, occ):
                self.id = rid
                self.total_cost = cost
                self.travel_date = datetime.strptime(dt_str, "%Y-%m-%d").date()
                self.occupancy_rate = occ
                self.demand_score = 0.7 # Example high demand
                self.popularity_score = 0.8

        from datetime import datetime
        mock_route = MockRoute(route_id, base_cost, travel_date_str, occupancy_rate)
        
        final_price, breakdown = enhanced_pricing_service.calculate_final_price(mock_route, use_ml=True)
        
        # Store in Redis
        cache_key = f"pricing:prediction:{route_id}"
        redis_client.setex(cache_key, 3600, json.dumps({
            "final_price": final_price,
            "breakdown": breakdown,
            "timestamp": datetime.utcnow().isoformat()
        }))
        
        logger.info(f"Price prediction complete for {route_id}: {final_price}")
        return {"route_id": route_id, "final_price": final_price}
        
    except Exception as e:
        logger.error(f"Error in predict_route_price: {e}")
        return {"error": str(e)}

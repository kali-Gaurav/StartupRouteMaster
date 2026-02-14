import asyncio
import logging
import random
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

async def fetch_external_routes(
    source: str,
    destination: str,
    travel_date: str,
    budget_category: Optional[str] = None,
    simulate_delay_ms: int = 0,
    simulate_failure_rate: float = 0.0
) -> List[Dict]:
    """
    Simulates fetching real-time route data from an external Railway/Bus API.
    
    Args:
        source: The source station name.
        destination: The destination station name.
        travel_date: The date of travel.
        budget_category: Optional budget category.
        simulate_delay_ms: Milliseconds to simulate network delay.
        simulate_failure_rate: Probability (0.0 to 1.0) of simulating an API failure.
        
    Returns:
        A list of dictionaries, where each dictionary represents a route.
    """
    
    if simulate_delay_ms > 0:
        await asyncio.sleep(simulate_delay_ms / 1000.0)
        
    if random.random() < simulate_failure_rate:
        logger.warning(f"Simulating external API failure for {source} to {destination}")
        raise ConnectionError("Simulated external API connection error")
        
    logger.info(f"Simulating external API fetch for {source} to {destination} on {travel_date}. (Delay: {simulate_delay_ms}ms, Failure Rate: {simulate_failure_rate})")
    
    # In a real scenario, this would involve making HTTP requests to external APIs
    # and parsing their responses into a standardized format.
    
    # For demonstration, return a dummy route
    if source == "Delhi" and destination == "Mumbai":
        return [
            {
                "id": "ext_route_1",
                "source": source,
                "destination": destination,
                "segments": [
                    {
                        "mode": "train",
                        "from": source,
                        "to": destination,
                        "departure_time": "08:00",
                        "arrival_time": "22:00",
                        "duration": "14h 0m",
                        "cost": 1500.0,
                        "details": "External Train Xpress"
                    }
                ],
                "total_duration": "14h 0m",
                "total_duration_minutes": 840,
                "total_cost": 1500.0,
                "safetyScore": 90,
                "budget_category": "standard",
                "num_transfers": 0,
                "is_unlocked": False
            }
        ]
    return []


async def fetch_external_inventory(segment_id: str, travel_date: str) -> Optional[int]:
    """
    Simulates fetching current seat availability for a specific segment and date
    from an external partner API.
    """
    logger.info(f"Simulating external inventory fetch for segment {segment_id} on {travel_date}.")
    
    # Simulate some delay
    await asyncio.sleep(random.uniform(0.1, 0.5))
    
    # Simulate variable availability
    if "segment_bus_1" in segment_id and travel_date == "2024-03-15":
        return random.randint(5, 15) # Example: 5-15 seats available
    elif "segment_train_2" in segment_id and travel_date == "2024-03-16":
        return 0 # Example: fully booked
    
    return random.randint(1, 30) # Default random availability

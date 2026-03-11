import logging
from typing import Dict, Any, List
from core.route_engine.data_provider import DataProvider

logger = logging.getLogger(__name__)

class FareVerificationService:
    def __init__(self):
        self.data_provider = DataProvider()

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

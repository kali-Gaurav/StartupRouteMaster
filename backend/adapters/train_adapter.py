import uuid
import logging
from typing import List
from schemas.unified_search import JourneyOption, JourneySegment

logger = logging.getLogger(__name__)

class TrainAdapter:
    def __init__(self, search_service):
        self.search_service = search_service

    async def search(self, req) -> List[JourneyOption]:
        """
        Calls the existing high-performance SearchService and maps results 
        to the Unified Journey Schema.
        """
        try:
            # Reusing the existing search_routes logic
            result = await self.search_service.search_routes(
                source=req.source,
                destination=req.destination,
                travel_date=req.date
            )
            
            journeys = []
            if not result or not result.get("journeys"):
                return []

            for r in result["journeys"]:
                segments = []
                for seg in r.get("legs", []):
                    segments.append(JourneySegment(
                        mode="train",
                        from_station=seg.get("from_station_code", ""),
                        to_station=seg.get("to_station_code", ""),
                        departure=seg.get("departure_time", ""),
                        arrival=seg.get("arrival_time", ""),
                        duration_minutes=seg.get("duration_minutes", 0),
                        price=float(seg.get("fare", 0.0)) if seg.get("fare") is not None else 0.0,
                        train_number=seg.get("train_number"),
                        train_name=seg.get("train_name")
                    ))
                
                # Create a JourneyOption compliant with V2 schema
                journeys.append(JourneyOption(
                    journey_id=r.get("journey_id", str(uuid.uuid4())),
                    total_price=float(r.get("total_cost", 0.0)),
                    total_duration=int(r.get("total_duration", 0)),
                    safety_score=r.get("safety_score", 0.85),
                    segments=segments,
                    is_locked=True, # Revenue Model: Hidden until payment
                    availability_status=r.get("availability_status", "PENDING")
                ))
            
            return journeys
        except Exception as e:
            logger.error(f"TrainAdapter Error: {e}", exc_info=True)
            return []

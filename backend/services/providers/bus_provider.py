import random
import asyncio
from typing import List, Dict, Any, Optional
from services.providers.base_provider import BaseProvider, TransportType


class MockBusProvider(BaseProvider):
    """
    [G8.1.3] Reference Mock Implementation: Bus Provider.
    Demonstrates how any new modality (Flight, Taxi, etc) can be 
    added using the BaseProvider contract.
    """
    
    async def search(self, src: str, dst: str, date: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        self.logger.info(f"🚌 Searching bus routes for {src} -> {dst}")
        # Simulated Search Results
        return [{
            "provider_id": self.provider_id,
            "transport_type": "bus",
            "bus_id": f"BUS-{random.randint(100,999)}",
            "operator": "RouteMaster Express",
            "departure": f"{date}T10:00:00",
            "arrival": f"{date}T18:00:00",
            "total_cost": 450.0,
            "availability": 15
        }]

    async def verify(self, candidate_id: str) -> Dict[str, Any]:
        return {"status": "available", "price": 450.0}

    async def book(self, candidate_id: str, passenger_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        pnr = f"BUSPNR-{random.randint(10000, 99999)}"
        return {
            "status": "success",
            "pnr": pnr,
            "message": f"Bus seat confirmed for {len(passenger_data)} passengers."
        }

    async def cancel(self, booking_id: str) -> bool:
        return True

    async def get_status(self, booking_id: str) -> str:
        return "SCHEDULED"

# Usage/Registration
bus_provider = MockBusProvider(provider_id="RM_INTERNAL_BUS", transport_type=TransportType.BUS)

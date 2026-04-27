import random
from typing import List, Dict, Any, Optional
from services.providers.base_provider import BaseProvider, TransportType

class MockFlightProvider(BaseProvider):
    """[G8.1.4] Mock Flight Provider."""
    
    async def search(self, src: str, dst: str, date: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        self.logger.info(f"✈️ Searching flights for {src} -> {dst}")
        return [{
            "provider_id": self.provider_id,
            "transport_type": "flight",
            "flight_num": f"RM-{random.randint(100,999)}",
            "airline": "SkyMaster",
            "total_cost": 4500.0,
            "pnr_status": "AVAILABLE",
            "departure_code": src,
            "arrival_code": dst
        }]

    async def verify(self, candidate_id: str) -> Dict[str, Any]: return {"status": "available", "price": 4500.0}
    async def book(self, candidate_id: str, passenger_data: List[Dict[str, Any]]) -> Dict[str, Any]: return {"status": "success", "pnr": f"FLY-{random.randint(1000,9999)}"}
    async def cancel(self, booking_id: str) -> bool: return True
    async def get_status(self, booking_id: str) -> str: return "CONFIRMED"

class MockTaxiProvider(BaseProvider):
    """[G8.1.5] Mock Taxi Provider."""
    
    async def search(self, src: str, dst: str, date: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        self.logger.info(f"🚕 Fetching taxi availability for {src}")
        return [{
            "provider_id": self.provider_id,
            "transport_type": "taxi",
            "vehicle": "Sedan",
            "eta_mins": 5,
            "total_cost": 300.0
        }]

    async def verify(self, candidate_id: str) -> Dict[str, Any]: return {"status": "available", "price": 300.0}
    async def book(self, candidate_id: str, passenger_data: List[Dict[str, Any]]) -> Dict[str, Any]: return {"status": "success", "ride_id": f"TAXI-{random.randint(100,999)}"}
    async def cancel(self, booking_id: str) -> bool: return True
    async def get_status(self, booking_id: str) -> str: return "ARRIVING"

# Instances
flight_p = MockFlightProvider(provider_id="SKY_ONE", transport_type=TransportType.FLIGHT)
taxi_p = MockTaxiProvider(provider_id="CITY_CAB", transport_type=TransportType.TAXI)

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime
from schemas.multimodal import MultimodalSegment, TransportMode

class MultimodalProvider(ABC):
    """
    [Titan:Omniscient] Abstract Base for External Travel APIs.
    This allows us to swap RapidAPI for AnyDirectAPI with zero downtime.
    """
    
    @abstractmethod
    async def search_flights(self, origin: str, destination: str, date: datetime) -> List[MultimodalSegment]:
        pass

    @abstractmethod
    async def search_buses(self, origin: str, destination: str, date: datetime) -> List[MultimodalSegment]:
        pass

    @abstractmethod
    async def get_taxi_estimate(self, origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float) -> Optional[MultimodalSegment]:
        pass

    @abstractmethod
    def get_status(self) -> str:
        pass

class MockMultimodalProvider(MultimodalProvider):
    """
    Strict Fallback: Returns empty lists if no real provider is available.
    Ensures the 'Omniscient' engine doesn't crash if API keys are missing.
    """
    async def search_flights(self, origin, destination, date): return []
    async def search_buses(self, origin, destination, date): return []
    async def get_taxi_estimate(self, olat, olng, dlat, dlng): return None
    def get_status(self): return "MOCK"

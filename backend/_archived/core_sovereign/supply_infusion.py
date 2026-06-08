"""
Supply Infusion Engine (SIE)
==============================
Patent Innovation #3: Autonomous multi-modal supply activation.

When rail demand exceeds supply on a corridor, the SIE automatically identifies
and activates alternative transport modes (Bus, Cab, Flight) to absorb overflow.
"""

import logging
import asyncio
import uuid
import time
from datetime import datetime, timedelta, date
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("sovereign.sie")

class SupplyMode(str, Enum):
    BUS = "bus"
    CAB = "cab"
    FLIGHT = "flight"
    METRO = "metro"

@dataclass(slots=True)
class SupplyOption:
    option_id: str
    mode: SupplyMode
    provider: str
    source: str
    destination: str
    departure_time: Optional[datetime] = None
    arrival_time: Optional[datetime] = None
    duration_minutes: int = 0
    fare: float = 0.0
    available_seats: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

class SupplyInfusionEngine:
    """
    Autonomous multi-modal supply activation engine.
    """

    def __init__(self):
        self._metrics = {"total_activations": 0}

    async def get_emergency_alternatives(
        self, 
        source: str, 
        destination: str, 
        pressure: float
    ) -> List[Dict[str, Any]]:
        """
        API expected by SIO.
        """
        if pressure < 0.90:
            return []

        logger.info(f"🚨 [SSIE] Searching for Emergency Alternatives for {source}->{destination} (Pressure: {pressure:.2f})")
        
        # Simulate discovery
        alternatives = []
        
        # Mock Bus Alternative
        bus_route = {
            "journey_id": f"ssie_bus_{uuid.uuid4().hex[:6]}",
            "type": "EMERGENCY_BUS",
            "transport_type": "BUS",
            "source": source,
            "destination": destination,
            "departure_time": (datetime.utcnow() + timedelta(hours=2)).isoformat(),
            "total_duration": 480,
            "total_cost": 950.0,
            "availability_count": 25,
            "score": 8.0,
            "metadata": {
                "is_ssie_injected": True,
                "reason": "RAIL_SATURATION",
                "ui_reasons": ["🚌 Direct Bus - Rail corridor is saturated"]
            }
        }
        alternatives.append(bus_route)
        
        self._metrics["total_activations"] += 1
        return alternatives

    def apply_emergency_subsidy(self, route: Dict[str, Any]) -> Dict[str, Any]:
        """
        Applies a system-paid subsidy to make the alternative attractive.
        """
        original_price = route.get("total_cost", 1000.0)
        subsidy = original_price * 0.35 # 35% Patent-Level Subsidy
        route["total_cost"] = original_price - subsidy
        route["metadata"]["subsidy_applied"] = subsidy
        route["metadata"]["ui_reasons"].append(f"💸 Sovereign Subsidy: Rs {int(subsidy)} applied")
        
        return route

# Global Singleton
ssie = SupplyInfusionEngine()

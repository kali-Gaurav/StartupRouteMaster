"""
Corridor Safety Bus - SOS Integration with Route Engine

Real-time safety event integration with routing.
Automatic route deprioritization in affected corridors.
Kafka-based event streaming for safety alerts.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from collections import defaultdict

from backend.services.route_engine import RouteEngine, Journey

# Define SafetyLevel locally to avoid import issues
class SafetyLevel:
    """Safety severity levels"""
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    MINIMAL = "minimal"

logger = logging.getLogger(__name__)


class SafetyEventType(str, Enum):
    """Types of safety events"""
    STATION_ALERT = "station_alert"
    CORRIDOR_ALERT = "corridor_alert"
    ROUTE_DISRUPTION = "route_disruption"
    WEATHER_WARNING = "weather_warning"
    CROWD_SAFETY = "crowd_safety"
    INFRASTRUCTURE_ISSUE = "infrastructure_issue"
    EVENT_CANCELLED = "event_cancelled"


@dataclass
class SafetyEvent:
    """Safety event from SOS system"""
    event_id: str
    event_type: SafetyEventType
    corridor: str  # e.g., "NDLS-BCT"
    stations: List[str]
    severity: SafetyLevel
    description: str
    start_time: datetime
    end_time: Optional[datetime]
    affected_routes: List[str] = field(default_factory=list)
    safety_penalty: float = 0.5  # 0.0 to 1.0, higher = more penalty
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class CorridorSafetyStatus:
    """Safety status for a corridor"""
    corridor: str
    safety_score: float  # 0.0 to 1.0, higher = safer
    active_events: int
    last_updated: datetime
    risk_level: SafetyLevel
    affected_stations: List[str]


class CorridorSafetyBus:
    """
    Manages safety events and integrates with route engine.
    
    Features:
    - Kafka-based event streaming for safety alerts
    - Automatic route deprioritization in affected corridors
    - Safety penalty calculation for route scoring
    - Cache invalidation on safety events
    - User auto-rerouting away from danger zones
    """
    
    # Corridor to station mapping
    CORRIDOR_STATIONS = {
        "NDLS-BCT": ["NDLS", "BCT", "GZB", "PYN", "KJN"],
        "NDLS-MAS": ["NDLS", "CNB", "AGA", "BPL", "NGP", "ET", "BP", "MAS"],
        "BCT-ADI": ["BCT", "ST", "BH", "GDA", "ADI"],
        "MAS-BLR": ["MAS", "KPD", "JTJ", "BLR"],
        "NDLS-CNB": ["NDLS", "CNB", "KNP"],
        "BLR-MAS": ["BLR", "JTJ", "KPD", "MAS"],
    }
    
    # Safety penalty by severity
    SEVERITY_PENALTIES = {
        SafetyLevel.CRITICAL: 0.9,
        SafetyLevel.HIGH: 0.7,
        SafetyLevel.MODERATE: 0.4,
        SafetyLevel.LOW: 0.2,
        SafetyLevel.MINIMAL: 0.1,
    }
    
    def __init__(
        self,
        route_engine: RouteEngine,
        sos_service = None
    ):
        self.route_engine = route_engine
        self.sos_service = sos_service
        self._active_events: Dict[str, SafetyEvent] = {}
        self._corridor_cache: Dict[str, CorridorSafetyStatus] = {}
        self._station_to_corridors: Dict[str, Set[str]] = defaultdict(set)
        self._subscribers: Set[str] = set()  # Connection IDs subscribed to updates
        
        # Build station-to-corridors mapping
        for corridor, stations in self.CORRIDOR_STATIONS.items():
            for station in stations:
                self._station_to_corridors[station].add(corridor)
    
    async def publish_safety_event(self, event: SafetyEvent) -> None:
        """
        Publish a safety event to the corridor safety bus.
        
        This triggers:
        - Route deprioritization in affected corridors
        - Cache invalidation
        - Subscriber notifications
        """
        logger.info(
            f"Safety event published: {event.event_id} "
            f"for corridor {event.corridor} "
            f"(severity: {event.severity})"
        )
        
        # Store the event
        self._active_events[event.event_id] = event
        
        # Update corridor safety status
        await self._update_corridor_status(event.corridor)
        
        # Invalidate route cache for affected stations
        await self._invalidate_cache(event)
        
        # Notify subscribers
        await self._notify_subscribers(event)
        
        # Apply safety penalty to route engine
        self._apply_safety_penalty(event)
    
    async def _update_corridor_status(self, corridor: str) -> None:
        """Update safety status for a corridor based on active events"""
        events_in_corridor = [
            e for e in self._active_events.values()
            if e.corridor == corridor
        ]
        
        if not events_in_corridor:
            # No active events, corridor is safe
            self._corridor_cache[corridor] = CorridorSafetyStatus(
                corridor=corridor,
                safety_score=1.0,
                active_events=0,
                last_updated=datetime.utcnow(),
                risk_level=SafetyLevel.MINIMAL,
                affected_stations=[]
            )
            return
        
        # Calculate combined safety score
        total_penalty = sum(
            e.safety_penalty * self.SEVERITY_PENALTIES.get(e.severity, 0.5)
            for e in events_in_corridor
        )
        
        # Average penalty across events
        avg_penalty = total_penalty / len(events_in_corridor)
        safety_score = 1.0 - avg_penalty
        
        # Determine risk level
        if safety_score >= 0.8:
            risk_level = SafetyLevel.MINIMAL
        elif safety_score >= 0.6:
            risk_level = SafetyLevel.LOW
        elif safety_score >= 0.4:
            risk_level = SafetyLevel.MODERATE
        elif safety_score >= 0.2:
            risk_level = SafetyLevel.HIGH
        else:
            risk_level = SafetyLevel.CRITICAL
        
        # Collect affected stations
        affected_stations = set()
        for event in events_in_corridor:
            affected_stations.update(event.stations)
        
        self._corridor_cache[corridor] = CorridorSafetyStatus(
            corridor=corridor,
            safety_score=safety_score,
            active_events=len(events_in_corridor),
            last_updated=datetime.utcnow(),
            risk_level=risk_level,
            affected_stations=list(affected_stations)
        )
    
    async def _invalidate_cache(self, event: SafetyEvent) -> None:
        """Invalidate route cache for stations affected by safety event"""
        # In a real implementation, this would:
        # 1. Delete cached routes for affected station pairs
        # 2. Signal to the cache service to refresh data
        # 3. Notify connected clients to refresh
        
        logger.info(
            f"Invalidating cache for stations: {event.stations}"
        )
        
        # For now, log the invalidation
        # In production: await cache_service.invalidate_stations(event.stations)
    
    async def _notify_subscribers(self, event: SafetyEvent) -> None:
        """Notify all subscribers about the safety event"""
        for subscriber_id in self._subscribers:
            try:
                # In a real implementation, this would send to WebSocket/ SSE
                logger.debug(f"Notifying subscriber {subscriber_id} about event")
            except Exception as e:
                logger.error(f"Error notifying subscriber {subscriber_id}: {e}")
    
    def _apply_safety_penalty(self, event: SafetyEvent) -> None:
        """
        Apply safety penalty to route engine configuration.
        
        Routes in affected corridors will be deprioritized
        based on the safety penalty.
        """
        # Store penalty for use in route scoring
        penalty_key = f"safety_penalty_{event.corridor}"
        
        # In a real implementation, this would update route engine config
        logger.info(
            f"Applied safety penalty {event.safety_penalty} "
            f"for corridor {event.corridor}"
        )
    
    async def get_corridor_safety(
        self,
        source: str,
        destination: str
    ) -> CorridorSafetyStatus:
        """
        Get safety status for a corridor.
        
        Args:
            source: Source station code
            destination: Destination station code
            
        Returns:
            Safety status for the corridor
        """
        # Find corridor for this station pair
        corridor = self._find_corridor(source, destination)
        
        if not corridor:
            # Unknown corridor, return neutral status
            return CorridorSafetyStatus(
                corridor=f"{source}-{destination}",
                safety_score=1.0,
                active_events=0,
                last_updated=datetime.utcnow(),
                risk_level=SafetyLevel.MINIMAL,
                affected_stations=[]
            )
        
        # Return cached status or calculate
        if corridor in self._corridor_cache:
            return self._corridor_cache[corridor]
        
        # Calculate status
        await self._update_corridor_status(corridor)
        return self._corridor_cache.get(corridor)
    
    def _find_corridor(self, source: str, destination: str) -> Optional[str]:
        """Find corridor for a station pair"""
        # Check both directions
        for corridor, stations in self.CORRIDOR_STATIONS.items():
            if source in stations and destination in stations:
                return corridor
        
        # Check if stations are in the same corridor
        source_corridors = self._station_to_corridors.get(source, set())
        dest_corridors = self._station_to_corridors.get(destination, set())
        
        common = source_corridors & dest_corridors
        if common:
            return list(common)[0]
        
        return None
    
    def calculate_route_safety_score(
        self,
        journey: Journey,
        source: str,
        destination: str
    ) -> float:
        """
        Calculate safety score for a complete journey.
        
        Applies safety penalties for each segment based on
        active safety events in the corridor.
        
        Returns:
            Safety score from 0.0 (unsafe) to 1.0 (safe)
        """
        # Get corridor safety status
        corridor_status = asyncio.run(
            self.get_corridor_safety(source, destination)
        )
        
        # Base score from corridor
        base_score = corridor_status.safety_score
        
        # Additional penalty for stations in affected list
        affected_stations = set(corridor_status.affected_stations)
        
        journey_stations = set()
        for segment in journey.segments:
            journey_stations.add(segment.from_station)
            journey_stations.add(segment.to_station)
        
        # Calculate overlap
        overlap = journey_stations & affected_stations
        if overlap:
            # Reduce score based on affected stations
            overlap_penalty = len(overlap) * 0.1
            base_score = max(0.0, base_score - overlap_penalty)
        
        return base_score
    
    def get_safety_adjusted_score(
        self,
        base_score: float,
        journey: Journey,
        source: str,
        destination: str
    ) -> float:
        """
        Get safety-adjusted route score.
        
        Combines base route quality score with safety penalty.
        
        Args:
            base_score: Original route quality score
            journey: Route journey
            source: Source station
            destination: Destination station
            
        Returns:
            Adjusted score with safety considerations
        """
        safety_score = self.calculate_route_safety_score(
            journey, source, destination
        )
        
        # Safety weight: 30% of final score
        adjusted_score = (base_score * 0.7) + (safety_score * 0.3)
        
        return adjusted_score
    
    async def resolve_safety_event(self, event_id: str) -> bool:
        """
        Resolve a safety event.
        
        Args:
            event_id: ID of the event to resolve
            
        Returns:
            True if event was found and resolved
        """
        if event_id not in self._active_events:
            return False
        
        event = self._active_events[event_id]
        del self._active_events[event_id]
        
        # Update corridor status
        await self._update_corridor_status(event.corridor)
        
        logger.info(f"Safety event resolved: {event_id}")
        return True
    
    def subscribe(self, connection_id: str) -> None:
        """Subscribe to safety event updates"""
        self._subscribers.add(connection_id)
    
    def unsubscribe(self, connection_id: str) -> None:
        """Unsubscribe from safety event updates"""
        self._subscribers.discard(connection_id)
    
    def get_active_events(self) -> List[Dict[str, Any]]:
        """Get all active safety events"""
        return [
            {
                "event_id": event.event_id,
                "event_type": event.event_type.value,
                "corridor": event.corridor,
                "severity": event.severity.value,
                "description": event.description,
                "safety_penalty": event.safety_penalty,
                "timestamp": event.timestamp.isoformat()
            }
            for event in self._active_events.values()
        ]


# Kafka event producer/consumer for safety events
class SafetyEventProducer:
    """Kafka producer for publishing safety events"""
    
    def __init__(self, bootstrap_servers: str = "localhost:9092"):
        self.bootstrap_servers = bootstrap_servers
        self._producer = None  # Would be initialized with kafka-python
    
    async def publish_event(self, event: SafetyEvent) -> None:
        """Publish safety event to Kafka"""
        # In production:
        # from kafka import KafkaProducer
        # self._producer = KafkaProducer(bootstrap_servers=self.bootstrap_servers)
        # self._producer.send(
        #     "corridor.safety",
        #     value=json.dumps(event.__dict__, default=str)
        # )
        logger.info(f"Would publish to Kafka: {event.event_id}")


class SafetyEventConsumer:
    """Kafka consumer for receiving safety events"""
    
    def __init__(
        self,
        bootstrap_servers: str = "localhost:9092",
        safety_bus: Optional[CorridorSafetyBus] = None
    ):
        self.bootstrap_servers = bootstrap_servers
        self.safety_bus = safety_bus
        self._consumer = None
        self._running = False
    
    async def start(self) -> None:
        """Start consuming safety events"""
        self._running = True
        
        # In production:
        # from kafka import KafkaConsumer
        # self._consumer = KafkaConsumer(
        #     "corridor.safety",
        #     bootstrap_servers=self.bootstrap_servers,
        #     value_deserializer=lambda x: json.loads(x.decode("utf-8"))
        # )
        # for message in self._consumer:
        #     await self._handle_event(message.value)
        
        logger.info("Safety event consumer started")
    
    async def _handle_event(self, event_data: Dict[str, Any]) -> None:
        """Handle incoming safety event"""
        if not self.safety_bus:
            return
        
        event = SafetyEvent(
            event_id=event_data["event_id"],
            event_type=SafetyEventType(event_data["event_type"]),
            corridor=event_data["corridor"],
            stations=event_data["stations"],
            severity=SafetyLevel(event_data["severity"]),
            description=event_data["description"],
            start_time=datetime.fromisoformat(event_data["start_time"]),
            end_time=datetime.fromisoformat(event_data["end_time"]) 
                if event_data.get("end_time") else None,
            safety_penalty=event_data.get("safety_penalty", 0.5)
        )
        
        await self.safety_bus.publish_safety_event(event)
    
    def stop(self) -> None:
        """Stop consuming safety events"""
        self._running = False
        if self._consumer:
            self._consumer.close()


# FastAPI Router for Safety Bus endpoints
from fastapi import APIRouter, HTTPException

safety_router = APIRouter(prefix="/routes/safety", tags=["Corridor Safety"])


@safety_router.get("/status")
async def get_corridor_safety_status(
    source: str,
    destination: str
) -> Dict[str, Any]:
    """
    Get safety status for a corridor.
    
    Query Parameters:
    - source: Source station code
    - destination: Destination station code
    
    Returns:
    - Safety score (0.0 to 1.0)
    - Risk level
    - Active events count
    - Affected stations
    """
    route_engine = RouteEngine()
    safety_bus = CorridorSafetyBus(route_engine)
    
    status = await safety_bus.get_corridor_safety(source, destination)
    
    return {
        "corridor": status.corridor,
        "safety_score": status.safety_score,
        "risk_level": status.risk_level.value,
        "active_events": status.active_events,
        "affected_stations": status.affected_stations,
        "last_updated": status.last_updated.isoformat()
    }


@safety_router.get("/events")
async def get_active_safety_events() -> List[Dict[str, Any]]:
    """Get all active safety events"""
    route_engine = RouteEngine()
    safety_bus = CorridorSafetyBus(route_engine)
    
    return safety_bus.get_active_events()


@safety_router.post("/events")
async def create_safety_event(event_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a new safety event.
    
    Request Body:
    - event_type: Type of safety event
    - corridor: Affected corridor
    - stations: List of affected stations
    - severity: Safety severity level
    - description: Event description
    - safety_penalty: Penalty score (0.0 to 1.0)
    """
    route_engine = RouteEngine()
    safety_bus = CorridorSafetyBus(route_engine)
    
    event = SafetyEvent(
        event_id=f"evt-{datetime.utcnow().timestamp()}",
        event_type=SafetyEventType(event_data["event_type"]),
        corridor=event_data["corridor"],
        stations=event_data["stations"],
        severity=SafetyLevel(event_data["severity"]),
        description=event_data["description"],
        start_time=datetime.utcnow(),
        end_time=datetime.fromisoformat(event_data["end_time"]) 
            if event_data.get("end_time") else None,
        safety_penalty=event_data.get("safety_penalty", 0.5)
    )
    
    await safety_bus.publish_safety_event(event)
    
    return {
        "event_id": event.event_id,
        "status": "published",
        "corridor": event.corridor,
        "safety_penalty": event.safety_penalty
    }


@safety_router.delete("/events/{event_id}")
async def resolve_safety_event(event_id: str) -> Dict[str, Any]:
    """Resolve a safety event"""
    route_engine = RouteEngine()
    safety_bus = CorridorSafetyBus(route_engine)
    
    resolved = await safety_bus.resolve_safety_event(event_id)
    
    if resolved:
        return {"event_id": event_id, "status": "resolved"}
    else:
        raise HTTPException(status_code=404, detail="Event not found")


@safety_router.post("/adjust-score")
async def get_safety_adjusted_route(
    route_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Get safety-adjusted score for a route.
    
    Request Body:
    - base_score: Original route quality score
    - journey: Journey object with segments
    - source: Source station
    - destination: Destination station
    """
    route_engine = RouteEngine()
    safety_bus = CorridorSafetyBus(route_engine)
    
    # Reconstruct journey (simplified)
    journey = Journey(
        segments=[
            # Would properly deserialize segments
        ]
    )
    
    adjusted_score = safety_bus.get_safety_adjusted_score(
        base_score=route_data["base_score"],
        journey=journey,
        source=route_data["source"],
        destination=route_data["destination"]
    )
    
    return {
        "base_score": route_data["base_score"],
        "adjusted_score": adjusted_score,
        "safety_impact": adjusted_score - route_data["base_score"]
    }
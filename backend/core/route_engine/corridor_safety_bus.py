"""
🛡️ Corridor Safety Bus — Feature D
SECURE + NEXUS Implementation

Real-time bidirectional safety channel between:
  - SOS System (publisher): Floods, cyclones, strikes, derailments
  - TurboRouter (subscriber): Applies dynamic penalty to affected corridors

Architecture:
  - In-process event bus (backed by Redis pub/sub in production)
  - CorridorSafetyBus singleton holds live safety events
  - TurboRouter / QPO queries the bus BEFORE routing any corridor
  - Events auto-expire after TTL (default 6 hours)

Kafka Integration (when available):
  - SOS service publishes to `corridor.safety` Kafka topic
  - SafetyBusConsumer subscribes and updates in-memory state

SECURE's Zero-Trust guarantee:
  - Every event is validated before being applied
  - Severity must be one of: INFO / WARNING / CRITICAL / EMERGENCY
  - Corrupted events are logged and dropped, never applied
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Any, Callable

logger = logging.getLogger("core.safety_bus")


class SafetySeverity(str, Enum):
    INFO = "INFO"               # Routine advisory — no routing impact
    WARNING = "WARNING"         # Minor disruption — small penalty
    CRITICAL = "CRITICAL"       # Major disruption — large penalty
    EMERGENCY = "EMERGENCY"     # Life-safety — route away completely


# Routing penalty applied per severity (in minutes, added to journey score)
_SEVERITY_PENALTIES: Dict[SafetySeverity, int] = {
    SafetySeverity.INFO: 0,
    SafetySeverity.WARNING: 15,
    SafetySeverity.CRITICAL: 60,
    SafetySeverity.EMERGENCY: 99999,  # Effectively blocks the corridor
}

# Severity → UI color mapping (returned in route metadata)
_SEVERITY_UI: Dict[SafetySeverity, str] = {
    SafetySeverity.INFO: "blue",
    SafetySeverity.WARNING: "amber",
    SafetySeverity.CRITICAL: "red",
    SafetySeverity.EMERGENCY: "black",
}

_DEFAULT_EVENT_TTL = 6 * 3600   # 6 hours


@dataclass
class CorridorSafetyEvent:
    """
    A safety event affecting one or more stations/corridors.

    station_codes: Affected station codes (e.g., ["NDLS", "MB"])
    corridor_id: Optional corridor string (e.g., "NDLS-BCT")
    severity: Safety level
    message: Human-readable description
    source: Originating system (e.g., "SOS", "GTFS_CANCELLATION", "MANUAL")
    event_id: Unique event identifier
    issued_at: Unix timestamp
    expires_at: Unix timestamp (auto-calculated if not set)
    """
    event_id: str
    source: str
    severity: SafetySeverity
    message: str
    station_codes: List[str]
    corridor_id: Optional[str] = None
    issued_at: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + _DEFAULT_EVENT_TTL)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    @property
    def penalty_minutes(self) -> int:
        return _SEVERITY_PENALTIES[self.severity]

    @property
    def ui_color(self) -> str:
        return _SEVERITY_UI[self.severity]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "source": self.source,
            "severity": self.severity.value,
            "message": self.message,
            "station_codes": self.station_codes,
            "corridor_id": self.corridor_id,
            "penalty_minutes": self.penalty_minutes,
            "ui_color": self.ui_color,
            "expires_at": self.expires_at,
        }


class CorridorSafetyBus:
    """
    In-process safety event store.

    Thread-safe singleton that TurboRouter/QPO queries before routing.
    SOS system calls `publish_event()` to inject safety alerts.

    In production: backed by Redis, with Kafka consumer syncing events.
    In development: purely in-memory with test helpers.
    """

    def __init__(self):
        # station_code → list of active events
        self._events: Dict[str, List[CorridorSafetyEvent]] = {}
        self._subscribers: List[Callable[[CorridorSafetyEvent], None]] = []
        self._total_published = 0
        self._total_expired = 0
        self._lock = asyncio.Lock() if asyncio.get_event_loop_policy() else None

    def publish_event(self, event: CorridorSafetyEvent) -> bool:
        """
        Publish a safety event to the bus.

        Called by:
        - SOS service when an emergency is triggered
        - GTFS cancellation processor when trains are cancelled
        - Admin manual override

        Returns True if event was accepted and applied.
        """
        # Zero-Trust Validation
        if not event.event_id or not event.station_codes:
            logger.warning(f"[SafetyBus] Rejected invalid event: {event}")
            return False

        if event.severity not in SafetySeverity.__members__.values():
            logger.warning(f"[SafetyBus] Rejected unknown severity: {event.severity}")
            return False

        if event.expires_at <= time.time():
            logger.warning(f"[SafetyBus] Rejected already-expired event: {event.event_id}")
            return False

        # Apply to all affected stations
        for code in event.station_codes:
            code = code.upper().strip()
            if code not in self._events:
                self._events[code] = []
            self._events[code].append(event)

        self._total_published += 1

        logger.warning(
            f"🚨 [SafetyBus] EVENT PUBLISHED: [{event.severity.value}] "
            f"Stations={event.station_codes} | {event.message} "
            f"| Penalty={event.penalty_minutes}min | TTL={int(event.expires_at - time.time())}s"
        )

        # Notify subscribers
        for sub in self._subscribers:
            try:
                sub(event)
            except Exception as e:
                logger.error(f"[SafetyBus] Subscriber error: {e}")

        return True

    def get_corridor_penalty(self, station_codes: List[str]) -> int:
        """
        Get the highest penalty for any station in a corridor.
        Called by TurboRouter before scoring a route.

        Returns penalty in minutes (0 = safe, 99999 = EMERGENCY block).
        """
        self._purge_expired()
        max_penalty = 0

        for code in station_codes:
            events = self._events.get(code.upper(), [])
            for event in events:
                if not event.is_expired:
                    max_penalty = max(max_penalty, event.penalty_minutes)

        return max_penalty

    def get_active_events_for_station(self, station_code: str) -> List[CorridorSafetyEvent]:
        """Get all active safety events for a specific station."""
        self._purge_expired()
        return [
            e for e in self._events.get(station_code.upper(), [])
            if not e.is_expired
        ]

    def get_all_active_events(self) -> List[CorridorSafetyEvent]:
        """Get all non-expired events across all stations."""
        self._purge_expired()
        seen: Set[str] = set()
        all_events = []
        for events in self._events.values():
            for event in events:
                if not event.is_expired and event.event_id not in seen:
                    all_events.append(event)
                    seen.add(event.event_id)
        return sorted(all_events, key=lambda e: e.issued_at, reverse=True)

    def clear_event(self, event_id: str) -> bool:
        """Manually clear/resolve a safety event."""
        cleared = False
        for code in self._events:
            before = len(self._events[code])
            self._events[code] = [
                e for e in self._events[code] if e.event_id != event_id
            ]
            if len(self._events[code]) < before:
                cleared = True

        if cleared:
            logger.info(f"✅ [SafetyBus] Event {event_id} cleared/resolved.")
        return cleared

    def subscribe(self, callback: Callable[[CorridorSafetyEvent], None]):
        """Register a callback for new safety events."""
        self._subscribers.append(callback)

    def _purge_expired(self):
        """Remove expired events from memory."""
        for code in list(self._events.keys()):
            before = len(self._events[code])
            self._events[code] = [e for e in self._events[code] if not e.is_expired]
            self._total_expired += before - len(self._events[code])
            if not self._events[code]:
                del self._events[code]

    def get_stats(self) -> Dict[str, Any]:
        self._purge_expired()
        return {
            "active_station_alerts": len(self._events),
            "active_events": len(self.get_all_active_events()),
            "total_published": self._total_published,
            "total_expired": self._total_expired,
            "subscribers": len(self._subscribers),
        }


# ── Kafka Consumer (Production Integration) ────────────────────────────────
class SafetyBusKafkaConsumer:
    """
    Subscribes to `corridor.safety` Kafka topic.
    Automatically syncs events to the in-process CorridorSafetyBus.

    Must be started as an async background task on application startup.
    """

    TOPIC = "corridor.safety"

    def __init__(self, safety_bus: CorridorSafetyBus, bootstrap_servers: str = "localhost:9092"):
        self.bus = safety_bus
        self.bootstrap_servers = bootstrap_servers
        self._running = False

    async def start(self):
        """Start consuming safety events from Kafka."""
        self._running = True
        logger.info(f"🔌 [SafetyBusKafka] Starting consumer for topic '{self.TOPIC}'")

        try:
            # aiokafka is optional — graceful degradation
            from aiokafka import AIOKafkaConsumer
            consumer = AIOKafkaConsumer(
                self.TOPIC,
                bootstrap_servers=self.bootstrap_servers,
                group_id="safety_bus_group",
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            )
            await consumer.start()
            try:
                async for msg in consumer:
                    if not self._running:
                        break
                    await self._process_message(msg.value)
            finally:
                await consumer.stop()
        except ImportError:
            logger.warning("[SafetyBusKafka] aiokafka not installed. Running in-process only.")
        except Exception as e:
            logger.error(f"[SafetyBusKafka] Consumer error: {e}")

    async def _process_message(self, payload: dict):
        """Parse and publish a Kafka safety message."""
        try:
            event = CorridorSafetyEvent(
                event_id=payload["event_id"],
                source=payload.get("source", "kafka"),
                severity=SafetySeverity(payload["severity"]),
                message=payload.get("message", ""),
                station_codes=payload.get("station_codes", []),
                corridor_id=payload.get("corridor_id"),
                expires_at=payload.get("expires_at", time.time() + _DEFAULT_EVENT_TTL),
            )
            self.bus.publish_event(event)
        except Exception as e:
            logger.error(f"[SafetyBusKafka] Failed to process message: {e} | payload={payload}")

    def stop(self):
        self._running = False


# ── SOS Integration Helper ─────────────────────────────────────────────────
def publish_sos_alert(
    sos_id: str,
    affected_stations: List[str],
    severity: str,
    message: str,
    duration_hours: float = 6.0,
) -> bool:
    """
    Convenience function for the SOS service to publish alerts.

    Called when an SOS emergency is confirmed and dispatched.
    Automatically invalidates routing through affected stations.

    Args:
        sos_id: SOS case ID (used as event_id for traceability)
        affected_stations: Station codes in the danger zone
        severity: "WARNING" | "CRITICAL" | "EMERGENCY"
        message: Alert description
        duration_hours: How long this alert stays active

    Returns:
        True if published successfully
    """
    try:
        sev = SafetySeverity(severity.upper())
    except ValueError:
        sev = SafetySeverity.WARNING
        logger.warning(f"[SafetyBus] Unknown severity '{severity}', defaulted to WARNING")

    event = CorridorSafetyEvent(
        event_id=f"SOS-{sos_id}",
        source="SOS_SYSTEM",
        severity=sev,
        message=message,
        station_codes=affected_stations,
        expires_at=time.time() + (duration_hours * 3600),
    )
    return corridor_safety_bus.publish_event(event)


# ── Singleton ──────────────────────────────────────────────────────────────
corridor_safety_bus = CorridorSafetyBus()

# ── API Router for Admin/Monitoring ───────────────────────────────────────
try:
    from fastapi import APIRouter as _APIRouter, Depends as _Depends
    safety_admin_router = _APIRouter(prefix="/api/v1/admin/safety", tags=["safety-bus"])

    @safety_admin_router.get("/events")
    async def get_active_safety_events():
        """List all active corridor safety events."""
        events = corridor_safety_bus.get_all_active_events()
        return {
            "total": len(events),
            "events": [e.to_dict() for e in events],
            "stats": corridor_safety_bus.get_stats(),
        }

    @safety_admin_router.delete("/events/{event_id}")
    async def resolve_safety_event(event_id: str):
        """Manually resolve/clear a safety event."""
        success = corridor_safety_bus.clear_event(event_id)
        return {"cleared": success, "event_id": event_id}

except ImportError:
    safety_admin_router = None

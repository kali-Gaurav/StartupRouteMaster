"""
Minimal Kafka Event Backbone for Railway Intelligence Engine

Phase 4 - Step 1: Only 3 events, single consumer, fire-and-forget
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime
import json
import time
import asyncio
import logging
from config import Config
from utils.metrics import EVENT_PUBLISH_LATENCY_MS, EVENT_PUBLISH_FAILURES_TOTAL, CIRCUIT_BREAKER_STATE, CIRCUIT_BREAKER_OPENS_TOTAL

logger = logging.getLogger(__name__)

# Event Schemas
class Event(ABC):
    """Base event class"""
    def __init__(self, event_type: str, timestamp: Optional[datetime] = None):
        self.event_type = event_type
        self.timestamp = timestamp or datetime.utcnow()
        self.version = "1.0"

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for JSON serialization"""
        return {
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "version": self.version
        }

class RouteSearchedEvent(Event):
    """Route search event for analytics"""
    def __init__(self,
                 user_id: Optional[str],
                 source: str,
                 destination: str,
                 travel_date: str,
                 routes_shown: int,
                 search_latency_ms: float,
                 filters: Optional[Dict[str, Any]] = None):
        super().__init__("RouteSearched")
        self.user_id = user_id
        self.source = source
        self.destination = destination
        self.travel_date = travel_date
        self.routes_shown = routes_shown
        self.search_latency_ms = search_latency_ms
        self.filters = filters or {}

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "user_id": self.user_id,
            "source": self.source,
            "destination": self.destination,
            "travel_date": self.travel_date,
            "routes_shown": self.routes_shown,
            "search_latency_ms": self.search_latency_ms,
            "filters": self.filters
        })
        return data

class BookingCreatedEvent(Event):
    """Booking creation event"""
    def __init__(self,
                 user_id: str,
                 route_id: str,
                 total_cost: float,
                 segments: list,
                 booking_reference: str):
        super().__init__("BookingCreated")
        self.user_id = user_id
        self.route_id = route_id
        self.total_cost = total_cost
        self.segments = segments
        self.booking_reference = booking_reference

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "user_id": self.user_id,
            "route_id": self.route_id,
            "total_cost": self.total_cost,
            "segments": self.segments,
            "booking_reference": self.booking_reference
        })
        return data

class TrainDelayedEvent(Event):
    """Train delay event for real-time updates"""
    def __init__(self,
                 train_id: str,
                 delay_minutes: int,
                 station_code: str,
                 scheduled_departure: str,
                 estimated_departure: str,
                 reason: Optional[str] = None):
        super().__init__("TrainDelayed")
        self.train_id = train_id
        self.delay_minutes = delay_minutes
        self.station_code = station_code
        self.scheduled_departure = scheduled_departure
        self.estimated_departure = estimated_departure
        self.reason = reason

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "train_id": self.train_id,
            "delay_minutes": self.delay_minutes,
            "station_code": self.station_code,
            "scheduled_departure": self.scheduled_departure,
            "estimated_departure": self.estimated_departure,
            "reason": self.reason
        })
        return data

# Event Producer Interface
class EventProducer(ABC):
    """Abstract event producer interface"""

    @abstractmethod
    async def publish_event(self, event: Event, topic: str) -> bool:
        """Publish event to topic. Returns success status."""
        pass

    @abstractmethod
    async def close(self):
        """Close producer connection"""
        pass

class KafkaEventProducer(EventProducer):
    """Kafka implementation of event producer with circuit breaker"""

    def __init__(self, bootstrap_servers: str = None, timeout_ms: int = 5000):
        self.bootstrap_servers = bootstrap_servers or Config.KAFKA_BOOTSTRAP_SERVERS or "localhost:9092"
        self.timeout_ms = timeout_ms
        self.producer = None
        self.circuit_breaker_failures = 0
        self.circuit_breaker_threshold = 5
        self.circuit_breaker_open = False
        self.last_failure_time = None
        self.circuit_breaker_recovery_timeout = 30  # seconds

        # Metrics for observability
        self.metrics = {
            'publish_attempts': 0,
            'publish_successes': 0,
            'publish_failures': 0,
            'circuit_breaker_opens': 0,
            'send_latencies_ms': [],  # List of latencies for P95 calculation
        }

    async def _ensure_producer(self):
        """Lazy initialization of Kafka producer"""
        if self.producer is None:
            try:
                # Import here to avoid hard dependency
                from aiokafka import AIOKafkaProducer
                self.producer = AIOKafkaProducer(
                    bootstrap_servers=self.bootstrap_servers,
                    value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                    request_timeout_ms=self.timeout_ms,
                    # Minimal backbone configuration: low blocking, low durability
                    acks=1,  # Wait for leader ack only (not all replicas)
                    max_batch_size=16384,  # 16KB batches
                    linger_ms=5,  # Small linger for batching
                    compression_type='gzip',  # Compress for efficiency
                )
                await self.producer.start()
                logger.info(f"Kafka producer connected to {self.bootstrap_servers}")
            except Exception as e:
                logger.error(f"Failed to create Kafka producer: {e}")
                self.producer = None
                raise

    def _check_circuit_breaker(self) -> bool:
        """Check if circuit breaker allows requests"""
        if not self.circuit_breaker_open:
            return True

        # Check if recovery timeout has passed
        if self.last_failure_time and \
           (datetime.utcnow() - self.last_failure_time).total_seconds() > self.circuit_breaker_recovery_timeout:
            logger.info("Circuit breaker recovery timeout passed, attempting to close circuit")
            self.circuit_breaker_open = False
            self.circuit_breaker_failures = 0
            return True

        return False

    def _record_failure(self):
        """Record a failure for circuit breaker"""
        self.circuit_breaker_failures += 1
        self.last_failure_time = datetime.utcnow()

        if self.circuit_breaker_failures >= self.circuit_breaker_threshold:
            logger.warning(f"Circuit breaker opened after {self.circuit_breaker_failures} failures")
            self.circuit_breaker_open = True
            self.metrics['circuit_breaker_opens'] += 1
            # Record circuit breaker open metric
            if CIRCUIT_BREAKER_OPENS_TOTAL is not None:
                CIRCUIT_BREAKER_OPENS_TOTAL.inc()

    def _record_success(self):
        """Record a success to reset circuit breaker"""
        if self.circuit_breaker_failures > 0:
            self.circuit_breaker_failures = 0
            logger.info("Circuit breaker reset after successful operation")

    async def publish_event(self, event: Event, topic: str) -> bool:
        """Publish event with circuit breaker protection - TRUE FIRE-AND-FORGET"""
        self.metrics['publish_attempts'] += 1

        if not self._check_circuit_breaker():
            logger.warning(f"Circuit breaker open, skipping event publish to {topic}")
            self.metrics['publish_failures'] += 1
            # Record circuit breaker state
            if CIRCUIT_BREAKER_STATE is not None:
                CIRCUIT_BREAKER_STATE.set(1)  # Open
            return False

        # Record circuit breaker state as closed
        if CIRCUIT_BREAKER_STATE is not None:
            CIRCUIT_BREAKER_STATE.set(0)  # Closed

        try:
            await self._ensure_producer()

            # Measure send latency (time to queue message)
            start_time = time.time()
            # TRUE fire-and-forget: send without waiting for ack
            # Circuit breaker protects against overwhelming the producer
            await self.producer.send(topic, event.to_dict())
            latency_ms = (time.time() - start_time) * 1000
            self.metrics['send_latencies_ms'].append(latency_ms)

            # Record Prometheus metrics
            if EVENT_PUBLISH_LATENCY_MS is not None:
                EVENT_PUBLISH_LATENCY_MS.observe(latency_ms)

            self._record_success()
            self.metrics['publish_successes'] += 1
            logger.debug(f"Published {event.event_type} event to {topic}")
            return True

        except Exception as e:
            logger.error(f"Failed to publish {event.event_type} to {topic}: {e}")
            self._record_failure()
            self.metrics['publish_failures'] += 1
            
            # Record failure metrics
            if EVENT_PUBLISH_FAILURES_TOTAL is not None:
                EVENT_PUBLISH_FAILURES_TOTAL.labels(topic=topic, error_type=type(e).__name__).inc()
            
            return False

    async def close(self):
        """Close producer connection"""
        if self.producer:
            await self.producer.stop()
            self.producer = None
            logger.info("Kafka producer closed")

    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics for observability"""
        latencies = self.metrics['send_latencies_ms']
        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0
        return {
            **self.metrics,
            'send_p95_latency_ms': p95_latency,
            'circuit_breaker_currently_open': self.circuit_breaker_open,
            'circuit_breaker_current_failures': self.circuit_breaker_failures,
        }

    def reset_circuit_breaker(self):
        """Reset circuit breaker for testing"""
        self.circuit_breaker_open = False
        self.circuit_breaker_failures = 0
        self.last_failure_time = None
        self.metrics = {
            'publish_attempts': 0,
            'publish_successes': 0,
            'publish_failures': 0,
            'circuit_breaker_opens': 0,
            'send_latencies_ms': [],
        }

class InMemoryEventProducer(EventProducer):
    """In-memory fallback producer for testing/development"""

    def __init__(self):
        self.events: Dict[str, list] = {}
        logger.info("Using in-memory event producer (fallback mode)")

    async def publish_event(self, event: Event, topic: str) -> bool:
        """Store event in memory"""
        if topic not in self.events:
            self.events[topic] = []
        self.events[topic].append(event.to_dict())
        logger.debug(f"Stored {event.event_type} event in memory for topic {topic}")
        return True

    async def close(self):
        """No-op for in-memory producer"""
        pass

    def get_events(self, topic: str) -> list:
        """Get stored events for topic (for testing)"""
        return self.events.get(topic, [])

# Global producer instance
_event_producer: Optional[EventProducer] = None

def get_event_producer() -> EventProducer:
    """Get or create event producer instance"""
    global _event_producer
    if _event_producer is None:
        # Try Kafka first, fallback to in-memory
        try:
            _event_producer = KafkaEventProducer()
        except Exception as e:
            logger.warning(f"Failed to create Kafka producer, using in-memory fallback: {e}")
            _event_producer = InMemoryEventProducer()
    return _event_producer

class GenericEvent(Event):
    """Generic event for arbitrary data"""
    def __init__(self, event_type: str, data: Dict[str, Any]):
        super().__init__(event_type)
        self.data = data

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update(self.data)
        return d

async def publish_event(event_type: str, data: Dict[str, Any]) -> bool:
    """Publish a generic event."""
    event = GenericEvent(event_type, data)
    return await get_event_producer().publish_event(event, f"{event_type}_events")

# Convenience functions for publishing events
async def publish_route_searched(user_id: Optional[str], source: str, destination: str,
                               travel_date: str, routes_shown: int, search_latency_ms: float,
                               filters: Optional[Dict[str, Any]] = None) -> bool:
    """Publish route search event"""
    event = RouteSearchedEvent(user_id, source, destination, travel_date,
                             routes_shown, search_latency_ms, filters)
    return await get_event_producer().publish_event(event, "route_events")

async def publish_booking_created(user_id: str, route_id: str, total_cost: float,
                                segments: list, booking_reference: str) -> bool:
    """Publish booking creation event"""
    event = BookingCreatedEvent(user_id, route_id, total_cost, segments, booking_reference)
    return await get_event_producer().publish_event(event, "booking_events")

async def publish_train_delayed(train_id: str, delay_minutes: int, station_code: str,
                              scheduled_departure: str, estimated_departure: str,
                              reason: Optional[str] = None) -> bool:
    """Publish train delay event"""
    event = TrainDelayedEvent(train_id, delay_minutes, station_code,
                            scheduled_departure, estimated_departure, reason)
    return await get_event_producer().publish_event(event, "delay_events")

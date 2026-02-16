"""
Real-Time Graph Mutation Engine - Train State Service

Manages live train state and applies real-time mutations to the routing graph.
Handles delays, cancellations, platform changes, and occupancy updates.

Key Features:
- Redis-backed fast state store
- PostgreSQL persistent state
- Graph delta application
- Cache invalidation
- Event-driven updates
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
import logging

from redis.asyncio import Redis
from sqlalchemy import and_, or_, update
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import Trip, StopTime, Stop
from .config import Config

logger = logging.getLogger(__name__)


@dataclass
class TrainState:
    """Live state of a train"""
    trip_id: int
    train_number: str
    current_station_id: Optional[int] = None
    next_station_id: Optional[int] = None
    delay_minutes: int = 0
    status: str = "on_time"  # on_time, delayed, cancelled, running_late
    platform_number: Optional[str] = None
    last_updated: datetime = None
    estimated_arrival: Optional[datetime] = None
    estimated_departure: Optional[datetime] = None
    occupancy_rate: float = 0.0  # 0.0 to 1.0
    cancelled_stations: List[int] = None  # List of cancelled stop IDs

    def __post_init__(self):
        if self.last_updated is None:
            self.last_updated = datetime.utcnow()
        if self.cancelled_stations is None:
            self.cancelled_stations = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Redis storage"""
        data = asdict(self)
        # Convert datetime to ISO string
        if self.last_updated:
            data['last_updated'] = self.last_updated.isoformat()
        if self.estimated_arrival:
            data['estimated_arrival'] = self.estimated_arrival.isoformat()
        if self.estimated_departure:
            data['estimated_departure'] = self.estimated_departure.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TrainState':
        """Create from dictionary (Redis data)"""
        # Convert ISO strings back to datetime
        if 'last_updated' in data and data['last_updated']:
            data['last_updated'] = datetime.fromisoformat(data['last_updated'])
        if 'estimated_arrival' in data and data['estimated_arrival']:
            data['estimated_arrival'] = datetime.fromisoformat(data['estimated_arrival'])
        if 'estimated_departure' in data and data['estimated_departure']:
            data['estimated_departure'] = datetime.fromisoformat(data['estimated_departure'])
        return cls(**data)


class TrainStateStore:
    """Dual-storage train state management (Redis + PostgreSQL)"""

    def __init__(self):
        self.redis: Optional[Redis] = None
        self.ttl_seconds = 3600 * 24  # 24 hours

    async def initialize(self):
        """Initialize Redis connection"""
        if not self.redis:
            self.redis = Redis.from_url(Config.REDIS_URL, decode_responses=True)
            await self.redis.ping()  # Test connection

    async def get_train_state(self, trip_id: int) -> Optional[TrainState]:
        """Get train state from Redis (fast path)"""
        if not self.redis:
            await self.initialize()

        key = f"train_state:{trip_id}"
        data = await self.redis.get(key)

        if data:
            try:
                state_dict = json.loads(data)
                return TrainState.from_dict(state_dict)
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Invalid train state data for trip {trip_id}: {e}")
                return None

        # Fallback to database
        return self._get_train_state_from_db(trip_id)

    def _get_train_state_from_db(self, trip_id: int) -> Optional[TrainState]:
        """Get train state from PostgreSQL (slow path)"""
        session = SessionLocal()
        try:
            # Check if we have a train_state table (to be created)
            # For now, return default state
            return TrainState(trip_id=trip_id, train_number=str(trip_id))
        except Exception as e:
            logger.error(f"Error getting train state from DB for trip {trip_id}: {e}")
            return None
        finally:
            session.close()

    async def update_train_state(self, state: TrainState):
        """Update train state in both Redis and PostgreSQL"""
        if not self.redis:
            await self.initialize()

        # Update Redis (fast storage)
        key = f"train_state:{state.trip_id}"
        data = json.dumps(state.to_dict())
        await self.redis.setex(key, self.ttl_seconds, data)

        # Update PostgreSQL (persistent storage)
        self._persist_train_state(state)

        # Publish update event for graph mutation
        await self._publish_state_update(state)

        logger.info(f"Updated train state for trip {state.trip_id}: delay={state.delay_minutes}min, status={state.status}")

    def _persist_train_state(self, state: TrainState):
        """Persist train state to PostgreSQL"""
        # This will be implemented when we create the train_state table
        # For now, just log
        logger.debug(f"Persisting train state for trip {state.trip_id}")

    async def _publish_state_update(self, state: TrainState):
        """Publish state update to Kafka for graph mutation"""
        # This will integrate with Kafka
        logger.debug(f"Publishing state update for trip {state.trip_id}")

    async def get_all_active_trains(self) -> List[TrainState]:
        """Get all trains that are currently active/running"""
        if not self.redis:
            await self.initialize()

        # Get all train state keys
        pattern = "train_state:*"
        keys = await self.redis.keys(pattern)

        states = []
        for key in keys:
            data = await self.redis.get(key)
            if data:
                try:
                    state_dict = json.loads(data)
                    state = TrainState.from_dict(state_dict)
                    # Only include active trains
                    if state.status in ['on_time', 'delayed', 'running_late']:
                        states.append(state)
                except Exception as e:
                    logger.warning(f"Error parsing train state from key {key}: {e}")

        return states

    async def apply_delay(self, trip_id: int, delay_minutes: int, reason: str = ""):
        """Apply delay to a train"""
        state = await self.get_train_state(trip_id)
        if not state:
            state = TrainState(trip_id=trip_id, train_number=str(trip_id))

        state.delay_minutes = delay_minutes
        state.status = 'delayed' if delay_minutes > 0 else 'on_time'
        state.last_updated = datetime.utcnow()

        await self.update_train_state(state)

        logger.info(f"Applied {delay_minutes}min delay to trip {trip_id}, reason: {reason}")

    async def cancel_train(self, trip_id: int, cancelled_stations: List[int] = None):
        """Cancel a train"""
        state = await self.get_train_state(trip_id)
        if not state:
            state = TrainState(trip_id=trip_id, train_number=str(trip_id))

        state.status = 'cancelled'
        state.cancelled_stations = cancelled_stations or []
        state.last_updated = datetime.utcnow()

        await self.update_train_state(state)

        logger.info(f"Cancelled trip {trip_id}")

    async def update_location(self, trip_id: int, current_station_id: int,
                            next_station_id: Optional[int] = None):
        """Update train's current location"""
        state = await self.get_train_state(trip_id)
        if not state:
            state = TrainState(trip_id=trip_id, train_number=str(trip_id))

        state.current_station_id = current_station_id
        state.next_station_id = next_station_id
        state.last_updated = datetime.utcnow()

        await self.update_train_state(state)

        logger.debug(f"Updated location for trip {trip_id}: station {current_station_id}")


class GraphMutationEngine:
    """Applies real-time mutations to the routing graph"""

    def __init__(self, route_engine):
        self.route_engine = route_engine
        self.train_state_store = TrainStateStore()
        self.mutation_cache = {}  # Cache of applied mutations

    async def initialize(self):
        """Initialize the mutation engine"""
        await self.train_state_store.initialize()

    async def apply_train_delay(self, trip_id: int, delay_minutes: int):
        """Apply delay mutation to graph"""
        # Get affected segments
        affected_segments = await self._get_affected_segments(trip_id)

        # Apply delay to each segment
        for segment in affected_segments:
            segment.departure_time += timedelta(minutes=delay_minutes)
            segment.arrival_time += timedelta(minutes=delay_minutes)

        # Update graph
        await self._update_graph_segments(trip_id, affected_segments)

        # Invalidate affected caches
        await self._invalidate_affected_caches(trip_id)

        logger.info(f"Applied {delay_minutes}min delay to {len(affected_segments)} segments for trip {trip_id}")

    async def apply_train_cancellation(self, trip_id: int, cancelled_stations: List[int] = None):
        """Apply cancellation mutation to graph"""
        # Mark segments as cancelled
        affected_segments = await self._get_affected_segments(trip_id)

        for segment in affected_segments:
            if cancelled_stations and segment.arrival_stop_id not in cancelled_stations:
                continue
            segment.is_cancelled = True

        # Update graph
        await self._update_graph_segments(trip_id, affected_segments)

        # Invalidate caches
        await self._invalidate_affected_caches(trip_id)

        logger.info(f"Cancelled {len(affected_segments)} segments for trip {trip_id}")

    async def _get_affected_segments(self, trip_id: int) -> List[Any]:
        """Get all route segments affected by a train change"""
        # This would query the route engine's graph
        # For now, return empty list
        return []

    async def _update_graph_segments(self, trip_id: int, segments: List[Any]):
        """Update graph with modified segments"""
        # Apply changes to the live graph
        # This would update the route engine's graph structure
        pass

    async def _invalidate_affected_caches(self, trip_id: int):
        """Invalidate caches for affected routes"""
        # Get stations affected by this train
        affected_stations = await self._get_affected_stations(trip_id)

        # Invalidate route caches for these stations
        for station_id in affected_stations:
            await self._invalidate_station_cache(station_id)

        logger.debug(f"Invalidated caches for {len(affected_stations)} stations")

    async def _get_affected_stations(self, trip_id: int) -> List[int]:
        """Get all stations affected by a train change"""
        # Query database for stations this train serves
        session = SessionLocal()
        try:
            stop_times = session.query(StopTime).filter(
                StopTime.trip_id == trip_id
            ).all()

            return list(set(st.stop_id for st in stop_times))
        finally:
            session.close()

    async def _invalidate_station_cache(self, station_id: int):
        """Invalidate cache for a specific station"""
        # This would clear Redis caches for this station
        # Implementation depends on caching strategy
        pass

    async def process_realtime_update(self, update_data: Dict[str, Any]):
        """Process real-time update from external sources"""
        update_type = update_data.get('type')

        if update_type == 'delay':
            trip_id = update_data['trip_id']
            delay_minutes = update_data['delay_minutes']
            await self.apply_train_delay(trip_id, delay_minutes)

        elif update_type == 'cancellation':
            trip_id = update_data['trip_id']
            cancelled_stations = update_data.get('cancelled_stations', [])
            await self.apply_train_cancellation(trip_id, cancelled_stations)

        elif update_type == 'location':
            trip_id = update_data['trip_id']
            current_station = update_data['current_station_id']
            next_station = update_data.get('next_station_id')
            await self.train_state_store.update_location(trip_id, current_station, next_station)

        logger.info(f"Processed {update_type} update for trip {update_data.get('trip_id')}")


# Global instances
train_state_store = TrainStateStore()
graph_mutation_engine = None  # Will be initialized with route engine

async def initialize_graph_mutation(route_engine):
    """Initialize the graph mutation engine"""
    global graph_mutation_engine
    graph_mutation_engine = GraphMutationEngine(route_engine)
    await graph_mutation_engine.initialize()
    return graph_mutation_engine
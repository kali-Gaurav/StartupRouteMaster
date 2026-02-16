"""
Availability Service - Seat Inventory Management

Handles seat availability checking, allocation, and quota management.
Implements IRCTC-grade inventory logic with segment-based allocation.

Key Features:
- Segment overlap detection
- Quota-based seat allocation
- Waitlist management
- Real-time availability updates
- High-performance Redis caching
"""

import asyncio
import json
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple, Set, Any
from dataclasses import dataclass
import logging

from sqlalchemy import and_, or_, func, update, select
from sqlalchemy.orm import Session, joinedload
import redis.asyncio as redis

from .database import SessionLocal
from .seat_inventory_models import (
    SeatInventory, QuotaInventory, WaitlistQueue, Coach, Seat,
    QuotaType, BookingStatus, CoachClass
)
from .models import StopTime
from .config import Config
from .services.multi_layer_cache import multi_layer_cache, AvailabilityQuery, cache_availability_check

logger = logging.getLogger(__name__)


@dataclass
class AvailabilityRequest:
    """Request for seat availability check"""
    trip_id: int
    from_stop_id: int
    to_stop_id: int
    travel_date: date
    quota_type: QuotaType
    passengers: int = 1

@dataclass
class AvailabilityResponse:
    """Response for availability check"""
    available: bool
    available_seats: int
    total_seats: int
    waitlist_position: Optional[int] = None
    confirmation_probability: Optional[float] = None
    message: str = ""

@dataclass
class SeatAllocation:
    """Seat allocation result"""
    inventory_id: str
    seat_ids: List[str]
    coach_number: str
    quota_type: QuotaType
    allocated_at: datetime


class AvailabilityService:
    """Core service for seat availability and allocation"""

    def __init__(self):
        self.redis: Optional[redis.Redis] = None
        self.cache_ttl = 300  # 5 minutes

    async def initialize(self):
        """Initialize Redis connection"""
        if not self.redis:
            self.redis = redis.Redis.from_url(Config.REDIS_URL, decode_responses=True)
            await self.redis.ping()

    async def check_availability(self, request: AvailabilityRequest) -> AvailabilityResponse:
        """Check seat availability for a segment with multi-layer caching"""
        await self.initialize()
        await multi_layer_cache.initialize()

        # Create cache query
        cache_query = AvailabilityQuery(
            train_id=request.trip_id,
            from_stop_id=request.from_stop_id,
            to_stop_id=request.to_stop_id,
            travel_date=request.travel_date,
            quota_type=request.quota_type.value,
            passengers=request.passengers
        )

        # Use cached availability check
        async def compute_availability():
            response = await self._check_availability_db(request)
            return response.__dict__

        cached_result = await multi_layer_cache.get_availability(cache_query)
        if cached_result:
            return AvailabilityResponse(**cached_result)

        # Compute and cache
        response = await self._check_availability_db(request)
        await multi_layer_cache.set_availability(cache_query, response.__dict__)

        return response

    async def _check_availability_db(self, request: AvailabilityRequest) -> AvailabilityResponse:
        """Check availability in database"""
        session = SessionLocal()
        try:
            # Find all segments that overlap with the requested segment
            overlapping_segments = await self._find_overlapping_segments(
                session, request.trip_id, request.from_stop_id, request.to_stop_id, request.travel_date
            )

            if not overlapping_segments:
                return AvailabilityResponse(
                    available=False,
                    available_seats=0,
                    total_seats=0,
                    message="No inventory found for this segment"
                )

            # Check availability for each overlapping segment
            min_available = float('inf')
            total_seats = 0

            for segment in overlapping_segments:
                # Get quota-specific availability
                quota_inventory = session.query(QuotaInventory).filter(
                    and_(
                        QuotaInventory.inventory_id == segment.id,
                        QuotaInventory.quota_type == request.quota_type
                    )
                ).first()

                if quota_inventory:
                    available = quota_inventory.available_seats
                    min_available = min(min_available, available)
                    total_seats += quota_inventory.max_allocation
                else:
                    # No specific quota allocation, use general inventory
                    available = segment.available_seats
                    min_available = min(min_available, available)
                    total_seats += segment.total_seats

            available_seats = int(min_available) if min_available != float('inf') else 0

            # Check if we have enough seats
            if available_seats >= request.passengers:
                return AvailabilityResponse(
                    available=True,
                    available_seats=available_seats,
                    total_seats=total_seats,
                    confirmation_probability=1.0,
                    message=f"{available_seats} seats available"
                )
            else:
                # Check waitlist
                waitlist_position = await self._get_waitlist_position(
                    session, overlapping_segments[0].id, request.passengers
                )

                # Calculate confirmation probability (simplified)
                probability = self._calculate_confirmation_probability(
                    available_seats, request.passengers, waitlist_position
                )

                return AvailabilityResponse(
                    available=False,
                    available_seats=available_seats,
                    total_seats=total_seats,
                    waitlist_position=waitlist_position,
                    confirmation_probability=probability,
                    message=f"Waitlist position {waitlist_position}"
                )

        finally:
            session.close()

    async def allocate_seats(self, request: AvailabilityRequest, user_id: str,
                           session_id: str) -> Optional[SeatAllocation]:
        """Allocate seats for booking"""
        await self.initialize()

        session = SessionLocal()
        try:
            # Find overlapping segments
            overlapping_segments = await self._find_overlapping_segments(
                session, request.trip_id, request.from_stop_id, request.to_stop_id, request.travel_date
            )

            if not overlapping_segments:
                return None

            # Try to allocate from each segment
            allocated_seats = []
            coach_number = None

            for segment in overlapping_segments:
                allocation = await self._allocate_from_segment(
                    session, segment, request.quota_type, request.passengers, user_id, session_id
                )

                if allocation:
                    allocated_seats.extend(allocation['seat_ids'])
                    if not coach_number:
                        coach_number = allocation['coach_number']
                else:
                    # Allocation failed, rollback previous allocations
                    await self._rollback_allocations(session, allocated_seats)
                    return None

            # Create allocation result
            return SeatAllocation(
                inventory_id=overlapping_segments[0].id,
                seat_ids=allocated_seats,
                coach_number=coach_number or "TBD",
                quota_type=request.quota_type,
                allocated_at=datetime.utcnow()
            )

        finally:
            session.close()

    async def _allocate_from_segment(self, session: Session, segment: SeatInventory,
                                   quota_type: QuotaType, passengers: int,
                                   user_id: str, session_id: str) -> Optional[Dict]:
        """Allocate seats from a specific segment"""
        # Get quota inventory
        quota_inventory = session.query(QuotaInventory).filter(
            and_(
                QuotaInventory.inventory_id == segment.id,
                QuotaInventory.quota_type == quota_type
            )
        ).first()

        if not quota_inventory or quota_inventory.available_seats < passengers:
            return None

        # Find available seats in coaches
        available_seats = await self._find_available_seats(session, segment, passengers)

        if len(available_seats) < passengers:
            return None

        # Allocate seats
        allocated_seat_ids = []
        coach_number = None

        for seat in available_seats[:passengers]:
            # Lock the seat
            lock_key = f"seat:{segment.trip_id}:{segment.date}:{seat.coach.coach_number}-{seat.seat_number}"
            lock_acquired = await self._acquire_seat_lock(lock_key, user_id, session_id, 60)

            if not lock_acquired:
                # Rollback previous locks
                for prev_seat_id in allocated_seat_ids:
                    await self._release_seat_lock(prev_seat_id, session_id)
                return None

            allocated_seat_ids.append(seat.id)
            if not coach_number:
                coach_number = seat.coach.coach_number

        # Update inventory counts
        quota_inventory.available_seats -= passengers
        quota_inventory.allocated_seats += passengers
        segment.booked_seats += passengers
        segment.available_seats -= passengers

        session.commit()

        # Invalidate cache
        await self._invalidate_availability_cache(segment)

        return {
            'seat_ids': allocated_seat_ids,
            'coach_number': coach_number
        }

    async def release_seats(self, seat_ids: List[str], session_id: str):
        """Release allocated seats"""
        await self.initialize()

        session = SessionLocal()
        try:
            for seat_id in seat_ids:
                # Find the seat and its inventory
                seat = session.query(Seat).filter(Seat.id == seat_id).first()
                if seat:
                    # Find related inventory segments
                    inventory_items = session.query(SeatInventory).filter(
                        SeatInventory.seat_id == seat_id
                    ).all()

                    for inventory in inventory_items:
                        # Update counts
                        inventory.booked_seats -= 1
                        inventory.available_seats += 1

                        # Update quota inventory
                        quota_inventory = session.query(QuotaInventory).filter(
                            QuotaInventory.inventory_id == inventory.id
                        ).first()

                        if quota_inventory:
                            quota_inventory.available_seats += 1
                            quota_inventory.allocated_seats -= 1

                    # Release lock
                    lock_key = f"seat:{seat.coach.train_id}:*:{seat.coach.coach_number}-{seat.seat_number}"
                    await self._release_seat_lock_by_pattern(lock_key, session_id)

            session.commit()

        finally:
            session.close()

    async def add_to_waitlist(self, request: AvailabilityRequest, user_id: str,
                            passengers_json: Dict, preferences_json: Optional[Dict] = None) -> int:
        """Add booking request to waitlist"""
        session = SessionLocal()
        try:
            # Find the inventory
            inventory = session.query(SeatInventory).filter(
                and_(
                    SeatInventory.trip_id == request.trip_id,
                    SeatInventory.segment_from_stop_id == request.from_stop_id,
                    SeatInventory.segment_to_stop_id == request.to_stop_id,
                    SeatInventory.date == request.travel_date,
                    SeatInventory.quota_type == request.quota_type
                )
            ).first()

            if not inventory:
                raise ValueError("Inventory not found")

            # Get next waitlist position
            max_position = session.query(func.max(WaitlistQueue.waitlist_position)).filter(
                WaitlistQueue.inventory_id == inventory.id
            ).scalar() or 0

            waitlist_position = max_position + 1

            # Create waitlist entry
            waitlist_entry = WaitlistQueue(
                inventory_id=inventory.id,
                user_id=user_id,
                waitlist_position=waitlist_position,
                passengers_json=passengers_json,
                preferences_json=preferences_json,
                status=BookingStatus.WAITLIST
            )

            session.add(waitlist_entry)
            session.commit()

            # Update inventory waitlist count
            inventory.current_waitlist_position = waitlist_position
            session.commit()

            return waitlist_position

        finally:
            session.close()

    async def promote_waitlist(self, inventory_id: str, seats_freed: int):
        """Promote waitlist entries when seats become available"""
        session = SessionLocal()
        try:
            # Find waitlist entries to promote
            waitlist_entries = session.query(WaitlistQueue).filter(
                and_(
                    WaitlistQueue.inventory_id == inventory_id,
                    WaitlistQueue.status == BookingStatus.WAITLIST
                )
            ).order_by(WaitlistQueue.waitlist_position).limit(seats_freed).all()

            promoted_count = 0
            for entry in waitlist_entries:
                # Try to allocate seats for this entry
                # This would trigger the booking orchestrator
                # For now, just mark as promoted
                entry.status = BookingStatus.RAC
                entry.promoted_at = datetime.utcnow()
                promoted_count += 1

            if promoted_count > 0:
                session.commit()
                logger.info(f"Promoted {promoted_count} waitlist entries for inventory {inventory_id}")

        finally:
            session.close()

    async def _find_overlapping_segments(self, session: Session, trip_id: int,
                                       from_stop_id: int, to_stop_id: int,
                                       travel_date: date) -> List[SeatInventory]:
        """Find all inventory segments that overlap with the requested segment"""
        # Get all stop times for this trip
        stop_times = session.query(StopTime).filter(
            StopTime.trip_id == trip_id
        ).order_by(StopTime.stop_sequence).all()

        # Find segments that overlap with [from_stop_id, to_stop_id]
        overlapping_segments = []

        for i, stop_time in enumerate(stop_times):
            if stop_time.stop_id == from_stop_id:
                # Find the corresponding to_stop
                for j in range(i + 1, len(stop_times)):
                    if stop_times[j].stop_id == to_stop_id:
                        # This is an overlapping segment
                        segment = session.query(SeatInventory).filter(
                            and_(
                                SeatInventory.trip_id == trip_id,
                                SeatInventory.segment_from_stop_id == from_stop_id,
                                SeatInventory.segment_to_stop_id == to_stop_id,
                                SeatInventory.date == travel_date
                            )
                        ).first()

                        if segment:
                            overlapping_segments.append(segment)
                        break
                break

        return overlapping_segments

    async def _find_available_seats(self, session: Session, segment: SeatInventory,
                                  count: int) -> List[Seat]:
        """Find available seats in coaches for this segment"""
        # Get coaches for this train
        coaches = session.query(Coach).filter(Coach.train_id == segment.trip_id).all()

        available_seats = []
        for coach in coaches:
            # Find seats that are not booked for this segment
            # This is a simplified version - in reality, we'd need to check
            # seat bookings across all overlapping segments
            seats = session.query(Seat).filter(
                and_(
                    Seat.coach_id == coach.id,
                    Seat.is_active == True
                )
            ).limit(count - len(available_seats)).all()

            available_seats.extend(seats)
            if len(available_seats) >= count:
                break

        return available_seats[:count]

    async def _get_waitlist_position(self, session: Session, inventory_id: str, passengers: int) -> int:
        """Get current waitlist position"""
        max_position = session.query(func.max(WaitlistQueue.waitlist_position)).filter(
            WaitlistQueue.inventory_id == inventory_id
        ).scalar() or 0

        return max_position + 1

    def _calculate_confirmation_probability(self, available: int, requested: int, waitlist_pos: int) -> float:
        """Calculate confirmation probability for waitlist"""
        if available >= requested:
            return 1.0
        elif waitlist_pos <= 5:
            return 0.8  # High chance for top waitlist
        elif waitlist_pos <= 20:
            return 0.4  # Medium chance
        else:
            return 0.1  # Low chance

    async def _acquire_seat_lock(self, lock_key: str, user_id: str, session_id: str, ttl: int) -> bool:
        """Acquire distributed lock for seat"""
        lock_data = {
            'user_id': user_id,
            'session_id': session_id,
            'acquired_at': datetime.utcnow().isoformat(),
            'expires_at': (datetime.utcnow() + timedelta(seconds=ttl)).isoformat()
        }

        # Try to set lock with NX (only if not exists)
        result = await self.redis.set(lock_key, json.dumps(lock_data), ex=ttl, nx=True)
        return result is not None

    async def _release_seat_lock(self, seat_id: str, session_id: str):
        """Release seat lock"""
        # Find lock key pattern
        lock_key = f"seat:*:{seat_id}"
        await self._release_seat_lock_by_pattern(lock_key, session_id)

    async def _release_seat_lock_by_pattern(self, lock_key_pattern: str, session_id: str):
        """Release lock by pattern"""
        # This is a simplified version - in production, you'd use Redis scripting
        # to safely release only locks owned by this session
        await self.redis.delete(lock_key_pattern)

    def _get_availability_cache_key(self, request: AvailabilityRequest) -> str:
        """Generate cache key for availability check"""
        return f"availability:{request.trip_id}:{request.from_stop_id}:{request.to_stop_id}:{request.travel_date}:{request.quota_type.value}"

    async def _invalidate_availability_cache(self, segment: SeatInventory):
        """Invalidate availability cache for a segment using multi-layer cache"""
        await multi_layer_cache.invalidate_availability(segment.trip_id, segment.date)

    async def _rollback_allocations(self, session: Session, seat_ids: List[str]):
        """Rollback seat allocations"""
        # This would release locks and update inventory counts
        # Implementation depends on how allocations are tracked
        pass


# Global instance
availability_service = AvailabilityService()
"""
Inventory Service - Phase 5 Seat Locking
Handles atomic reservation and release of train seat inventory.
With circuit breaker protection, distributed locking, and comprehensive error handling.
"""

import logging
from datetime import datetime, timedelta, date
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import Optional, Dict, Any
from dataclasses import dataclass
from collections import deque
from contextlib import contextmanager

from database.models import SeatAvailability as SeatInventory, AuditLog
from services.cache_service import cache_service
from core.resilience.core import circuit_manager as circuit_breaker_manager
from core.resilience.retry import retry_sync

logger = logging.getLogger(__name__)


@dataclass
class InventoryConfig:
    """Configuration for inventory service."""
    lock_minutes: int = 15
    cache_ttl_seconds: int = 60
    circuit_failure_threshold: int = 5
    batch_release_chunk_size: int = 100


@dataclass
class InventoryResult:
    """Result of inventory operation."""
    success: bool
    trip_id: int
    travel_date: date
    coach_type: str
    operation: str
    available_seats: int
    locked_seats: int
    message: str
    error: Optional[str] = None


class InventoryService:
    """
    Inventory Service for managing seat availability and temporary locks.
    With circuit breaker protection and distributed locking support.
    """
    
    _metrics: deque = deque(maxlen=1000)
    _metrics_lock = None  # Will be initialized lazily
    
    def __init__(self, config: Optional[InventoryConfig] = None):
        self.config = config or InventoryConfig()
        self._breaker = circuit_breaker_manager.get_or_create("inventory")
        self._lock_manager = None  # Will be initialized with cache_service
    
    def _get_lock_manager(self):
        """Get or create lock manager."""
        if self._lock_manager is None:
            self._lock_manager = cache_service
        return self._lock_manager
    
    def _get_cache_key(self, trip_id: int, travel_date: date, coach_type: str) -> str:
        """Generate cache key for inventory."""
        return f"inventory:{trip_id}:{travel_date.isoformat()}:{coach_type}"
    
    def _get_cached_inventory(self, trip_id: int, travel_date: date, coach_type: str) -> Optional[Dict]:
        """Get cached inventory data."""
        cache_key = self._get_cache_key(trip_id, travel_date, coach_type)
        return cache_service.get(cache_key)
    
    def _cache_inventory(self, trip_id: int, travel_date: date, coach_type: str, data: Dict):
        """Cache inventory data."""
        cache_key = self._get_cache_key(trip_id, travel_date, coach_type)
        cache_service.set(cache_key, data, ttl_seconds=self.config.cache_ttl_seconds)
    
    @circuit_breaker_manager.get_or_create("inventory").decorate
    @retry_sync
    def reserve_seat_temporary(
        self,
        db: Session, 
        trip_id: int, 
        travel_date: date, 
        coach_type: str,
        booking_id: str,
        lock_minutes: Optional[int] = None
    ) -> InventoryResult:
        """
        Subtask 45.2: Atomically decrement available seats and set a lock.
        Uses optimistic concurrency or SELECT FOR UPDATE if needed.
        
        Args:
            db: Database session
            trip_id: Trip identifier
            travel_date: Date of travel
            coach_type: Type of coach (AC_THREE_TIER, etc.)
            booking_id: Booking ID for tracking
            lock_minutes: Lock duration in minutes
            
        Returns:
            InventoryResult with operation outcome
        """
        lock_duration = lock_minutes or self.config.lock_minutes
        start_time = datetime.utcnow()
        
        try:
            # 1. Find the inventory record with row lock
            inventory = db.query(SeatInventory).filter(
                SeatInventory.trip_id == trip_id,
                SeatInventory.travel_date == travel_date,
                SeatInventory.coach_type == coach_type
            ).with_for_update().first()
            
            if not inventory:
                logger.warning(f"No inventory record found for Trip {trip_id} on {travel_date}")
                return InventoryResult(
                    success=False,
                    trip_id=trip_id,
                    travel_date=travel_date,
                    coach_type=coach_type,
                    operation="reserve",
                    available_seats=0,
                    locked_seats=0,
                    message="Inventory not found",
                    error="No inventory record found"
                )
            
            # 2. Check availability
            if inventory.available_seats <= 0:
                return InventoryResult(
                    success=False,
                    trip_id=trip_id,
                    travel_date=travel_date,
                    coach_type=coach_type,
                    operation="reserve",
                    available_seats=0,
                    locked_seats=0,
                    message="No seats available",
                    error="Insufficient inventory"
                )
            
            # 3. Reserve the seat
            old_seats = inventory.available_seats
            inventory.available_seats -= 1
            inventory.locked_until = datetime.utcnow() + timedelta(minutes=lock_duration)
            inventory.locked_by_booking_id = booking_id
            inventory.last_updated = datetime.utcnow()
            
            # 4. Create audit log
            audit = AuditLog(
                entity_type="Inventory",
                entity_id=inventory.id,
                action="SEAT_LOCKED_TEMPORARY",
                old_value=str(old_seats),
                new_value=str(inventory.available_seats),
                performed_by="SYSTEM_INVENTORY",
                reason=f"Booking {booking_id} locked 1 seat."
            )
            db.add(audit)
            db.commit()
            
            # 5. Update cache
            self._cache_inventory(trip_id, travel_date, coach_type, {
                "available_seats": inventory.available_seats,
                "locked_until": inventory.locked_until.isoformat(),
                "locked_by": booking_id
            })
            
            # 6. Record metrics
            self._record_operation("reserve", True, trip_id, travel_date, coach_type)
            
            logger.info(f"Seat reserved: Trip {trip_id}, {coach_type}, Booking {booking_id}")
            
            return InventoryResult(
                success=True,
                trip_id=trip_id,
                travel_date=travel_date,
                coach_type=coach_type,
                operation="reserve",
                available_seats=inventory.available_seats,
                locked_seats=1,
                message="Seat reserved successfully"
            )
            
        except Exception as e:
            logger.error(f"Error reserving seat: {e}")
            db.rollback()
            self._record_operation("reserve", False, trip_id, travel_date, coach_type)
            
            return InventoryResult(
                success=False,
                trip_id=trip_id,
                travel_date=travel_date,
                coach_type=coach_type,
                operation="reserve",
                available_seats=0,
                locked_seats=0,
                message="Reservation failed",
                error=str(e)
            )

    @circuit_breaker_manager.get_or_create("inventory").decorate
    def release_expired_locks(self, db: Session, batch_size: Optional[int] = None) -> Dict[str, Any]:
        """
        Subtask 45.3: Restore seats for expired locks.
        
        Args:
            db: Database session
            batch_size: Maximum number of locks to release per batch
            
        Returns:
            Dictionary with release statistics
        """
        chunk_size = batch_size or self.config.batch_release_chunk_size
        now = datetime.utcnow()
        
        try:
            # Find expired locks
            expired = db.query(SeatInventory).filter(
                SeatInventory.locked_until != None,
                SeatInventory.locked_until < now
            ).limit(chunk_size).all()
            
            released_count = 0
            total_seats_released = 0
            
            for inv in expired:
                old_seats = inv.available_seats
                inv.available_seats += 1
                inv.locked_until = None
                inv.locked_by_booking_id = None
                inv.last_updated = datetime.utcnow()
                released_count += 1
                total_seats_released += 1
                
                # Create audit log
                audit = AuditLog(
                    entity_type="Inventory",
                    entity_id=inv.id,
                    action="SEAT_LOCK_EXPIRED",
                    old_value=str(old_seats),
                    new_value=str(inv.available_seats),
                    performed_by="SYSTEM_INVENTORY",
                    reason="Lock expired, seat released"
                )
                db.add(audit)
            
            if released_count > 0:
                db.commit()
                logger.info(f"Released {released_count} expired seat locks, {total_seats_released} seats")
            
            # Record metrics
            self._record_operation("release_expired", True, 0, None, None)
            
            return {
                "success": True,
                "locks_released": released_count,
                "seats_released": total_seats_released,
                "batch_size": chunk_size
            }
            
        except Exception as e:
            logger.error(f"Error releasing expired locks: {e}")
            db.rollback()
            self._record_operation("release_expired", False, 0, None, None)
            
            return {
                "success": False,
                "locks_released": 0,
                "seats_released": 0,
                "error": str(e)
            }

    @circuit_breaker_manager.get_or_create("inventory").decorate
    def release_seat(
        self,
        db: Session,
        trip_id: int,
        travel_date: date,
        coach_type: str,
        booking_id: str,
        reason: str = "cancellation"
    ) -> InventoryResult:
        """
        Release a reserved seat (e.g., on cancellation).
        
        Args:
            db: Database session
            trip_id: Trip identifier
            travel_date: Date of travel
            coach_type: Type of coach
            booking_id: Booking ID that held the lock
            reason: Reason for release
            
        Returns:
            InventoryResult with operation outcome
        """
        try:
            # Find the inventory record with lock
            inventory = db.query(SeatInventory).filter(
                SeatInventory.train_number == str(trip_id),
                SeatInventory.journey_date == travel_date,
                SeatInventory.class_type == coach_type
            ).with_for_update().first()
            
            if not inventory:
                return InventoryResult(
                    success=False,
                    trip_id=trip_id,
                    travel_date=travel_date,
                    coach_type=coach_type,
                    operation="release",
                    available_seats=0,
                    locked_seats=0,
                    message="Inventory not found",
                    error="No inventory record found"
                )
            
            # Check if this booking holds the lock
            if inventory.locked_by_booking_id != booking_id:
                logger.warning(f"Lock mismatch: {booking_id} != {inventory.locked_by_booking_id}")
                return InventoryResult(
                    success=False,
                    trip_id=trip_id,
                    travel_date=travel_date,
                    coach_type=coach_type,
                    operation="release",
                    available_seats=inventory.available_seats,
                    locked_seats=1,
                    message="Lock held by different booking",
                    error="Lock ownership mismatch"
                )
            
            old_seats = inventory.available_seats
            inventory.available_seats += 1
            inventory.locked_until = None
            inventory.locked_by_booking_id = None
            inventory.last_updated = datetime.utcnow()
            
            # Create audit log
            audit = AuditLog(
                entity_type="Inventory",
                entity_id=inventory.id,
                action="SEAT_RELEASED",
                old_value=str(old_seats),
                new_value=str(inventory.available_seats),
                performed_by="SYSTEM_INVENTORY",
                reason=f"Booking {booking_id} released seat. Reason: {reason}"
            )
            db.add(audit)
            db.commit()
            
            # Update cache
            self._cache_inventory(trip_id, travel_date, coach_type, {
                "available_seats": inventory.available_seats,
                "locked_until": None,
                "locked_by": None
            })
            
            # Record metrics
            self._record_operation("release", True, trip_id, travel_date, coach_type)
            
            return InventoryResult(
                success=True,
                trip_id=trip_id,
                travel_date=travel_date,
                coach_type=coach_type,
                operation="release",
                available_seats=inventory.available_seats,
                locked_seats=0,
                message="Seat released successfully"
            )
            
        except Exception as e:
            logger.error(f"Error releasing seat: {e}")
            db.rollback()
            self._record_operation("release", False, trip_id, travel_date, coach_type)
            
            return InventoryResult(
                success=False,
                trip_id=trip_id,
                travel_date=travel_date,
                coach_type=coach_type,
                operation="release",
                available_seats=0,
                locked_seats=0,
                message="Release failed",
                error=str(e)
            )

    @circuit_breaker_manager.get_or_create("inventory").decorate
    def get_availability(
        self,
        db: Session,
        trip_id: int,
        travel_date: date,
        coach_type: str,
        bypass_cache: bool = False
    ) -> Dict[str, Any]:
        """
        Get current seat availability.
        
        Args:
            db: Database session
            trip_id: Trip identifier
            travel_date: Date of travel
            coach_type: Type of coach
            bypass_cache: Skip cache and fetch fresh data
            
        Returns:
            Dictionary with availability information
        """
        # Check cache first
        if not bypass_cache:
            cached = self._get_cached_inventory(trip_id, travel_date, coach_type)
            if cached:
                return {
                    **cached,
                    "trip_id": trip_id,
                    "travel_date": travel_date.isoformat(),
                    "coach_type": coach_type,
                    "cached": True
                }
        
        try:
            inventory = db.query(SeatInventory).filter(
                SeatInventory.train_number == str(trip_id),
                SeatInventory.journey_date == travel_date,
                SeatInventory.class_type == coach_type
            ).first()
            
            if not inventory:
                return {
                    "trip_id": trip_id,
                    "travel_date": travel_date.isoformat(),
                    "coach_type": coach_type,
                    "available_seats": 0,
                    "total_seats": 0,
                    "locked": False,
                    "cached": False
                }
            
            result = {
                "trip_id": trip_id,
                "travel_date": travel_date.isoformat(),
                "coach_type": coach_type,
                "available_seats": inventory.available_seats,
                "total_seats": inventory.total_seats,
                "locked": inventory.locked_until is not None and inventory.locked_until > datetime.utcnow(),
                "locked_until": inventory.locked_until.isoformat() if inventory.locked_until else None,
                "locked_by": inventory.locked_by_booking_id,
                "cached": False
            }
            
            # Cache the result
            self._cache_inventory(trip_id, travel_date, coach_type, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting availability: {e}")
            return {
                "trip_id": trip_id,
                "travel_date": travel_date.isoformat(),
                "coach_type": coach_type,
                "error": str(e),
                "cached": False
            }

    def _record_operation(
        self,
        operation: str,
        success: bool,
        trip_id: int,
        travel_date: Optional[date],
        coach_type: Optional[str]
    ):
        """Record operation for metrics."""
        if self._metrics_lock is None:
            import asyncio
            self._metrics_lock = asyncio.Lock()
        
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        loop.run_until_complete(self._record_operation_async(operation, success, trip_id, travel_date, coach_type))
    
    async def _record_operation_async(
        self,
        operation: str,
        success: bool,
        trip_id: int,
        travel_date: Optional[date],
        coach_type: Optional[str]
    ):
        """Record operation for metrics (async)."""
        async with self._metrics_lock:
            self._metrics.append({
                "timestamp": datetime.utcnow(),
                "operation": operation,
                "success": success,
                "trip_id": trip_id,
                "coach_type": coach_type
            })

    def get_metrics(self) -> dict:
        """Get inventory service metrics."""
        if not self._metrics:
            return {"total_operations": 0, "success_rate": 0.0}
        
        total = len(self._metrics)
        successful = sum(1 for m in self._metrics if m["success"])
        
        operations = {}
        for m in self._metrics:
            op = m["operation"]
            if op not in operations:
                operations[op] = {"total": 0, "success": 0}
            operations[op]["total"] += 1
            if m["success"]:
                operations[op]["success"] += 1
        
        return {
            "total_operations": total,
            "successful_operations": successful,
            "success_rate": successful / total if total > 0 else 0.0,
            "operation_breakdown": operations,
            "circuit_breaker_state": self._breaker.get_state().value
        }

    def health_check(self) -> dict:
        """Check service health."""
        return {
            "status": "healthy",
            "circuit_breaker": self._breaker.get_state().value,
            "config": {
                "lock_minutes": self.config.lock_minutes,
                "cache_ttl_seconds": self.config.cache_ttl_seconds,
                "batch_release_chunk_size": self.config.batch_release_chunk_size
            },
            "metrics": self.get_metrics()
        }

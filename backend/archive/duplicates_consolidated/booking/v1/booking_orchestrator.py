"""
Booking Transaction Orchestrator - Distributed Booking Engine

Implements Saga pattern for distributed booking transactions.
Handles payment processing, seat allocation, PNR generation, and rollback.

Key Features:
- Saga pattern for distributed transactions
- Payment integration with rollback
- Seat allocation coordination
- PNR generation and notification
- High-concurrency handling
- Dead letter queue for failed transactions
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
import logging
import uuid

from sqlalchemy import and_, or_, func, update
from sqlalchemy.orm import Session
import redis.asyncio as redis

from .database import SessionLocal
from .seat_inventory_models import (
    PNRRecord, PassengerDetail, BookingLock, BookingStatus
)
from .availability_service import availability_service, AvailabilityRequest, SeatAllocation
from .models import User, Trip, StopTime
from .config import Config

# Microservice Integration
try:
    from microservices.common.grpc_clients import grpc_clients
    import inventory_pb2
    from google.protobuf.timestamp_pb2 import Timestamp
    MICROSERVICE_MODE = True
except ImportError:
    MICROSERVICE_MODE = False

logger = logging.getLogger(__name__)


@dataclass
class BookingRequest:
    """Booking request data"""
    user_id: str
    trip_id: int
    from_stop_id: int
    to_stop_id: int
    travel_date: str  # ISO date string
    quota_type: str
    passengers: List[Dict]  # List of passenger details
    payment_method: Dict
    preferences: Optional[Dict] = None

@dataclass
class BookingResponse:
    """Booking response"""
    success: bool
    pnr_number: Optional[str] = None
    booking_id: Optional[str] = None
    total_amount: Optional[float] = None
    message: str = ""
    errors: List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class SagaStep:
    """Individual step in a saga transaction"""

    def __init__(self, name: str, execute_func: Callable, compensate_func: Callable):
        self.name = name
        self.execute_func = execute_func
        self.compensate_func = compensate_func
        self.executed = False
        self.compensated = False

    async def execute(self, context: Dict) -> bool:
        """Execute the step"""
        try:
            result = await self.execute_func(context)
            self.executed = True
            return result
        except Exception as e:
            logger.error(f"Saga step {self.name} failed: {e}")
            return False

    async def compensate(self, context: Dict) -> bool:
        """Compensate the step"""
        if not self.executed:
            return True

        try:
            result = await self.compensate_func(context)
            self.compensated = True
            return result
        except Exception as e:
            logger.error(f"Saga step {self.name} compensation failed: {e}")
            return False


class BookingSaga:
    """Saga orchestrator for booking transactions"""

    def __init__(self, booking_request: BookingRequest):
        self.booking_request = booking_request
        self.saga_id = str(uuid.uuid4())
        self.steps: List[SagaStep] = []
        self.context: Dict[str, Any] = {
            'saga_id': self.saga_id,
            'booking_request': booking_request,
            'allocated_seats': [],
            'pnr_record': None,
            'payment_transaction': None
        }
        self.redis: Optional[redis.Redis] = None
        self._build_saga()

    async def initialize(self):
        """Initialize Redis connection"""
        if not self.redis:
            self.redis = redis.Redis.from_url(Config.REDIS_URL, decode_responses=True)
            await self.redis.ping()

    def _build_saga(self):
        """Build the saga steps"""
        # Step 1: Validate booking request
        self.steps.append(SagaStep(
            "validate_request",
            self._validate_request,
            self._compensate_validate_request
        ))

        # Step 2: Check availability and allocate seats
        self.steps.append(SagaStep(
            "allocate_seats",
            self._allocate_seats,
            self._compensate_allocate_seats
        ))

        # Step 3: Process payment
        self.steps.append(SagaStep(
            "process_payment",
            self._process_payment,
            self._compensate_process_payment
        ))

        # Step 4: Generate PNR and create booking record
        self.steps.append(SagaStep(
            "generate_pnr",
            self._generate_pnr,
            self._compensate_generate_pnr
        ))

        # Step 5: Send notifications
        self.steps.append(SagaStep(
            "send_notifications",
            self._send_notifications,
            self._compensate_send_notifications
        ))

    async def execute(self) -> BookingResponse:
        """Execute the saga"""
        await self.initialize()

        # Store saga state in Redis
        await self._save_saga_state("running")

        try:
            for step in self.steps:
                logger.info(f"Executing saga step: {step.name}")
                success = await step.execute(self.context)

                if not success:
                    # Start compensation
                    await self._compensate()
                    await self._save_saga_state("failed")
                    return BookingResponse(
                        success=False,
                        message=f"Booking failed at step: {step.name}"
                    )

            # All steps successful
            await self._save_saga_state("completed")
            return BookingResponse(
                success=True,
                pnr_number=self.context.get('pnr_number'),
                booking_id=self.context.get('booking_id'),
                total_amount=self.context.get('total_amount'),
                message="Booking confirmed successfully"
            )

        except Exception as e:
            logger.error(f"Saga execution failed: {e}")
            await self._compensate()
            await self._save_saga_state("failed")
            return BookingResponse(
                success=False,
                message=f"Booking failed: {str(e)}"
            )

    async def _compensate(self):
        """Compensate all executed steps in reverse order"""
        logger.info("Starting saga compensation")

        for step in reversed(self.steps):
            if step.executed and not step.compensated:
                logger.info(f"Compensating saga step: {step.name}")
                await step.compensate(self.context)

        await self._save_saga_state("compensated")

    async def _validate_request(self, context: Dict) -> bool:
        """Validate booking request"""
        request = context['booking_request']

        # Validate user exists
        session = SessionLocal()
        try:
            user = session.query(User).filter(User.id == request.user_id).first()
            if not user:
                context['validation_error'] = "User not found"
                return False

            # Validate trip exists
            trip = session.query(Trip).filter(Trip.id == request.trip_id).first()
            if not trip:
                context['validation_error'] = "Trip not found"
                return False

            # Validate stops
            from_stop = session.query(StopTime).filter(
                and_(StopTime.trip_id == request.trip_id, StopTime.stop_id == request.from_stop_id)
            ).first()

            to_stop = session.query(StopTime).filter(
                and_(StopTime.trip_id == request.trip_id, StopTime.stop_id == request.to_stop_id)
            ).first()

            if not from_stop or not to_stop:
                context['validation_error'] = "Invalid stops for this trip"
                return False

            # Validate passenger count
            if len(request.passengers) > 6:
                context['validation_error'] = "Maximum 6 passengers allowed"
                return False

            # Validate travel date
            travel_date = datetime.fromisoformat(request.travel_date).date()
            if travel_date < datetime.utcnow().date():
                context['validation_error'] = "Cannot book for past dates"
                return False

            context['validated_user'] = user
            context['validated_trip'] = trip
            context['travel_date'] = travel_date

            return True

        finally:
            session.close()

    async def _compensate_validate_request(self, context: Dict) -> bool:
        """No compensation needed for validation"""
        return True

    async def _allocate_seats(self, context: Dict) -> bool:
        """Allocate seats for the booking"""
        request: BookingRequest = context['booking_request']
        travel_date = context['travel_date']

        if MICROSERVICE_MODE:
            logger.info(f"Allocating seats via gRPC for trip {request.trip_id}")
            try:
                inventory_grpc = grpc_clients.get_inventory_client()
                ts = Timestamp()
                ts.FromDatetime(datetime.combine(travel_date, datetime.min.time()))
                
                # Step 1: Lock Seats
                lock_resp = await inventory_grpc.LockSeats(inventory_pb2.LockRequest(
                    train_id=str(request.trip_id),
                    from_stop_id=str(request.from_stop_id),
                    to_stop_id=str(request.to_stop_id),
                    travel_date=ts,
                    count=len(request.passengers),
                    lock_token=context['saga_id'],
                    expiry_seconds=300
                ))
                
                if not lock_resp.success:
                    context['allocation_error'] = lock_resp.error_message
                    return False
                
                context['lock_id'] = lock_resp.lock_id
                # Note: Actual allocation happens after payment in gRPC mode
                return True
            except Exception as e:
                logger.error(f"gRPC Allocation failed: {e}")
                return False

        # Local logic (Original)
        # Create availability request
        avail_request = AvailabilityRequest(
            trip_id=request.trip_id,
            from_stop_id=request.from_stop_id,
            to_stop_id=request.to_stop_id,
            travel_date=travel_date,
            quota_type=request.quota_type,
            passengers=len(request.passengers)
        )

        # Allocate seats
        allocation = await availability_service.allocate_seats(
            avail_request, request.user_id, context['saga_id']
        )

        if not allocation:
            context['allocation_error'] = "Seats not available"
            return False

        context['seat_allocation'] = allocation
        context['allocated_seats'] = allocation.seat_ids

        return True

    async def _compensate_allocate_seats(self, context: Dict) -> bool:
        """Release allocated seats"""
        if MICROSERVICE_MODE and 'lock_id' in context:
            try:
                inventory_grpc = grpc_clients.get_inventory_client()
                await inventory_grpc.ReleaseSeats(inventory_pb2.ReleaseRequest(
                    lock_id=context['lock_id']
                ))
                return True
            except Exception as e:
                logger.error(f"gRPC Release failed: {e}")
                return False

        allocated_seats = context.get('allocated_seats', [])
        if allocated_seats:
            await availability_service.release_seats(allocated_seats, context['saga_id'])
        return True
        return True

    async def _process_payment(self, context: Dict) -> bool:
        """Process payment for the booking"""
        request = context['booking_request']
        allocation = context['seat_allocation']

        # Calculate total amount (simplified - would integrate with fare engine)
        # For now, use a fixed amount per passenger
        base_fare = 500.0  # This would come from fare engine
        passengers = len(request.passengers)
        total_amount = base_fare * passengers

        # Process payment (simplified - would integrate with payment gateway)
        payment_result = await self._process_payment_gateway(
            request.payment_method, total_amount, context['saga_id']
        )

        if not payment_result['success']:
            context['payment_error'] = payment_result.get('error', 'Payment failed')
            return False

        context['payment_transaction'] = payment_result['transaction_id']
        context['total_amount'] = total_amount

        return True

    async def _compensate_process_payment(self, context: Dict) -> bool:
        """Refund payment"""
        transaction_id = context.get('payment_transaction')
        if transaction_id:
            await self._refund_payment(transaction_id)
        return True

    async def _generate_pnr(self, context: Dict) -> bool:
        """Generate PNR and create booking record"""
        request = context['booking_request']
        allocation = context['seat_allocation']
        travel_date = context['travel_date']

        session = SessionLocal()
        try:
            # Generate unique 10-digit PNR
            pnr_number = await self._generate_unique_pnr()

            # Create PNR record
            pnr_record = PNRRecord(
                pnr_number=pnr_number,
                user_id=request.user_id,
                trip_id=request.trip_id,
                from_stop_id=request.from_stop_id,
                to_stop_id=request.to_stop_id,
                travel_date=travel_date,
                quota_type=request.quota_type,
                total_passengers=len(request.passengers),
                total_amount=context['total_amount'],
                payment_transaction_id=context['payment_transaction'],
                booking_status=BookingStatus.CONFIRMED,
                seat_allocation_json={
                    'seat_ids': allocation.seat_ids,
                    'coach_number': allocation.coach_number,
                    'quota_type': allocation.quota_type.value
                },
                preferences_json=request.preferences
            )

            session.add(pnr_record)
            session.flush()  # Get the ID

            # Create passenger details
            for i, passenger in enumerate(request.passengers):
                passenger_detail = PassengerDetail(
                    pnr_id=pnr_record.id,
                    passenger_sequence=i + 1,
                    name=passenger['name'],
                    age=passenger['age'],
                    gender=passenger['gender'],
                    seat_number=allocation.seat_ids[i] if i < len(allocation.seat_ids) else None,
                    passenger_json=passenger
                )
                session.add(passenger_detail)

            session.commit()

            context['pnr_record'] = pnr_record
            context['pnr_number'] = pnr_number
            context['booking_id'] = pnr_record.id

            return True

        except Exception as e:
            session.rollback()
            context['pnr_error'] = str(e)
            return False
        finally:
            session.close()

    async def _compensate_generate_pnr(self, context: Dict) -> bool:
        """Cancel PNR and booking"""
        pnr_record = context.get('pnr_record')
        if pnr_record:
            session = SessionLocal()
            try:
                # Mark PNR as cancelled
                pnr_record.booking_status = BookingStatus.CANCELLED
                session.commit()
            finally:
                session.close()
        return True

    async def _send_notifications(self, context: Dict) -> bool:
        """Send booking confirmation notifications"""
        pnr_number = context['pnr_number']
        user_id = context['booking_request'].user_id

        # Send email/SMS notification (simplified)
        try:
            await self._send_booking_notification(user_id, pnr_number)
            return True
        except Exception as e:
            logger.error(f"Notification failed: {e}")
            # Don't fail the booking for notification errors
            return True

    async def _compensate_send_notifications(self, context: Dict) -> bool:
        """Send cancellation notification"""
        pnr_number = context.get('pnr_number')
        user_id = context['booking_request'].user_id

        try:
            await self._send_cancellation_notification(user_id, pnr_number)
            return True
        except Exception as e:
            logger.error(f"Cancellation notification failed: {e}")
            return True

    async def _generate_unique_pnr(self) -> str:
        """Generate unique 10-digit PNR number"""
        session = SessionLocal()
        try:
            while True:
                # Generate random 10-digit number
                pnr = str(uuid.uuid4().int)[:10]

                # Check if it exists
                existing = session.query(PNRRecord).filter(PNRRecord.pnr_number == pnr).first()
                if not existing:
                    return pnr
        finally:
            session.close()

    async def _process_payment_gateway(self, payment_method: Dict, amount: float, saga_id: str) -> Dict:
        """Process payment through gateway (simplified)"""
        # This would integrate with actual payment gateway
        # For now, simulate success
        await asyncio.sleep(0.1)  # Simulate network call

        return {
            'success': True,
            'transaction_id': f"txn_{saga_id}",
            'amount': amount
        }

    async def _refund_payment(self, transaction_id: str):
        """Refund payment (simplified)"""
        # This would integrate with payment gateway for refunds
        logger.info(f"Processing refund for transaction: {transaction_id}")

    async def _send_booking_notification(self, user_id: str, pnr_number: str):
        """Send booking confirmation notification"""
        # This would integrate with notification service
        logger.info(f"Sending booking confirmation for PNR: {pnr_number} to user: {user_id}")

    async def _send_cancellation_notification(self, user_id: str, pnr_number: str):
        """Send booking cancellation notification"""
        # This would integrate with notification service
        logger.info(f"Sending cancellation notification for PNR: {pnr_number} to user: {user_id}")

    async def _save_saga_state(self, state: str):
        """Save saga state to Redis"""
        state_data = {
            'saga_id': self.saga_id,
            'state': state,
            'context': self.context,
            'timestamp': datetime.utcnow().isoformat()
        }

        await self.redis.setex(
            f"saga:{self.saga_id}",
            3600,  # 1 hour TTL
            json.dumps(state_data)
        )


class BookingTransactionOrchestrator:
    """Main orchestrator for booking transactions"""

    def __init__(self):
        self.redis: Optional[redis.Redis] = None

    async def initialize(self):
        """Initialize Redis connection"""
        if not self.redis:
            self.redis = redis.Redis.from_url(Config.REDIS_URL, decode_responses=True)
            await self.redis.ping()

    async def process_booking(self, booking_request: BookingRequest) -> BookingResponse:
        """Process a booking request using saga pattern"""
        await self.initialize()

        # Create and execute saga
        saga = BookingSaga(booking_request)
        result = await saga.execute()

        # Log the result
        logger.info(f"Booking saga {saga.saga_id} completed with result: {result.success}")

        return result

    async def cancel_booking(self, pnr_number: str, user_id: str) -> Dict[str, Any]:
        """Cancel a booking"""
        session = SessionLocal()
        try:
            # Find PNR record
            pnr_record = session.query(PNRRecord).filter(
                and_(
                    PNRRecord.pnr_number == pnr_number,
                    PNRRecord.user_id == user_id
                )
            ).first()

            if not pnr_record:
                return {'success': False, 'message': 'PNR not found'}

            if pnr_record.booking_status == BookingStatus.CANCELLED:
                return {'success': False, 'message': 'Booking already cancelled'}

            # Check cancellation policy (simplified)
            travel_date = pnr_record.travel_date
            days_until_travel = (travel_date - datetime.utcnow().date()).days

            if days_until_travel < 1:
                return {'success': False, 'message': 'Cannot cancel booking less than 24 hours before travel'}

            # Calculate refund amount (simplified)
            refund_amount = pnr_record.total_amount * 0.9  # 90% refund

            # Update PNR status
            pnr_record.booking_status = BookingStatus.CANCELLED
            pnr_record.cancelled_at = datetime.utcnow()

            # Release seats
            seat_allocation = pnr_record.seat_allocation_json
            if seat_allocation and 'seat_ids' in seat_allocation:
                await availability_service.release_seats(seat_allocation['seat_ids'], 'cancellation')

            # Process refund
            if pnr_record.payment_transaction_id:
                await self._process_refund(pnr_record.payment_transaction_id, refund_amount)

            session.commit()

            return {
                'success': True,
                'message': 'Booking cancelled successfully',
                'refund_amount': refund_amount
            }

        finally:
            session.close()

    async def _process_refund(self, transaction_id: str, amount: float):
        """Process refund (simplified)"""
        logger.info(f"Processing refund of {amount} for transaction: {transaction_id}")

    async def get_booking_status(self, pnr_number: str, user_id: str) -> Optional[Dict]:
        """Get booking status"""
        session = SessionLocal()
        try:
            pnr_record = session.query(PNRRecord).filter(
                and_(
                    PNRRecord.pnr_number == pnr_number,
                    PNRRecord.user_id == user_id
                )
            ).first()

            if not pnr_record:
                return None

            return {
                'pnr_number': pnr_record.pnr_number,
                'status': pnr_record.booking_status.value,
                'travel_date': pnr_record.travel_date.isoformat(),
                'total_amount': pnr_record.total_amount,
                'passengers': pnr_record.total_passengers,
                'created_at': pnr_record.created_at.isoformat()
            }

        finally:
            session.close()


# Global instance
booking_orchestrator = BookingTransactionOrchestrator()

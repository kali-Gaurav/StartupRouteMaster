"""
Redistribution Booking Integrator

Integrates demand redistribution service with booking system.
Enables seamless passenger movement from high-demand to low-demand routes.

Patent Innovation #1: Demand-Based Passenger Redistribution
This system continuously monitors demand/supply across the network and offers
incentives to flexible passengers to balance distribution, maximizing utilization
and revenue while improving passenger experience.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, date, timedelta
from dataclasses import dataclass, field
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from core.resilience import circuit_breaker_manager, CircuitBreaker, CircuitConfig
from core.retry import RetryPolicy
from database.models import (
    Booking, User, BookingAuditLog
)
from database.algorithm_models import (
    RedistributionOffer as RedistributionOfferModel
)

logger = logging.getLogger("redistribution.integrator")


@dataclass
class RedistributionResult:
    """Result of redistribution execution"""
    success: bool
    original_booking_id: Optional[str] = None
    new_booking_id: Optional[str] = None
    new_pnr: Optional[str] = None
    incentive_amount: float = 0.0
    message: str = ""
    error: Optional[str] = None


@dataclass
class BookingDetails:
    """Booking details for redistribution"""
    booking_id: str
    pnr: str
    user_id: str
    route_id: str
    source: str
    destination: str
    travel_date: date
    train_number: str
    coach: str
    seats: List[str]
    passenger_count: int
    total_fare: float
    booking_status: str


class RedistributionBookingIntegrator:
    """
    Integrates redistribution offers with booking system.
    
    Enables:
    - Seamless offer acceptance
    - Automatic booking cancellation
    - New booking creation on alternative routes
    - Incentive credit application
    - Complete audit trail
    """
    
    def __init__(self, db: Session):
        self.db = db
        self._circuit_breaker = circuit_breaker_manager.get_or_create(
            "redistribution_booking",
            CircuitConfig(failure_threshold=5, timeout_seconds=30.0, success_threshold=2)
        )
        self._retry = RetryPolicy(
            max_attempts=3,
            initial_delay=0.5,
            max_delay=5.0,
            conditions=[
                lambda e: isinstance(e, (ConnectionError, TimeoutError)),
                lambda e: "timeout" in str(e).lower()
            ]
        )
        logger.info("RedistributionBookingIntegrator initialized")
    
    async def execute_redistribution(
        self, 
        offer_id: str, 
        passenger_id: str, 
        accepted: bool = True
    ) -> RedistributionResult:
        """
        Execute redistribution when passenger accepts offer.
        
        Args:
            offer_id: ID of the redistribution offer
            passenger_id: ID of the passenger
            accepted: Whether offer was accepted
            
        Returns:
            RedistributionResult with execution details
        """
        try:
            # Get offer details
            offer: RedistributionOfferModel = self._get_offer(offer_id)
            if not offer:
                return RedistributionResult(
                    success=False,
                    error="Offer not found"
                )
            
            # Verify passenger
            if offer.passenger_id != passenger_id:
                return RedistributionResult(
                    success=False,
                    error="Passenger mismatch"
                )
            
            # Check offer validity
            if offer.expires_at < datetime.utcnow():
                return RedistributionResult(
                    success=False,
                    error="Offer expired"
                )
            
            if not accepted:
                return await self._handle_rejection(offer, passenger_id)
            
            # Execute redistribution
            return await self._execute_redistribution(offer, passenger_id)
            
        except Exception as e:
            logger.error(f"Redistribution execution failed: {e}")
            return RedistributionResult(
                success=False,
                error=str(e)
            )
    
    async def _execute_redistribution(
        self, 
        offer: RedistributionOfferModel, 
        passenger_id: str
    ) -> RedistributionResult:
        """Execute successful redistribution"""
        
        # Step 1: Get original booking details
        original_booking = self._get_booking(offer.original_booking_id)
        if not original_booking:
            return RedistributionResult(
                success=False,
                error="Original booking not found"
            )
        
        booking_details = self._extract_booking_details(original_booking)
        
        # Step 2: Cancel original booking
        cancel_result = await self._cancel_booking(original_booking)
        if not cancel_result["success"]:
            return RedistributionResult(
                success=False,
                error=f"Failed to cancel original booking: {cancel_result.get('error')}"
            )
        
        # Step 3: Create new booking on alternative route
        new_booking = await self._create_booking(
            passenger_id=passenger_id,
            source=offer.alternative_source,
            destination=offer.alternative_destination,
            travel_date=offer.alternative_travel_date,
            train_number=offer.alternative_train,
            passenger_count=booking_details.passenger_count,
            original_fare=booking_details.total_fare,
            incentive_amount=offer.incentive_amount
        )
        
        if not new_booking:
            # Rollback cancellation
            await self._restore_booking(original_booking)
            return RedistributionResult(
                success=False,
                error="Failed to create new booking"
            )
        
        # Step 4: Apply incentive credit
        incentive_result = await self._apply_incentive(
            passenger_id, 
            offer.incentive_amount,
            new_booking.id
        )
        
        # Step 5: Update offer status
        offer.status = "accepted"
        offer.executed_at = datetime.utcnow()
        offer.new_booking_id = new_booking.id
        self.db.commit()
        
        # Step 6: Create audit log
        self._create_audit_log(
            original_booking=original_booking,
            new_booking=new_booking,
            offer=offer,
            incentive_amount=offer.incentive_amount
        )
        
        # Step 7: Update redistribution metrics
        await self._update_metrics(offer, accepted=True)
        
        logger.info(f"Redistribution executed: {offer.original_booking_id} -> {new_booking.id}")
        
        return RedistributionResult(
            success=True,
            original_booking_id=offer.original_booking_id,
            new_booking_id=new_booking.id,
            new_pnr=new_booking.pnr,
            incentive_amount=offer.incentive_amount,
            message="Redistribution completed successfully"
        )
    
    async def _handle_rejection(
        self, 
        offer: RedistributionOfferModel, 
        passenger_id: str
    ) -> RedistributionResult:
        """Handle offer rejection"""
        
        # Update offer status
        offer.status = "rejected"
        offer.executed_at = datetime.utcnow()
        
        # Update metrics (which commits)
        await self._update_metrics(offer, accepted=False)
        
        logger.info(f"Redistribution offer rejected: {offer.id}")
        
        return RedistributionResult(
            success=True,
            original_booking_id=offer.original_booking_id,
            incentive_amount=0,
            message="Offer declined"
        )
    
    def _get_offer(self, offer_id: str) -> Optional[RedistributionOfferModel]:
        """Get redistribution offer from database"""
        return self.db.query(RedistributionOfferModel).filter(
            RedistributionOfferModel.id == offer_id
        ).first()
    
    def _get_booking(self, booking_id: str) -> Optional[Booking]:
        """Get booking from database"""
        return self.db.query(Booking).filter(
            Booking.id == booking_id
        ).first()
    
    def _extract_booking_details(self, booking: Booking) -> BookingDetails:
        """Extract booking details for redistribution"""
        return BookingDetails(
            booking_id=booking.id,
            pnr=booking.pnr,
            user_id=booking.user_id,
            route_id=booking.route_id,
            source=booking.source_station,
            destination=booking.destination_station,
            travel_date=booking.travel_date,
            train_number=booking.train_number,
            coach=booking.coach,
            seats=booking.seats if isinstance(booking.seats, list) else [],
            passenger_count=booking.passenger_count,
            total_fare=booking.total_fare,
            booking_status=booking.booking_status
        )
    
    async def _cancel_booking(self, booking: Booking) -> Dict[str, Any]:
        """Cancel original booking"""
        try:
            # Check cancellation policy
            days_before_travel = (booking.travel_date - date.today()).days
            
            if days_before_travel < 1:
                return {"success": False, "error": "Cannot cancel within 24 hours of travel"}
            
            # Calculate refund
            refund_amount = self._calculate_refund(booking, days_before_travel)
            
            # Update booking status
            booking.booking_status = "cancelled"
            booking.cancellation_date = datetime.utcnow()
            booking.refund_amount = refund_amount
            
            # Restore inventory
            # (Would update seat availability here)
            
            self.db.commit()
            
            logger.info(f"Booking cancelled: {booking.id}, refund: {refund_amount}")
            
            return {
                "success": True,
                "refund_amount": refund_amount,
                "cancellation_date": booking.cancellation_date
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to cancel booking: {e}")
            return {"success": False, "error": str(e)}
    
    def _calculate_refund(self, booking: Booking, days_before_travel: int) -> float:
        """Calculate refund amount based on cancellation policy"""
        base_fare = booking.total_fare
        
        # Cancellation charges based on days before travel
        if days_before_travel >= 7:
            return base_fare  # Full refund
        elif days_before_travel >= 3:
            return base_fare * 0.75  # 25% charge
        elif days_before_travel >= 1:
            return base_fare * 0.50  # 50% charge
        else:
            return 0  # No refund
    
    async def _create_booking(
        self,
        passenger_id: str,
        source: str,
        destination: str,
        travel_date: date,
        train_number: str,
        passenger_count: int,
        original_fare: float,
        incentive_amount: float
    ) -> Optional[Booking]:
        """Create new booking on alternative route"""
        try:
            # Calculate new fare (apply incentive)
            new_fare = max(0, original_fare - incentive_amount)
            
            # Generate PNR
            pnr = self._generate_pnr()
            
            # Create booking
            booking = Booking(
                pnr=pnr,
                user_id=passenger_id,
                source_station=source,
                destination_station=destination,
                travel_date=travel_date,
                train_number=train_number,
                passenger_count=passenger_count,
                total_fare=new_fare,
                booking_status="confirmed",
                booking_date=datetime.utcnow(),
                seats=[],  # Would be allocated by seat service
                coach="",  # Would be allocated by seat service
                route_id=""  # Would be looked up
            )
            
            self.db.add(booking)
            self.db.commit()
            self.db.refresh(booking)
            
            logger.info(f"New booking created via redistribution: {booking.id}")
            
            return booking
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create booking: {e}")
            return None
    
    def _generate_pnr(self) -> str:
        """Generate PNR number"""
        import random
        import string
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    
    async def _restore_booking(self, booking: Booking) -> None:
        """Restore booking if new booking creation fails"""
        try:
            booking.booking_status = "confirmed"
            booking.cancellation_date = None
            booking.refund_amount = None
            self.db.commit()
            logger.info(f"Booking restored: {booking.id}")
        except Exception as e:
            logger.error(f"Failed to restore booking: {e}")
    
    async def _apply_incentive(
        self, 
        user_id: str, 
        amount: float,
        booking_id: str
    ) -> Dict[str, Any]:
        """Apply incentive credit to user account"""
        try:
            credit = IncentiveCredit(
                user_id=user_id,
                amount=amount,
                credit_type="redistribution",
                description="Redistribution incentive",
                booking_id=booking_id,
                created_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(days=90)
            )
            
            self.db.add(credit)
            self.db.commit()
            
            logger.info(f"Incentive applied: {user_id}, amount: {amount}")
            
            return {"success": True, "credit_id": credit.id}
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to apply incentive: {e}")
            return {"success": False, "error": str(e)}
    
    def _create_audit_log(
        self,
        original_booking: Booking,
        new_booking: Booking,
        offer: RedistributionOfferModel,
        incentive_amount: float
    ) -> None:
        """Create audit log for redistribution"""
        try:
            audit = BookingAuditLog(
                booking_id=new_booking.id,
                action="redistribution",
                old_value=str({
                    "booking_id": original_booking.id,
                    "pnr": original_booking.pnr,
                    "train": original_booking.train_number,
                    "route": f"{original_booking.source_station}->{original_booking.destination_station}"
                }),
                new_value=str({
                    "booking_id": new_booking.id,
                    "pnr": new_booking.pnr,
                    "train": new_booking.train_number,
                    "route": f"{new_booking.source_station}->{new_booking.destination_station}",
                    "incentive": incentive_amount
                }),
                user_id=new_booking.user_id,
                timestamp=datetime.utcnow(),
                ip_address="system",
                details=f"Redistribution from offer {offer.id}"
            )
            
            self.db.add(audit)
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Failed to create audit log: {e}")
    
    async def _update_metrics(self, offer: RedistributionOfferModel, accepted: bool) -> None:
        """Update redistribution metrics"""
        try:
            # Update offer metrics
            offer.accepted = accepted
            offer.processed_at = datetime.utcnow()
            
            self.db.commit()
            
            # Would update aggregate metrics here
            logger.info(f"Metrics updated: offer {offer.id}, accepted={accepted}")
            
        except Exception as e:
            logger.error(f"Failed to update metrics: {e}")
    
    def get_redistribution_status(self, booking_id: str) -> Dict[str, Any]:
        """Get redistribution status for a booking"""
        offer = self.db.query(RedistributionOffer).filter(
            RedistributionOffer.original_booking_id == booking_id
        ).order_by(RedistributionOffer.created_at.desc()).first()
        
        if not offer:
            return {"status": "not_offered"}
        
        return {
            "status": offer.status,
            "offer_id": offer.id,
            "alternative_route": f"{offer.alternative_source}->{offer.alternative_destination}",
            "incentive_amount": offer.incentive_amount,
            "created_at": offer.created_at.isoformat(),
            "expires_at": offer.expires_at.isoformat()
        }


# Global instance factory
_redistribution_integrator = None

def get_redistribution_integrator(db: Session = None) -> RedistributionBookingIntegrator:
    """Get or create redistribution integrator instance"""
    global _redistribution_integrator
    if _redistribution_integrator is None:
        from database.session import SessionLocal
        db_session = db or SessionLocal()
        _redistribution_integrator = RedistributionBookingIntegrator(db_session)
    return _redistribution_integrator


# Export for external use
__all__ = [
    'RedistributionBookingIntegrator',
    'RedistributionResult',
    'get_redistribution_integrator'
]
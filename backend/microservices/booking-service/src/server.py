import sys
import os
import asyncio
import grpc
from concurrent import futures
import logging
from datetime import datetime
import json

# Add the root backend directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../')))

import booking_pb2
import booking_pb2_grpc
from backend.database import SessionLocal
from backend.services.booking_orchestrator import booking_orchestrator, BookingRequest
from backend.services.booking_service import BookingService
from backend.services.payment_service import PaymentService
from backend.models import Booking, User
from google.protobuf.timestamp_pb2 import Timestamp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BookingServicer(booking_pb2_grpc.BookingServiceServicer):
    """gRPC Booking Service - Booking orchestration microservice"""
    
    def __init__(self):
        self.orchestrator = booking_orchestrator
        self.db = SessionLocal()
        self.payment_service = PaymentService()
        logger.info("Booking Service initialized with Saga orchestrator")

    async def InitiateBooking(self, request, context):
        """Initiate booking with distributed Saga transaction"""
        logger.info(f"InitiateBooking: user={request.user_id}, "
                   f"passengers={len(request.passengers)}, amount={request.total_amount}")
        
        try:
            # Convert proto travel_date to string
            travel_date_str = datetime.fromtimestamp(request.travel_date.seconds).strftime('%Y-%m-%d')
            
            # Convert proto passengers to dicts
            passengers = []
            for p in request.passengers:
                passengers.append({
                    'name': p.name,
                    'age': p.age,
                    'gender': p.gender,
                    'berth_preference': p.berth_preference
                })
            
            # Build booking request
            booking_req = BookingRequest(
                user_id=request.user_id,
                trip_id=int(request.trip_id),
                from_stop_id=int(request.from_stop_id),
                to_stop_id=int(request.to_stop_id),
                travel_date=travel_date_str,
                quota_type=request.quota_type or "general",
                passengers=passengers,
                payment_method={
                    'type': request.payment_method or 'razorpay',
                    'details': {'amount': request.total_amount}
                },
                preferences=json.loads(request.preferences) if request.preferences else {}
            )
            
            # Execute booking through Saga orchestrator
            result = await self.orchestrator.process_booking(booking_req)
            
            return booking_pb2.BookingResponse(
                success=result.success,
                pnr=result.pnr_number or "",
                booking_id=result.booking_id or "",
                status=result.status,
                total_amount=result.total_amount or 0.0,
                transaction_id=result.transaction_id if hasattr(result, 'transaction_id') else "",
                message=result.message or "Booking processed"
            )
            
        except Exception as e:
            logger.error(f"Error in InitiateBooking: {e}", exc_info=True)
            context.set_details(f"Booking failed: {str(e)}")
            context.set_code(grpc.StatusCode.INTERNAL)
            return booking_pb2.BookingResponse(
                success=False,
                status="FAILED",
                message=f"Booking initiation failed: {str(e)}"
            )

    async def GetBookingStatus(self, request, context):
        """Get booking status by PNR"""
        logger.info(f"GetBookingStatus: pnr={request.pnr}")
        
        try:
            # Query booking from database
            booking = self.db.query(Booking).filter_by(id=request.pnr).first()
            
            if not booking:
                return booking_pb2.StatusResponse(
                    pnr=request.pnr,
                    status="NOT_FOUND",
                    message="Booking not found"
                )
            
            return booking_pb2.StatusResponse(
                pnr=request.pnr,
                status=booking.status if hasattr(booking, 'status') else booking.payment_status,
                payment_status=booking.payment_status,
                created_at=int(booking.created_at.timestamp()) if booking.created_at else 0,
                message=f"Booking status: {booking.status}"
            )
            
        except Exception as e:
            logger.error(f"Error in GetBookingStatus: {e}", exc_info=True)
            return booking_pb2.StatusResponse(
                pnr=request.pnr,
                status="ERROR",
                message=f"Status check failed: {str(e)}"
            )

    async def CancelBooking(self, request, context):
        """Cancel booking and process refund"""
        logger.info(f"CancelBooking: pnr={request.pnr}, reason={request.reason}")
        
        try:
            # Query booking
            booking = self.db.query(Booking).filter_by(id=request.pnr).first()
            
            if not booking:
                return booking_pb2.CancelResponse(
                    success=False,
                    pnr=request.pnr,
                    message="Booking not found"
                )
            
            # Calculate refund
            cancellation_charges = booking.amount_paid * 0.1  # 10% cancellation fee
            refund_amount = booking.amount_paid - cancellation_charges
            
            # Update booking status
            booking.payment_status = "cancelled"
            if hasattr(booking, 'status'):
                booking.status = "cancelled"
            self.db.commit()
            
            logger.info(f"Booking cancelled: {request.pnr}, refund: ₹{refund_amount}")
            
            return booking_pb2.CancelResponse(
                success=True,
                pnr=request.pnr,
                refund_amount=refund_amount,
                cancellation_charge=cancellation_charges,
                message=f"Booking cancelled. Refund: ₹{refund_amount}"
            )
            
        except Exception as e:
            logger.error(f"Error in CancelBooking: {e}", exc_info=True)
            return booking_pb2.CancelResponse(
                success=False,
                pnr=request.pnr,
                message=f"Cancellation failed: {str(e)}"
            )

async def serve():
    server = grpc.aio.server()
    booking_pb2_grpc.add_BookingServiceServicer_to_server(BookingServicer(), server)
    listen_addr = '[::]:50053'
    server.add_insecure_port(listen_addr)
    logger.info(f"Starting Booking Service on {listen_addr}")
    await server.start()
    await server.wait_for_termination()

if __name__ == '__main__':
    asyncio.run(serve())

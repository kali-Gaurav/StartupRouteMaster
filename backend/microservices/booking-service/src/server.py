import sys
import os
import asyncio
import grpc
from concurrent import futures
import logging
from datetime import datetime

# Add the root backend directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../')))

import booking_pb2
import booking_pb2_grpc
from backend.booking_orchestrator import BookingOrchestrator, BookingRequest as BookReq
from google.protobuf.timestamp_pb2 import Timestamp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BookingServicer(booking_pb2_grpc.BookingServiceServicer):
    def __init__(self):
        self.orchestrator = BookingOrchestrator()

    async def InitiateBooking(self, request, context):
        logger.info(f"Initiating booking for user {request.user_id}")
        
        # Convert proto travel_date to string (as expected by BookReq)
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
            
        # Call existing orchestrator
        # Note: orchestrator likely has an async method
        # I'll check the method name in a moment
        # result = await self.orchestrator.process_booking(BookReq(...))
        
        # Placeholder for now
        return booking_pb2.BookingResponse(
            pnr="PNR12345678",
            status="CONFIRMED",
            total_amount=1250.0,
            transaction_id="TXN_999"
        )

    async def GetBookingStatus(self, request, context):
        return booking_pb2.StatusResponse(pnr=request.pnr, status="CONFIRMED")

    async def CancelBooking(self, request, context):
        return booking_pb2.CancelResponse(success=True, refund_amount=1000.0)

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

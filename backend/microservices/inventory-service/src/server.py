import sys
import os
import asyncio
import grpc
from concurrent import futures
import logging
from datetime import datetime

# Add the root backend directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../')))

import inventory_pb2
import inventory_pb2_grpc
from backend.availability_service import AvailabilityService, AvailabilityRequest as AvailReq
from backend.seat_inventory_models import QuotaType
from google.protobuf.timestamp_pb2 import Timestamp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class InventoryServicer(inventory_pb2_grpc.InventoryServiceServicer):
    def __init__(self):
        self.service = AvailabilityService()

    async def CheckAvailability(self, request, context):
        logger.info(f"Checking availability for train {request.train_id}")
        
        # Convert proto timestamp to date
        travel_date = datetime.fromtimestamp(request.travel_date.seconds).date()
        
        # Call existing service
        resp = await self.service.check_availability(AvailReq(
            trip_id=int(request.train_id),
            from_stop_id=int(request.from_stop_id),
            to_stop_id=int(request.to_stop_id),
            travel_date=travel_date,
            quota_type=QuotaType(request.quota_type or "GENERAL"),
            passengers=1
        ))
        
        return inventory_pb2.AvailabilityResponse(
            available_count=resp.available_count if hasattr(resp, 'available_count') else 0,
            status=resp.status if hasattr(resp, 'status') else "UNKNOWN",
            prediction_accuracy=90,
            price=getattr(resp, 'fare', 0.0)
        )

    async def LockSeats(self, request, context):
        logger.info(f"Locking {request.count} seats for train {request.train_id}")
        # Build logical bridging to distributed lock
        return inventory_pb2.LockResponse(success=True, lock_id="lock_123")

    async def ReleaseSeats(self, request, context):
        return inventory_pb2.ReleaseResponse(success=True)

    async def AllocateSeats(self, request, context):
        return inventory_pb2.AllocationResponse(success=True, seat_numbers=["B1-12"])

async def serve():
    server = grpc.aio.server()
    inventory_pb2_grpc.add_InventoryServiceServicer_to_server(InventoryServicer(), server)
    listen_addr = '[::]:50052'
    server.add_insecure_port(listen_addr)
    logger.info(f"Starting Inventory Service on {listen_addr}")
    await server.start()
    await server.wait_for_termination()

if __name__ == '__main__':
    asyncio.run(serve())

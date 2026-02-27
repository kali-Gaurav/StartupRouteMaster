import sys
import os
import asyncio
import grpc
from concurrent import futures
import logging
from datetime import datetime, date
from typing import Optional

# Add the root backend directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../')))

import inventory_pb2
import inventory_pb2_grpc
from database import SessionLocal
from services.availability_service import availability_service, AvailabilityRequest
from services.advanced_seat_allocation_engine import advanced_seat_allocation_engine
from services.cancellation_predictor import cancellation_predictor
from seat_inventory_models import QuotaType
from models import SeatInventory, Booking
from google.protobuf.timestamp_pb2 import Timestamp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class InventoryServicer(inventory_pb2_grpc.InventoryServiceServicer):
    """gRPC Inventory Service - Seat availability and allocation microservice"""
    
    def __init__(self):
        self.availability_service = availability_service
        self.allocation_engine = advanced_seat_allocation_engine
        self.cancellation_predictor = cancellation_predictor
        self.db = SessionLocal()
        logger.info("Inventory Service initialized")

    async def CheckAvailability(self, request, context):
        """Check seat availability for a trip segment with prediction"""
        logger.info(f"CheckAvailability: train={request.train_id}, "
                   f"quota={request.quota_type}, passengers={request.num_passengers}")
        
        try:
            # Parse request
            travel_date = datetime.fromtimestamp(request.travel_date.seconds).date()
            quota_type = request.quota_type or "general"
            
            # Check real availability
            avail_request = AvailabilityRequest(
                trip_id=int(request.train_id),
                from_stop_id=int(request.from_stop_id),
                to_stop_id=int(request.to_stop_id),
                travel_date=travel_date,
                quota_type=QuotaType(quota_type.lower()),
                passengers=request.num_passengers if request.num_passengers > 0 else 1
            )
            
            availability = await self.availability_service.check_availability(avail_request)
            
            # Get cancellation prediction for better accuracy
            cancellation_pred = cancellation_predictor.predict_cancellation_rate(
                train_id=int(request.train_id),
                travel_date=travel_date.isoformat(),
                quota_type=quota_type,
                days_to_departure=max((travel_date - datetime.now().date()).days, 1),
                booking_velocity=0.5,
                route_popularity=0.7,
                demand_forecast=0.6,
                historical_cancellation_rate=0.08
            )
            
            # Adjust availability based on cancellation prediction
            adjusted_available = int(
                availability.available_seats * (1 + cancellation_pred.predicted_cancellation_rate * 0.5)
            )
            
            return inventory_pb2.AvailabilityResponse(
                train_id=request.train_id,
                available_count=max(adjusted_available, 0),
                total_seats=availability.total_seats,
                status="AVAILABLE" if adjusted_available > 0 else "WAITLIST",
                prediction_accuracy=int(cancellation_pred.confidence_score * 100),
                price=getattr(availability, 'fare', 0.0),
                occupancy_rate=1 - (adjusted_available / max(availability.total_seats, 1))
            )
            
        except Exception as e:
            logger.error(f"Error in CheckAvailability: {e}", exc_info=True)
            context.set_details(f"Availability check failed: {str(e)}")
            context.set_code(grpc.StatusCode.INTERNAL)
            return inventory_pb2.AvailabilityResponse(
                train_id=request.train_id,
                available_count=0,
                status="ERROR"
            )

    async def LockSeats(self, request, context):
        """Lock seats for a user during checkout"""
        logger.info(f"LockSeats: train={request.train_id}, count={request.count}, "
                   f"user={request.user_id}, ttl={request.ttl_seconds}s")
        
        try:
            # Create distributed lock in Redis
            from services.cache_service import cache_service
            
            lock_key = f"seat_lock:{request.train_id}:{request.user_id}"
            lock = cache_service.get_lock(lock_key, timeout=request.ttl_seconds or 600)
            
            if lock.acquire(blocking=False):
                logger.info(f"Seats locked: {lock_key}")
                
                return inventory_pb2.LockResponse(
                    success=True,
                    lock_id=lock_key,
                    expires_in_seconds=request.ttl_seconds or 600,
                    message="Seats locked successfully"
                )
            else:
                logger.warning(f"Could not acquire lock: {lock_key}")
                
                return inventory_pb2.LockResponse(
                    success=False,
                    message="Seats are currently locked by another user"
                )
            
        except Exception as e:
            logger.error(f"Error in LockSeats: {e}", exc_info=True)
            return inventory_pb2.LockResponse(
                success=False,
                message=f"Lock failed: {str(e)}"
            )

    async def ReleaseSeats(self, request, context):
        """Release seat lock"""
        logger.info(f"ReleaseSeats: lock_id={request.lock_id}")
        
        try:
            from services.cache_service import cache_service
            
            # Release the lock
            cache_service.redis.delete(request.lock_id)
            logger.info(f"Lock released: {request.lock_id}")
            
            return inventory_pb2.ReleaseResponse(
                success=True,
                message="Seats released successfully"
            )
            
        except Exception as e:
            logger.error(f"Error in ReleaseSeats: {e}", exc_info=True)
            return inventory_pb2.ReleaseResponse(
                success=False,
                message=f"Release failed: {str(e)}"
            )

    async def AllocateSeats(self, request, context):
        """Allocate specific seats to passengers using smart allocation"""
        logger.info(f"AllocateSeats: pnr={request.pnr}, num_passengers={request.num_passengers}, "
                   f"preferences={request.preferences}")
        
        try:
            # Parse passenger preferences
            from services.advanced_seat_allocation_engine import PassengerPreference, BerthType
            
            preferences = []
            for pref in request.preferences:
                berth_map = {
                    'LB': BerthType.LOWER,
                    'UB': BerthType.UPPER,
                    'SL': BerthType.SIDE_LOWER,
                    'SU': BerthType.SIDE_UPPER,
                }
                preferences.append(
                    PassengerPreference(
                        berth_type=berth_map.get(pref, BerthType.NO_PREFERENCE),
                        is_female=False,  # TODO: add to proto
                        is_senior=False
                    )
                )
            
            # Allocate seats using advanced engine
            result = self.allocation_engine.allocate_seats_fair_distribution(
                pnr=request.pnr,
                num_passengers=request.num_passengers,
                preferences=preferences
            )
            
            return inventory_pb2.AllocationResponse(
                success=result.success,
                pnr=request.pnr,
                seat_numbers=result.seats,
                coach=result.coach,
                status=result.status,
                message=result.message
            )
            
        except Exception as e:
            logger.error(f"Error in AllocateSeats: {e}", exc_info=True)
            return inventory_pb2.AllocationResponse(
                success=False,
                pnr=request.pnr,
                message=f"Allocation failed: {str(e)}"
            )

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

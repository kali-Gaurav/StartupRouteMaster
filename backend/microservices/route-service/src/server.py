import sys
import os
import asyncio
import grpc
from concurrent import futures
import logging
from datetime import datetime

# Add the root backend directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../')))

import route_pb2
import route_pb2_grpc
from backend.route_engine import RouteEngine, RouteConstraints
from google.protobuf.timestamp_pb2 import Timestamp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RouteServicer(route_pb2_grpc.RouteServiceServicer):
    def __init__(self):
        self.engine = RouteEngine()

    async def FindRoutes(self, request, context):
        logger.info(f"Finding routes from {request.from_station_id} to {request.to_station_id}")
        
        # Convert proto timestamp to datetime
        departure_date = datetime.fromtimestamp(request.departure_date.seconds)
        
        # Create RouteConstraints
        constraints = RouteConstraints(
            max_transfers=request.max_transfers if request.max_transfers > 0 else 3,
            preferred_class=request.preferences[0] if request.preferences else "SL"
        )
        
        # Call existing engine
        routes = await self.engine.find_routes(
            source_stop_id=int(request.from_station_id),
            dest_stop_id=int(request.to_station_id),
            departure_date=departure_date,
            constraints=constraints
        )
        
        # Convert to proto response
        proto_routes = []
        for r in routes:
            legs = []
            for segment in r.segments:
                dep_time = Timestamp()
                dep_time.FromDatetime(segment.departure_time)
                arr_time = Timestamp()
                arr_time.FromDatetime(segment.arrival_time)
                
                legs.append(route_pb2.Leg(
                    trip_id=str(segment.trip_id),
                    train_number=segment.train_number,
                    train_name=segment.train_name,
                    from_station_id=str(segment.departure_stop_id),
                    to_station_id=str(segment.arrival_stop_id),
                    departure_time=dep_time,
                    arrival_time=arr_time,
                    duration_mins=segment.duration_minutes,
                    distance_km=segment.distance_km
                ))
            
            proto_routes.append(route_pb2.Route(
                route_id=f"r_{int(time.time())}",
                legs=legs,
                total_duration_mins=sum(l.duration_mins for l in legs),
                total_price=sum(s.fare for s in r.segments),
                reliability_score=0.95 # Mock for now
            ))
        
        return route_pb2.RouteResponse(
            routes=proto_routes,
            search_id=f"search_{int(time.time())}",
            latency_ms=0.0, # Will measure properly
            cached=False
        )

    async def UpdateGraph(self, request, context):
        logger.info(f"Updating graph for train {request.train_number}")
        # Implementation depends on graph_mutation_service integration
        return route_pb2.GraphUpdateResponse(success=True, affected_routes_count=1)

    async def GetStationReachability(self, request, context):
        logger.info(f"Getting reachability for station {request.source_station_id}")
        # Implementation depends on RAPTOR-based reachability
        return route_pb2.ReachabilityResponse(reachable_stations={})

async def serve():
    server = grpc.aio.server()
    route_pb2_grpc.add_RouteServiceServicer_to_server(RouteServicer(), server)
    listen_addr = '[::]:50051'
    server.add_insecure_port(listen_addr)
    logger.info(f"Starting Route Service on {listen_addr}")
    await server.start()
    await server.wait_for_termination()

if __name__ == '__main__':
    import time # Needed for the route_id generation in this draft
    asyncio.run(serve())

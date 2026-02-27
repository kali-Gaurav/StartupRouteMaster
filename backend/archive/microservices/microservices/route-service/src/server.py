import sys
import os
import asyncio
import grpc
import time
from concurrent import futures
import logging
from datetime import datetime
from typing import Optional

# Add the root backend directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../')))

import route_pb2
import route_pb2_grpc
from database import SessionLocal
from core.route_engine import route_engine, RouteEngine
from services.route_ranking_predictor import route_ranking_predictor
from services.advanced_route_engine import AdvancedRouteEngine
from models import Stop, Trip
from google.protobuf.timestamp_pb2 import Timestamp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RouteServicer(route_pb2_grpc.RouteServiceServicer):
    """gRPC Route Service - High-performance route search microservice"""
    
    def __init__(self):
        # use shared `route_engine` instance for backward-compatible multi-modal API
        self.multi_modal_engine = route_engine
        self.advanced_engine = AdvancedRouteEngine()
        self.db = SessionLocal()
        logger.info("Route Service initialized with multi-modal and advanced engines")

    async def FindRoutes(self, request, context):
        """Find optimal routes using RAPTOR, A*, and Yen's algorithms"""
        start_time = time.time()
        logger.info(f"FindRoutes: {request.from_station_id} → {request.to_station_id}, "
                   f"date={request.departure_date.seconds}, max_transfers={request.max_transfers}")
        
        try:
            # Parse request
            from_station_id = int(request.from_station_id)
            to_station_id = int(request.to_station_id)
            departure_date = datetime.fromtimestamp(request.departure_date.seconds).date()
            max_transfers = request.max_transfers if request.max_transfers > 0 else 3
            num_alternatives = request.num_alternatives if request.num_alternatives > 0 else 5
            
            # Load engines if needed
            if not self.multi_modal_engine._is_loaded:
                self.multi_modal_engine.load_graph_from_db(self.db)
            
            # Use advanced route engine for IRCTC-grade routing
            routes = self.advanced_engine.search_routes(
                source_stop_id=from_station_id,
                destination_stop_id=to_station_id,
                travel_date=departure_date,
                num_passengers=request.num_passengers if request.num_passengers > 0 else 1,
                max_transfers=max_transfers,
                num_alternatives=num_alternatives
            )
            
            # Convert routes to proto
            proto_routes = []
            for i, route in enumerate(routes):
                legs = []
                total_duration = 0
                total_price = 0.0
                
                for segment in route.get('segments', []):
                    dep_time = Timestamp()
                    dep_time.FromDatetime(segment['departure_time'])
                    arr_time = Timestamp()
                    arr_time.FromDatetime(segment['arrival_time'])
                    
                    duration = (segment['arrival_time'] - segment['departure_time']).total_seconds() // 60
                    total_duration += duration
                    total_price += segment.get('fare', 0)
                    
                    legs.append(route_pb2.Leg(
                        trip_id=str(segment.get('trip_id', '')),
                        train_number=segment.get('train_number', ''),
                        train_name=segment.get('train_name', ''),
                        from_station_id=str(segment.get('from_stop_id', '')),
                        to_station_id=str(segment.get('to_stop_id', '')),
                        departure_time=dep_time,
                        arrival_time=arr_time,
                        duration_mins=int(duration),
                        distance_km=segment.get('distance_km', 0.0)
                    ))
                
                # Get reliability score
                reliability = route_ranking_predictor.predict_route_quality(
                    route_data={
                        'duration': total_duration,
                        'transfers': len(route.get('transfers', [])),
                        'price': total_price
                    }
                ) if route_ranking_predictor.is_trained else 0.85
                
                proto_routes.append(route_pb2.Route(
                    route_id=f"route_{i}_{int(time.time())}",
                    legs=legs,
                    total_duration_mins=int(total_duration),
                    total_price=round(total_price, 2),
                    reliability_score=float(reliability),
                    num_transfers=len(route.get('transfers', []))
                ))
            
            latency_ms = (time.time() - start_time) * 1000
            
            return route_pb2.RouteResponse(
                routes=proto_routes,
                search_id=f"search_{int(time.time())}_{from_station_id}_{to_station_id}",
                latency_ms=round(latency_ms, 2),
                cached=False,
                total_results=len(proto_routes)
            )
            
        except Exception as e:
            logger.error(f"Error in FindRoutes: {e}", exc_info=True)
            context.set_details(f"Route search failed: {str(e)}")
            context.set_code(grpc.StatusCode.INTERNAL)
            return route_pb2.RouteResponse(routes=[], total_results=0)

    async def UpdateGraph(self, request, context):
        """Update routing graph with real-time train state changes"""
        logger.info(f"UpdateGraph: train {request.train_number}, "
                   f"delay={request.delay_minutes}m, status={request.status}")
        
        try:
            from graph_mutation_engine import graph_mutation_engine
            
            # Apply mutation to graph
            if request.status == "delayed":
                graph_mutation_engine.apply_delay_mutation(
                    trip_id=int(request.trip_id),
                    delay_minutes=request.delay_minutes
                )
                affected_routes = graph_mutation_engine.get_affected_routes(
                    trip_id=int(request.trip_id)
                )
            elif request.status == "cancelled":
                graph_mutation_engine.apply_cancellation_mutation(
                    trip_id=int(request.trip_id)
                )
                affected_routes = graph_mutation_engine.get_affected_routes(
                    trip_id=int(request.trip_id)
                )
            else:
                affected_routes = []
            
            logger.info(f"Graph updated: {len(affected_routes)} routes affected")
            
            return route_pb2.GraphUpdateResponse(
                success=True,
                affected_routes_count=len(affected_routes),
                message=f"Updated train {request.train_number}"
            )
            
        except Exception as e:
            logger.error(f"Error in UpdateGraph: {e}", exc_info=True)
            return route_pb2.GraphUpdateResponse(
                success=False,
                message=f"Graph update failed: {str(e)}"
            )

    async def GetStationReachability(self, request, context):
        """Get all stations reachable from source within time/transfer constraints"""
        logger.info(f"GetStationReachability: source={request.source_station_id}, "
                   f"max_transfers={request.max_transfers}")
        
        try:
            # Use RAPTOR algorithm for reachability
            reachable = self.advanced_engine.get_reachable_stations(
                source_stop_id=int(request.source_station_id),
                max_transfers=request.max_transfers if request.max_transfers > 0 else 3,
                travel_date=datetime.now().date()
            )
            
            return route_pb2.ReachabilityResponse(
                source_station_id=request.source_station_id,
                reachable_stations={
                    str(station_id): station_info
                    for station_id, station_info in reachable.items()
                }
            )
            
        except Exception as e:
            logger.error(f"Error in GetStationReachability: {e}", exc_info=True)
            return route_pb2.ReachabilityResponse(
                source_station_id=request.source_station_id,
                reachable_stations={}
            )

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

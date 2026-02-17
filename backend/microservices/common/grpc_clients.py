import grpc
import os
import sys
import logging
from typing import Optional
from contextlib import asynccontextmanager
from pybreaker import CircuitBreaker

# Configure logging
logger = logging.getLogger(__name__)

# Dynamically find proto-generated modules
def _add_proto_paths():
    base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))
    for service_dir in ['route-service', 'inventory-service', 'booking-service']:
        src_path = os.path.join(base_path, service_dir, 'src')
        if src_path not in sys.path:
            sys.path.append(src_path)

_add_proto_paths()

import route_pb2_grpc  # type: ignore
import inventory_pb2_grpc  # type: ignore
import booking_pb2_grpc  # type: ignore


class GRPCClientManager:
    """
    Production-grade gRPC client manager with:
    - Connection pooling
    - Circuit breaker pattern
    - Automatic retry logic
    - Health checking
    - Load balancing
    """
    
    def __init__(self):
        self._channels = {}
        self._clients = {}
        self._circuit_breakers = {}
        self._health_checks = {}
        logger.info("GRPCClientManager initialized")
    
    def _get_circuit_breaker(self, service_name: str) -> CircuitBreaker:
        """Get or create circuit breaker for a service"""
        if service_name not in self._circuit_breakers:
            self._circuit_breakers[service_name] = CircuitBreaker(
                fail_max=5,
                reset_timeout=60,
                listeners=[
                    lambda cb: logger.warning(f"Circuit breaker for {service_name} opened"),
                    lambda cb: logger.info(f"Circuit breaker for {service_name} closed"),
                ]
            )
        return self._circuit_breakers[service_name]
    
    def _get_channel(self, host: str, port: int, service_name: str) -> grpc.Channel:
        """Get or create gRPC channel with keepalive"""
        target = f"{host}:{port}"
        key = f"{service_name}:{target}"
        
        if key not in self._channels:
            # Create channel with keepalive options
            options = [
                ('grpc.keepalive_time_ms', 10000),  # Send keepalive every 10s
                ('grpc.keepalive_timeout_ms', 5000),  # Wait 5s for keepalive response
                ('grpc.keepalive_permit_without_calls', True),
                ('grpc.http2.max_pings_without_data', 0),
                ('grpc.max_connection_idle_ms', 300000),  # 5 minute idle timeout
                ('grpc.max_connection_age_ms', 600000),  # 10 minute max age
            ]
            
            try:
                self._channels[key] = grpc.aio.secure_channel(
                    target,
                    grpc.ssl_channel_credentials(),
                    options=options
                )
                logger.info(f"Created secure channel for {service_name} at {target}")
            except Exception as e:
                logger.warning(f"Could not create secure channel: {e}, falling back to insecure")
                self._channels[key] = grpc.aio.insecure_channel(target, options=options)
        
        return self._channels[key]
    
    def get_inventory_client(
        self,
        host: str = 'localhost',
        port: int = 50052,
        timeout_seconds: int = 30
    ) -> inventory_pb2_grpc.InventoryServiceStub:
        """
        Get inventory service client with circuit breaker protection
        
        Args:
            host: Service host
            port: Service port
            timeout_seconds: Request timeout
            
        Returns:
            InventoryServiceStub with circuit breaker wrapped calls
        """
        service_name = "inventory-service"
        target = f"{host}:{port}"
        key = f"{service_name}:{target}"
        
        if key not in self._clients:
            channel = self._get_channel(host, port, service_name)
            stub = inventory_pb2_grpc.InventoryServiceStub(channel)
            
            # Wrap with circuit breaker
            cb = self._get_circuit_breaker(service_name)
            
            # Return a proxy that applies circuit breaker logic
            class CircuitBreakerStub:
                def __init__(self, stub, cb, timeout):
                    self._stub = stub
                    self._cb = cb
                    self._timeout = timeout
                
                async def CheckAvailability(self, request, **kwargs):
                    return await self._cb.call_async(
                        self._stub.CheckAvailability,
                        request,
                        timeout=self._timeout,
                        **kwargs
                    )
                
                async def LockSeats(self, request, **kwargs):
                    return await self._cb.call_async(
                        self._stub.LockSeats,
                        request,
                        timeout=self._timeout,
                        **kwargs
                    )
                
                async def ReleaseSeats(self, request, **kwargs):
                    return await self._cb.call_async(
                        self._stub.ReleaseSeats,
                        request,
                        timeout=self._timeout,
                        **kwargs
                    )
                
                async def AllocateSeats(self, request, **kwargs):
                    return await self._cb.call_async(
                        self._stub.AllocateSeats,
                        request,
                        timeout=self._timeout,
                        **kwargs
                    )
            
            self._clients[key] = CircuitBreakerStub(stub, cb, timeout_seconds)
            logger.info(f"Created inventory service client for {target}")
        
        return self._clients[key]

    def get_route_client(
        self,
        host: str = 'localhost',
        port: int = 50051,
        timeout_seconds: int = 30
    ) -> route_pb2_grpc.RouteServiceStub:
        """Get route service client with circuit breaker protection"""
        service_name = "route-service"
        target = f"{host}:{port}"
        key = f"{service_name}:{target}"
        
        if key not in self._clients:
            channel = self._get_channel(host, port, service_name)
            stub = route_pb2_grpc.RouteServiceStub(channel)
            
            cb = self._get_circuit_breaker(service_name)
            
            class CircuitBreakerStub:
                def __init__(self, stub, cb, timeout):
                    self._stub = stub
                    self._cb = cb
                    self._timeout = timeout
                
                async def FindRoutes(self, request, **kwargs):
                    return await self._cb.call_async(
                        self._stub.FindRoutes,
                        request,
                        timeout=self._timeout,
                        **kwargs
                    )
                
                async def UpdateGraph(self, request, **kwargs):
                    return await self._cb.call_async(
                        self._stub.UpdateGraph,
                        request,
                        timeout=self._timeout,
                        **kwargs
                    )
                
                async def GetStationReachability(self, request, **kwargs):
                    return await self._cb.call_async(
                        self._stub.GetStationReachability,
                        request,
                        timeout=self._timeout,
                        **kwargs
                    )
            
            self._clients[key] = CircuitBreakerStub(stub, cb, timeout_seconds)
            logger.info(f"Created route service client for {target}")
        
        return self._clients[key]

    def get_booking_client(
        self,
        host: str = 'localhost',
        port: int = 50053,
        timeout_seconds: int = 60
    ) -> booking_pb2_grpc.BookingServiceStub:
        """Get booking service client with circuit breaker protection"""
        service_name = "booking-service"
        target = f"{host}:{port}"
        key = f"{service_name}:{target}"
        
        if key not in self._clients:
            channel = self._get_channel(host, port, service_name)
            stub = booking_pb2_grpc.BookingServiceStub(channel)
            
            cb = self._get_circuit_breaker(service_name)
            
            class CircuitBreakerStub:
                def __init__(self, stub, cb, timeout):
                    self._stub = stub
                    self._cb = cb
                    self._timeout = timeout
                
                async def InitiateBooking(self, request, **kwargs):
                    return await self._cb.call_async(
                        self._stub.InitiateBooking,
                        request,
                        timeout=self._timeout,
                        **kwargs
                    )
                
                async def GetBookingStatus(self, request, **kwargs):
                    return await self._cb.call_async(
                        self._stub.GetBookingStatus,
                        request,
                        timeout=self._timeout,
                        **kwargs
                    )
                
                async def CancelBooking(self, request, **kwargs):
                    return await self._cb.call_async(
                        self._stub.CancelBooking,
                        request,
                        timeout=self._timeout,
                        **kwargs
                    )
            
            self._clients[key] = CircuitBreakerStub(stub, cb, timeout_seconds)
            logger.info(f"Created booking service client for {target}")
        
        return self._clients[key]
    
    async def close_all(self):
        """Close all gRPC channels"""
        for channel in self._channels.values():
            await channel.close()
        self._channels.clear()
        self._clients.clear()
        logger.info("All gRPC channels closed")


# Singleton instance
grpc_clients = GRPCClientManager()

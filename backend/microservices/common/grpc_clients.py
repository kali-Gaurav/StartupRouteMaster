import grpc
import os
import sys
from typing import Optional

# Dynamically find proto-generated modules
# This is a bit hacky for the unified repo structure
def _add_proto_paths():
    base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))
    for service_dir in ['route-service', 'inventory-service', 'booking-service']:
        src_path = os.path.join(base_path, service_dir, 'src')
        if src_path not in sys.path:
            sys.path.append(src_path)

_add_proto_paths()

import route_pb2_grpc
import inventory_pb2_grpc
import booking_pb2_grpc

class GRPCClientManager:
    """Helper to manage gRPC connections across services"""
    
    def __init__(self):
        self._channels = {}
    
    def get_inventory_client(self, host: str = 'localhost', port: int = 50052):
        target = f"{host}:{port}"
        if target not in self._channels:
            channel = grpc.insecure_channel(target)
            self._channels[target] = inventory_pb2_grpc.InventoryServiceStub(channel)
        return self._channels[target]

    def get_route_client(self, host: str = 'localhost', port: int = 50051):
        target = f"{host}:{port}"
        if target not in self._channels:
            channel = grpc.insecure_channel(target)
            self._channels[target] = route_pb2_grpc.RouteServiceStub(channel)
        return self._channels[target]

    def get_booking_client(self, host: str = 'localhost', port: int = 50053):
        target = f"{host}:{port}"
        if target not in self._channels:
            channel = grpc.insecure_channel(target)
            self._channels[target] = booking_pb2_grpc.BookingServiceStub(channel)
        return self._channels[target]

# Singleton instance
grpc_clients = GRPCClientManager()

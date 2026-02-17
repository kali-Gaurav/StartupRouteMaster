#!/usr/bin/env python3
"""
Unified Microservices Startup Script
Starts all three gRPC microservices (Route, Inventory, Booking) with proper initialization
"""

import asyncio
import logging
import sys
import os
from pathlib import Path
import signal
import importlib.util

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def start_route_service():
    """Start Route Service on port 50051"""
    try:
        logger.info("Starting Route Service...")
        route_service_path = Path(__file__).parent / 'route-service' / 'src'
        server_module_path = route_service_path / 'server.py'
        
        # Load server module dynamically
        spec = importlib.util.spec_from_file_location("route_server", server_module_path)
        route_server = importlib.util.module_from_spec(spec)
        sys.modules["route_server"] = route_server
        spec.loader.exec_module(route_server)
        
        await route_server.serve()
    except Exception as e:
        logger.error(f"Route Service failed to start: {e}", exc_info=True)
        raise


async def start_inventory_service():
    """Start Inventory Service on port 50052"""
    try:
        logger.info("Starting Inventory Service...")
        inventory_service_path = Path(__file__).parent / 'inventory-service' / 'src'
        server_module_path = inventory_service_path / 'server.py'
        
        # Load server module dynamically
        spec = importlib.util.spec_from_file_location("inventory_server", server_module_path)
        inventory_server = importlib.util.module_from_spec(spec)
        sys.modules["inventory_server"] = inventory_server
        spec.loader.exec_module(inventory_server)
        
        await inventory_server.serve()
    except Exception as e:
        logger.error(f"Inventory Service failed to start: {e}", exc_info=True)
        raise


async def start_booking_service():
    """Start Booking Service on port 50053"""
    try:
        logger.info("Starting Booking Service...")
        booking_service_path = Path(__file__).parent / 'booking-service' / 'src'
        server_module_path = booking_service_path / 'server.py'
        
        # Load server module dynamically
        spec = importlib.util.spec_from_file_location("booking_server", server_module_path)
        booking_server = importlib.util.module_from_spec(spec)
        sys.modules["booking_server"] = booking_server
        spec.loader.exec_module(booking_server)
        
        await booking_server.serve()
    except Exception as e:
        logger.error(f"Booking Service failed to start: {e}", exc_info=True)
        raise


async def main():
    """Start all microservices concurrently"""
    logger.info("=" * 80)
    logger.info("IRCTC-Inspired Backend: Microservices Initialization")
    logger.info("=" * 80)
    logger.info("Services to start:")
    logger.info("  - Route Service (gRPC) on :50051")
    logger.info("  - Inventory Service (gRPC) on :50052")
    logger.info("  - Booking Service (gRPC) on :50053")
    logger.info("=" * 80)
    
    # Create tasks for all services
    tasks = [
        asyncio.create_task(start_route_service()),
        asyncio.create_task(start_inventory_service()),
        asyncio.create_task(start_booking_service()),
    ]
    
    # Handle graceful shutdown
    def handle_shutdown():
        logger.info("Shutdown signal received, stopping services...")
        for task in tasks:
            task.cancel()
    
    for sig in (signal.SIGTERM, signal.SIGINT):
        asyncio.get_event_loop().add_signal_handler(sig, handle_shutdown)
    
    try:
        # Wait for all services (they run indefinitely)
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        logger.info("All services stopped")
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        logger.info("Microservices shutdown complete")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

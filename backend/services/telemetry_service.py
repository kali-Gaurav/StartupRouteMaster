import asyncio
import logging
import json
import time
from datetime import datetime
from typing import Dict, Any
from sqlalchemy.orm import Session
from core.redis_client import async_redis_client as redis_client
from database.models import ConversionEvent

logger = logging.getLogger("routemaster.telemetry")

async def push_to_stream(event: Dict[str, Any]):
    """
    Pushes telemetry events to Redis Stream.
    O(1) complexity, non-blocking.
    """
    try:
        # Stream Key: 'search_telemetry'
        await redis_client.xadd("search_telemetry", event)
    except Exception as e:
        logger.error(f"Failed to push to telemetry stream: {e}")

async def record_conversion(db: Session, booking_id: str, search_id: str, revenue: float):
    """
    [Patent-Level] Links a booking event to a specific search intent.
    This is the core signal for our Profit Intelligence Engine.
    """
    try:
        conversion = ConversionEvent(
            recommendation_event_id=search_id,
            user_action="BOOK",
            revenue=revenue,
            timestamp=datetime.utcnow()
        )
        db.add(conversion)
        db.commit()
        logger.info(f"💰 Conversion captured: Booking {booking_id} -> Search {search_id}")
    except Exception as e:
        logger.error(f"Failed to record conversion: {e}")

def telemetry_collector(func):
    """
    Decorator for SearchService methods.
    Captures telemetry without adding latency to the user request.
    """
    async def wrapper(*args, **kwargs):
        start = time.time()
        
        # Execute the main function
        response = await func(*args, **kwargs)
        
        # Calculate latency
        latency = (time.time() - start) * 1000
        
        # Prepare payload (extract params from kwargs or args)
        event = {
            "origin": kwargs.get("source") or (args[1] if len(args) > 1 else "unknown"),
            "destination": kwargs.get("destination") or (args[2] if len(args) > 2 else "unknown"),
            "timestamp": datetime.utcnow().isoformat(),
            "latency_ms": str(latency),
            "method": func.__name__
        }
        
        # Non-blocking async task to push to Redis
        asyncio.create_task(push_to_stream(event))
        
        return response
    return wrapper

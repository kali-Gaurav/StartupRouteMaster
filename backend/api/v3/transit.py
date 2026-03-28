from fastapi import APIRouter, Request
from core.nexus.transit.stream import transit_streamer
import logging

logger = logging.getLogger("api.v3.transit")

router = APIRouter(prefix="/transit", tags=["Nexus Transit (V3)"])

@router.get("/stream")
async def transit_updates_stream(request: Request):
    """
    [Task 13.1] Real-time Transit Update Stream (SSE).
    Subscribes the client to live train delay and cancellation events.
    """
    return await transit_streamer.subscribe(request)

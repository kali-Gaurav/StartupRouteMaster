from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Path
import logging
from services.ws_manager import ws_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/booking/ws", tags=["booking_ws"])

@router.websocket("/{booking_id}")
async def booking_status_ws(
    websocket: WebSocket,
    booking_id: str = Path(...)
):
    """
    Task 42: Live WebSocket Log Streaming for Bookings.
    Allows frontend to listen for "Ghost Worker" updates.
    """
    await ws_manager.connect(booking_id, websocket)
    try:
        while True:
            # Keep connection alive
            data = await websocket.receive_text()
            # We don't expect messages from client, but we handle pong/ping if needed
    except WebSocketDisconnect:
        ws_manager.disconnect(booking_id, websocket)
        logger.info(f"Booking WebSocket disconnected: {booking_id}")
    except Exception as e:
        logger.error(f"Booking WebSocket error: {e}")
        ws_manager.disconnect(booking_id, websocket)

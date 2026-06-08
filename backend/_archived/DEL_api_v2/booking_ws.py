from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Path, Depends
import logging
import asyncio
from services.ws_manager import ws_manager
from database.session import get_db
from sqlalchemy.orm import Session
from database.models import Booking

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/booking/ws", tags=["booking_ws"])

@router.websocket("/{booking_id}")
async def booking_status_ws(
    websocket: WebSocket,
    booking_id: str = Path(...),
    db: Session = Depends(get_db)
):
    """
    Task 31: Live WebSocket Log Streaming for Bookings with Fast-Sync.
    """
    # [31.2] Secure Subscription Validation
    # In a full production env, we'd extract token from headers/query and validate user_id
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        await websocket.close(code=4004, reason="Booking not found")
        return

    # [31.4] Fast-Sync on Reconnect
    current_status = booking.escrow_status.value if hasattr(booking.escrow_status, 'value') else str(booking.escrow_status)
    
    await ws_manager.connect(booking_id, websocket, current_status=current_status)
    try:
        while True:
            # [31.5] Connection Keep-Alive
            data = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
            if data == "ping":
                await websocket.send_text("pong")
    except asyncio.TimeoutError:
        logger.info(f"Booking WS {booking_id} timeout (no ping). Disconnecting.")
        ws_manager.disconnect(booking_id, websocket)
        await websocket.close(code=1000)
    except WebSocketDisconnect:
        ws_manager.disconnect(booking_id, websocket)
        logger.info(f"Booking WebSocket disconnected: {booking_id}")
    except Exception as e:
        logger.error(f"Booking WebSocket error: {e}")
        ws_manager.disconnect(booking_id, websocket)

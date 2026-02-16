"""
Grafana Dashboard API - REST endpoints for dashboard control

Endpoints for:
- Dashboard command execution
- Real-time metrics
- Operation monitoring
- Data collection triggers
- Live data fetching
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, WebSocket
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import asyncio
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent", tags=["agent"])


# ==========================================
# PYDANTIC MODELS
# ==========================================

class DashboardCommand(BaseModel):
    """Command from Grafana dashboard."""
    command: str
    parameters: Optional[Dict[str, Any]] = {}
    priority: Optional[str] = "medium"


class UnlockRouteRequest(BaseModel):
    """Request to unlock route details."""
    train_number: str
    source: str
    dest: str
    date: str


class AvailabilityCheckRequest(BaseModel):
    """Request to check availability."""
    train_number: str
    source: str
    dest: str
    date: str
    passengers: Optional[int] = 1


# ==========================================
# DASHBOARD COMMAND ENDPOINTS
# ==========================================

@router.post("/dashboard/execute-command")
async def execute_dashboard_command(
    cmd: DashboardCommand,
    background_tasks: BackgroundTasks,
    manager=None
) -> JSONResponse:
    """
    Execute command from Grafana dashboard.
    
    Supported commands:
    - update_schedule: Update train schedules
    - update_live_status: Update live status
    - check_availability: Check availability
    - collect_all_data: Full data collection
    - generate_report: Generate report
    """
    logger.info(f"[DASHBOARD] Command received: {cmd.command}")
    
    try:
        result = await manager.execute_dashboard_command(cmd.command, cmd.parameters)
        
        return JSONResponse({
            "success": True,
            "command": cmd.command,
            "status": "executed",
            "result": result.get("result"),
            "timestamp": datetime.utcnow().isoformat(),
        })
        
    except Exception as e:
        logger.error(f"Dashboard command failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


@router.get("/dashboard/metrics")
async def get_dashboard_metrics(manager=None) -> JSONResponse:
    """
    Get metrics for Grafana dashboard.
    
    Returns:
    - Total operations
    - Success/failure rates
    - Data collected
    - Active operations
    - Next scheduled run
    """
    try:
        metrics = await manager.get_dashboard_metrics()
        
        return JSONResponse({
            "success": True,
            "metrics": metrics,
            "timestamp": datetime.utcnow().isoformat(),
        })
        
    except Exception as e:
        logger.error(f"Metrics retrieval failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


@router.get("/dashboard/operations")
async def list_operations(manager=None, limit: int = 50) -> JSONResponse:
    """
    List recent operations for dashboard.
    
    Returns list of operations with status, duration, etc.
    """
    try:
        # Get last N operations from history
        operations = manager.operation_history[-limit:]
        
        return JSONResponse({
            "success": True,
            "operations": operations,
            "total": len(manager.operation_history),
            "timestamp": datetime.utcnow().isoformat(),
        })
        
    except Exception as e:
        logger.error(f"Operations list failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


@router.get("/dashboard/operation/{operation_id}")
async def get_operation_status(operation_id: str, manager=None) -> JSONResponse:
    """
    Get status of specific operation.
    """
    try:
        status = await manager.get_operation_status(operation_id)
        
        return JSONResponse({
            "success": True,
            "operation": status,
            "timestamp": datetime.utcnow().isoformat(),
        })
        
    except Exception as e:
        logger.error(f"Operation status failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


# ==========================================
# LIVE DATA ENDPOINTS
# ==========================================

@router.post("/unlock-route-details")
async def unlock_route_details(
    request: UnlockRouteRequest,
    manager=None
) -> JSONResponse:
    """
    Live fetch route details when user unlocks.
    
    Returns:
    - Train schedule
    - Live running status
    - Seat availability
    - Fares
    - Alerts
    - Confidence scores
    """
    logger.info(f"[LIVE] Unlocking route: {request.train_number}")
    
    try:
        result = await manager.unlock_route_details(
            train_number=request.train_number,
            source=request.source,
            dest=request.dest,
            date=request.date
        )
        
        if not result.get("success"):
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": result.get("error", "Unknown error"),
                }
            )
        
        return JSONResponse({
            "success": True,
            "data": result.get("data"),
            "cached": result.get("cached", False),
            "extraction_time": result.get("extraction_time"),
            "timestamp": datetime.utcnow().isoformat(),
        })
        
    except Exception as e:
        logger.error(f"Route unlock failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


@router.post("/check-availability")
async def check_availability(
    request: AvailabilityCheckRequest,
    manager=None
) -> JSONResponse:
    """
    Real-time availability check for booking.
    
    Returns:
    - Available seats per class
    - RAC/WL status
    - Fares
    - Quotas
    - Confidence scores
    """
    logger.info(f"[LIVE] Checking availability for {request.train_number}")
    
    try:
        result = await manager.check_availability_live(
            train_number=request.train_number,
            source=request.source,
            dest=request.dest,
            date=request.date,
            passengers=request.passengers
        )
        
        if not result.get("success"):
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": result.get("error")}
            )
        
        return JSONResponse({
            "success": True,
            "available": result.get("available"),
            "classes": result.get("classes"),
            "last_updated": result.get("last_updated"),
            "next_check": result.get("next_check"),
        })
        
    except Exception as e:
        logger.error(f"Availability check failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


# ==========================================
# FRONTEND DATA ENDPOINTS
# ==========================================

@router.get("/route/{train_number}/{source}/{dest}/{date}")
async def get_route_for_frontend(
    train_number: str,
    source: str,
    dest: str,
    date: str,
    manager=None
) -> JSONResponse:
    """
    Get all route data for frontend display.
    
    Optimized response for:
    - Train details
    - Schedule
    - Live status
    - Availability
    - Fares
    - Alerts
    - Booking links
    """
    logger.info(f"[FRONTEND] Getting route data for {train_number}")
    
    try:
        result = await manager.get_route_details_for_frontend(
            train_number=train_number,
            source=source,
            dest=dest,
            date=date
        )
        
        if not result.get("success"):
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": result.get("error")}
            )
        
        return JSONResponse({
            "success": True,
            "route": result.get("data"),
            "cached": result.get("cached", False),
        })
        
    except Exception as e:
        logger.error(f"Frontend data failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


# ==========================================
# WEBSOCKET FOR REAL-TIME UPDATES
# ==========================================

active_connections: List[WebSocket] = []


@router.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket, manager=None):
    """
    WebSocket for real-time dashboard updates.
    
    Sends:
    - Operation progress
    - Metrics updates
    - Alerts
    - Status changes
    """
    await websocket.accept()
    active_connections.append(websocket)
    logger.info("Dashboard WebSocket connected")
    
    try:
        while True:
            # Send metrics every 5 seconds
            await asyncio.sleep(5)
            
            metrics = await manager.get_dashboard_metrics()
            
            await websocket.send_json({
                "type": "metrics_update",
                "metrics": metrics,
                "timestamp": datetime.utcnow().isoformat(),
            })
            
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        
    finally:
        active_connections.remove(websocket)
        logger.info("Dashboard WebSocket disconnected")


async def broadcast_update(message: Dict[str, Any]):
    """Broadcast update to all connected dashboards."""
    for connection in active_connections:
        try:
            await connection.send_json(message)
        except Exception as e:
            logger.error(f"Broadcast failed: {e}")


# ==========================================
# SCHEDULED OPERATIONS ENDPOINTS
# ==========================================

@router.post("/operations/collect-monthly-schedules")
async def trigger_monthly_collection(
    background_tasks: BackgroundTasks,
    manager=None
) -> JSONResponse:
    """Manually trigger monthly schedule collection."""
    
    def run_collection():
        asyncio.run(manager.collect_monthly_schedule_updates())
    
    background_tasks.add_task(run_collection)
    
    return JSONResponse({
        "success": True,
        "status": "collection_started",
        "message": "Monthly schedule collection has been triggered",
    })


@router.post("/operations/update-live-status")
async def trigger_live_status_update(
    background_tasks: BackgroundTasks,
    manager=None
) -> JSONResponse:
    """Manually trigger live status update."""
    
    def run_update():
        asyncio.run(manager.collect_daily_live_status())
    
    background_tasks.add_task(run_update)
    
    return JSONResponse({
        "success": True,
        "status": "update_started",
        "message": "Live status update has been triggered",
    })


@router.get("/operations/schedule")
async def get_operation_schedule(manager=None) -> JSONResponse:
    """Get scheduled operation times."""
    
    return JSONResponse({
        "success": True,
        "schedule": {
            "monthly_schedule_update": "1st of month at 2:00 AM IST",
            "daily_live_status": "Daily at 3:00 AM IST",
            "hourly_live_checks": "Every hour",
            "weekly_maintenance": "Sundays at 4:00 AM IST",
        },
    })

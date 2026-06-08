"""
System API routes
"""
from fastapi import APIRouter

router = APIRouter(tags=["system"])

@router.get("/health")
async def system_health():
    return {"status": "healthy", "service": "system"}

@router.get("/version")
async def system_version():
    return {"version": "3.0.0", "name": "RouteMaster"}

@router.get("/config")
async def system_config():
    return {"environment": "development", "mode": "standard"}

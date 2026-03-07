from fastapi import APIRouter
from utils.external_api_health import api_health

router = APIRouter(prefix="/monitoring", tags=["monitoring"])

@router.get("/external-health")
async def get_external_health():
    """
    Task 29.5: Get real-time health and latency metrics for external APIs.
    """
    return api_health.get_status()

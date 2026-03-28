from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from database.session import AsyncSessionUser
from database.models import APIBudget
from core.metrics import jit_metrics
from typing import List, Dict, Any

router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("/debug/budget", response_model=List[Dict[str, Any]])
async def get_api_budgets():
    """[Task 26] Fetch current API spending vs limits."""
    try:
        async with AsyncSessionUser() as session:
            stmt = select(APIBudget)
            result = await session.execute(stmt)
            budgets = result.scalars().all()
            
            return [
                {
                    "provider": b.provider_name,
                    "spent": float(b.current_spend),
                    "limit": float(b.monthly_limit),
                    "is_active": b.is_active,
                    "usage_percent": round((b.current_spend / b.monthly_limit) * 100, 2) if b.monthly_limit > 0 else 0
                }
                for b in budgets
            ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/debug/metrics")
async def get_system_metrics():
    """[Task 25/26] Fetch internal telemetry report."""
    return jit_metrics.get_report()

@router.get("/debug/providers")
async def get_provider_status():
    """[Task 25] Fetch circuit breaker states."""
    from providers.gateway import provider_gateway
    return await provider_gateway.get_health()

from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

from backend.services.cache_service import cache_service

router = APIRouter(prefix="/api/flow", tags=["flow"])

_redis = cache_service.redis if cache_service and cache_service.is_available() else None
_local_flow: Dict[str, Dict[str, Any]] = {}
FLOW_KEY_PREFIX = "flow:"
FLOW_INDEX_KEY = "flow:ids"

class FlowAckPayload(BaseModel):
    correlation_id: str
    event: str
    payload: Optional[Dict[str, Any]] = None

class FlowStatusResponse(BaseModel):
    active_flows: int
    completed_flows: int
    failed_flows: int
    avg_completion_time_sec: Optional[float] = None
    active_correlation_ids: Optional[List[str]] = None
    warnings: Optional[List[str]] = None


def _flow_key(correlation_id: str) -> str:
    return f"{FLOW_KEY_PREFIX}{correlation_id}"


def _load_flow(correlation_id: str) -> Dict[str, Any]:
    if _redis:
        try:
            raw = _redis.get(_flow_key(correlation_id))
            if raw:
                import json
                return json.loads(raw)
        except Exception:
            pass
    return _local_flow.get(correlation_id, {"start_time": datetime.utcnow().isoformat(), "events": [], "status": "active"})


def _save_flow(correlation_id: str, data: Dict[str, Any]):
    if _redis:
        try:
            import json
            _redis.set(_flow_key(correlation_id), json.dumps(data))
            _redis.sadd(FLOW_INDEX_KEY, correlation_id)
            return
        except Exception:
            pass
    _local_flow[correlation_id] = data


@router.post("/ack")
async def ack_flow(payload: FlowAckPayload):
    cid = payload.correlation_id
    flow = _load_flow(cid)

    if "start_time" not in flow:
        flow["start_time"] = datetime.utcnow().isoformat()

    flow.setdefault("events", []).append({
        "event": payload.event,
        "timestamp": datetime.utcnow().isoformat(),
        "payload": payload.payload,
    })

    if payload.event in ("PAYMENT_CONFIRMED", "UI_CONFIRMED"):
        flow["status"] = "completed"
        flow["end_time"] = datetime.utcnow().isoformat()
    elif "FAIL" in payload.event.upper():
        flow["status"] = "failed"
        flow["end_time"] = datetime.utcnow().isoformat()

    _save_flow(cid, flow)
    return {"message": "Flow event acknowledged"}


@router.get("/status", response_model=FlowStatusResponse)
async def get_flow_status():
    ids = []
    if _redis:
        try:
            ids = list(_redis.smembers(FLOW_INDEX_KEY) or [])
        except Exception:
            ids = list(_local_flow.keys())
    else:
        ids = list(_local_flow.keys())

    active = completed = failed = 0
    total_time = 0.0
    completed_count = 0
    active_ids = []
    warnings = []

    for cid in ids:
        f = _load_flow(cid)
        status = f.get("status", "active")
        if status == "active":
            active += 1
            active_ids.append(cid)
        elif status == "completed":
            completed += 1
            if f.get("start_time") and f.get("end_time"):
                try:
                    from datetime import datetime
                    st = datetime.fromisoformat(f["start_time"])
                    et = datetime.fromisoformat(f["end_time"])
                    total_time += (et - st).total_seconds()
                    completed_count += 1
                except Exception:
                    pass
        elif status == "failed":
            failed += 1
            warnings.append(f"Flow {cid} failed.")

    avg = (total_time / completed_count) if completed_count else None
    return FlowStatusResponse(
        active_flows=active,
        completed_flows=completed,
        failed_flows=failed,
        avg_completion_time_sec=avg,
        active_correlation_ids=active_ids,
        warnings=warnings,
    )

"""
🌊 SSE Progressive Route Delivery — Feature A
SIGMA / KYLO Implementation

Streams route results progressively using Server-Sent Events.
Users see direct trains in < 500ms, transfer routes stream in as found.
This makes the app feel 10x faster with zero additional compute.
"""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, date
from typing import AsyncGenerator, Optional

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from services.route_engine import get_route_engine
from services.intelligence.demand_service import demand_service

logger = logging.getLogger("api.sse")

router = APIRouter(prefix="/api/v1/search", tags=["search-sse"])


def _sse_event(event: str, data: dict) -> str:
    """Format a single SSE message."""
    payload = json.dumps(data, default=str)
    return f"event: {event}\ndata: {payload}\n\n"


async def _route_stream_generator(
    source: str,
    destination: str,
    travel_date: str,
    max_transfers: int,
    class_type: Optional[str],
    persona: str,
    search_id: str,
) -> AsyncGenerator[str, None]:
    """
    Core async generator: yields SSE events as routes are discovered.

    Phase 1 — Direct trains (< 500ms)
    Phase 2 — 1-transfer routes (< 1500ms)
    Phase 3 — 2-transfer routes (< 3000ms)
    Final   — Completion event with metadata
    """
    start_time = time.time()
    total_routes = 0

    # Announce search start
    yield _sse_event("search_start", {
        "search_id": search_id,
        "source": source,
        "destination": destination,
        "travel_date": travel_date,
        "persona": persona,
        "timestamp": datetime.utcnow().isoformat(),
    })

    # Log demand intent (Pillar 3)
    demand_service.log_search_intent(source, destination, persona)

    try:
        parsed_date = datetime.strptime(travel_date, "%Y-%m-%d").date()
    except ValueError:
        yield _sse_event("error", {"message": "Invalid date format. Use YYYY-MM-DD."})
        return

    route_engine = get_route_engine()

    # ── Phase 1: Direct Trains ──────────────────────────────────────────────
    try:
        yield _sse_event("phase_start", {"phase": 1, "label": "Direct Trains"})

        direct_routes = await route_engine.search_routes(
            source_code=source.upper(),
            dest_code=destination.upper(),
            travel_date=parsed_date,
            max_transfers=0,
            class_type=class_type,
            persona=persona,
        )

        for journey in direct_routes:
            route_dict = _serialize_journey(journey, phase=1)
            yield _sse_event("route", route_dict)
            total_routes += 1
            # Small pause to allow client to render
            await asyncio.sleep(0)

        phase1_ms = int((time.time() - start_time) * 1000)
        yield _sse_event("phase_complete", {
            "phase": 1,
            "routes_found": len(direct_routes),
            "elapsed_ms": phase1_ms,
        })

    except Exception as e:
        logger.warning(f"[SSE:Phase1] Error: {e}")
        yield _sse_event("phase_error", {"phase": 1, "message": str(e)})

    # ── Phase 2: 1-Transfer Routes ───────────────────────────────────────────
    if max_transfers >= 1:
        try:
            yield _sse_event("phase_start", {"phase": 2, "label": "1-Transfer Routes"})

            one_transfer = await route_engine.search_routes(
                source_code=source.upper(),
                dest_code=destination.upper(),
                travel_date=parsed_date,
                max_transfers=1,
                class_type=class_type,
                persona=persona,
            )

            for journey in one_transfer:
                route_dict = _serialize_journey(journey, phase=2)
                yield _sse_event("route", route_dict)
                total_routes += 1
                await asyncio.sleep(0)

            phase2_ms = int((time.time() - start_time) * 1000)
            yield _sse_event("phase_complete", {
                "phase": 2,
                "routes_found": len(one_transfer),
                "elapsed_ms": phase2_ms,
            })

        except Exception as e:
            logger.warning(f"[SSE:Phase2] Error: {e}")
            yield _sse_event("phase_error", {"phase": 2, "message": str(e)})

    # ── Phase 3: 2-Transfer Routes ───────────────────────────────────────────
    if max_transfers >= 2:
        try:
            yield _sse_event("phase_start", {"phase": 3, "label": "2-Transfer Routes"})

            two_transfer = await route_engine.search_routes(
                source_code=source.upper(),
                dest_code=destination.upper(),
                travel_date=parsed_date,
                max_transfers=2,
                class_type=class_type,
                persona=persona,
            )

            for journey in two_transfer:
                route_dict = _serialize_journey(journey, phase=3)
                yield _sse_event("route", route_dict)
                total_routes += 1
                await asyncio.sleep(0)

            phase3_ms = int((time.time() - start_time) * 1000)
            yield _sse_event("phase_complete", {
                "phase": 3,
                "routes_found": len(two_transfer),
                "elapsed_ms": phase3_ms,
            })

        except Exception as e:
            logger.warning(f"[SSE:Phase3] Error: {e}")
            yield _sse_event("phase_error", {"phase": 3, "message": str(e)})

    # ── Final: Search Complete ───────────────────────────────────────────────
    total_ms = int((time.time() - start_time) * 1000)
    yield _sse_event("search_complete", {
        "search_id": search_id,
        "total_routes": total_routes,
        "total_elapsed_ms": total_ms,
        "timestamp": datetime.utcnow().isoformat(),
    })


def _serialize_journey(journey, phase: int) -> dict:
    """Convert a Journey object to a clean SSE-safe dict."""
    try:
        segments = [
            {
                "train_number": s.train_number,
                "train_name": getattr(s, "train_name", ""),
                "from_station": s.from_station_code,
                "to_station": s.to_station_code,
                "departure_time": str(s.departure_time),
                "arrival_time": str(s.arrival_time),
                "duration_minutes": s.duration_minutes,
                "class_type": getattr(s, "class_type", None),
                "fare": getattr(s, "fare", 0),
                "availability": getattr(s, "availability", "UNKNOWN"),
            }
            for s in journey.segments
        ]
        return {
            "discovery_phase": phase,
            "journey_id": journey.journey_id,
            "train_numbers": [s.train_number for s in journey.segments],
            "from_station": journey.segments[0].from_station_code,
            "to_station": journey.segments[-1].to_station_code,
            "departure_time": str(journey.departure_time),
            "arrival_time": str(journey.arrival_time),
            "duration_minutes": journey.total_duration,
            "transfers": journey.transfers,
            "total_fare": journey.total_fare,
            "demand_factor": getattr(journey, "demand_factor", 1.0),
            "safety_score": getattr(journey, "safety_score", 0.5),
            "tis_score": getattr(journey, "tis_score", None),  # Transfer Intelligence Score
            "tis_risk": getattr(journey, "tis_risk", None),    # HIGH_RISK / MODERATE / LOW
            "availability_status": getattr(journey, "availability_status", "UNKNOWN"),
            "persona_tags": getattr(journey, "persona_tags", []),
            "segments": segments,
        }
    except Exception as e:
        logger.error(f"[SSE] Serialization error: {e}")
        return {"error": "Serialization failed", "discovery_phase": phase}


@router.get("/stream")
async def stream_routes(
    source: str = Query(..., min_length=2, max_length=10, description="Origin station code"),
    destination: str = Query(..., min_length=2, max_length=10, description="Destination station code"),
    travel_date: str = Query(..., description="Travel date YYYY-MM-DD"),
    max_transfers: int = Query(2, ge=0, le=3, description="Maximum number of transfers"),
    class_type: Optional[str] = Query(None, description="Coach class (SL, 3A, 2A, 1A)"),
    persona: str = Query("comfort", description="Ranking persona: comfort, budget, fast"),
):
    """
    🌊 Progressive Route Search via Server-Sent Events (SSE)

    Returns routes in real-time phases:
    - **Phase 1**: Direct trains (fastest, < 500ms)
    - **Phase 2**: 1-transfer connections (< 1500ms)
    - **Phase 3**: 2-transfer connections (< 3000ms)

    Each event is self-contained and can be rendered immediately by the client.
    This endpoint dramatically improves perceived performance.

    **Event Types:**
    - `search_start` — Search metadata
    - `phase_start` — Phase beginning
    - `route` — Individual route result (stream these to the UI)
    - `phase_complete` — Phase done with count + elapsed time
    - `search_complete` — All phases done
    - `error` / `phase_error` — Error events
    """
    search_id = str(uuid.uuid4())

    generator = _route_stream_generator(
        source=source,
        destination=destination,
        travel_date=travel_date,
        max_transfers=max_transfers,
        class_type=class_type,
        persona=persona,
        search_id=search_id,
    )

    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",       # Disable nginx buffering
            "Connection": "keep-alive",
            "X-Search-ID": search_id,
        },
    )

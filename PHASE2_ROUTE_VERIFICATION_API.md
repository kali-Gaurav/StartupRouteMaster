# Phase 2 Route Verification & Graph API Proposal

## 1. Current State Summary
- `SearchService` uses the lazy `route_engine`/`RailwayRouteEngine` to build hybrid RAPTOR routes backed by snapshots (`SnapshotManager`), real-time overlays, and ML ranking.
- `/api/v2/journey/{journey_id}/unlock-details` currently delegates to `SearchService.unlock_journey_details`, reconstructing the journey (segments, transfers) via `JourneyReconstructionEngine`, allocating seats, and calling `verification_service.verify_journey`.
- `RouteVerificationService` (used by the unlock payment flow) orchestrates seat/fare verification through `DataProvider`, which prefers RapidAPI (with Redis caching) and gracefully falls back to database lookups.
- `DetailedJourneyResponse` today exposes `journey`, `segments`, `seat_allocation`, `verification`, `fare_breakdown`, and `can_unlock_details`, but lacks:
  - Explicit transfer nodes or graph metadata that the frontend/chatbot can visualize.
  - Verification status tied to each segment (source = RapidAPI vs database).
  - A clear signal for which verification steps succeeded via RapidAPI versus fallback.

## 2. Gap Audit (Phase 2 Unlock Visualization Needs)
| Requirement | Current Coverage | Gap | Proposal |
|---|---|---|---|
| Route graph + transfers for UI/graph rendering | Journey segments are returned, but transfers/junction metadata is missing | UI cannot draw the full graph for direct/multi-transfer journeys | Extend response to include `route_graph` block with nodes for segments and explicit transfer edges. Include station codes, scheduled times, distances, transfer wait minutes, and `is_direct` flag.
| RapidAPI verification transparency | Overall `verification` dict exists, but there is no `source` metadata per class or segment | Frontend/chatbot cannot indicate whether RapidAPI or DB data is driving availability/fare | Enhance verification payload with `source` flags, last cache key used, and `status` per class (SL, AC3). Align with `DataProvider` results that already include `source` in seat/fare responses.
| Unlock readiness storytelling | Response only says `can_unlock_details` and high-level fare/seat data | Hard to compose chatbot/narrative like “RapidAPI seat check verified 3A for this direct route” | Add `verification_summary` that cites API call counts (`api_calls_made`), warnings, and availability booleans, so the UI can surface friendly messages.
| Unlock route metadata for chatbot/graph | Route ID -> unlock flow uses `journey_id` but does not expose encoded segments/transfers | Chatbot cannot easily describe the route path | Provide `route_graph.nodes` + `route_graph.edges`, referencing station codes, trains, durations, and `transfer_reason` details.

## 3. Proposed API Extensions
### 3.1 Schema additions (extend `DetailedJourneyResponse`)
```python
class RouteGraphNode(BaseModel):
    segment_id: str
    train_number: str
    train_name: Optional[str]
    from_station_code: str
    to_station_code: str
    departure_time: str  # ISO or HH:MM
    arrival_time: str
    duration_minutes: int
    distance_km: float
    coach_preference: str
    verification_source: Optional[str]
    availability_status: str

class RouteGraphEdge(BaseModel):
    from_segment_id: str
    to_segment_id: str
    transfer_station_code: str
    wait_minutes: int
    platform: Optional[str]
    transfer_reason: str  # e.g., "Interchange" or "Through trip"

class VerificationSummary(BaseModel):
    rapidapi_calls: int
    seat_availability: Dict[str, Dict]
    fare_verification: Dict[str, Dict]
    warnings: List[str]
```
- Add `route_graph: Dict[str, Any]` to the response with `nodes` and `edges` lists.
- Update each `segment` in the existing `segments` array to include `verification_source` and `availability_status` so the frontend can color-code the route.

### 3.2 Response payload fields
Expand `/api/v2/journey/{journey_id}/unlock-details` to return:
```json
{
  "journey": {...},
  "route_graph": {
    "nodes": [...],
    "edges": [...],
    "is_direct": true/false
  },
  "verification_summary": {
    "rapidapi_calls": 4,
    "seat_availability": {
      "SL": {"status": "verified", "source": "rapidapi", "available_seats": 22},
      "AC3": {"status": "pending", "source": "database", "available_seats": 10}
    },
    "fare_verification": {...},
    "warnings": [...]
  }
}
```
- Include `segment_id` references so clients can correlate nodes with journey segments.
- Provide `route_graph.transfer_count` and `graph_summary` describing total distance/time.

### 3.3 Optional helper endpoint (if decoupling is easier)
Add `/api/v2/journey/{journey_id}/graph` returning only the route graph + verification metadata to keep `/unlock-details` lean for payment clients that don’t need the extra fields.

## 4. Implementation Plan
1. **Data extraction**: Use `JourneyReconstructionEngine` output (via `SearchService.unlock_journey_details`) to build `route_graph.nodes/edges`. Each `RouteSegment` already contains departure/arrival/station codes; extend `search_service` helper `_format_route_for_frontend` or a new serializer to include segment IDs and verifying metadata.
2. **Verification enrichment**: In `RouteVerificationService`, propagate `source` (RapidAPI vs database) from `_verify_seat_availability` and `_verify_fare` into `verification_results`, and return the raw `api_calls_made`/`warnings` data. `SearchService.unlock_journey_details` should merge that into `verification_summary` before sending the response.
3. **Schema updates**: Extend `schemas.DetailedJourneyResponse` or create supporting models (above) in `backend/schemas.py`. Keep existing UI consumers working by marking new fields as optional.
4. **API changes**: Update `backend/api/integrated_search.py` to include the new JSON structure, and document this contract for the frontend/chatbot teams.
5. **Testing & docs**: Add tests covering direct/multi-transfer journeys to ensure the graph metadata and verification summary populate correctly. Update Phase 2 audit doc with before/after payloads.

## 5. Live API configuration checklist

Before the verification graph can consistently surface RapidAPI-backed data (and to move the system from `OFFLINE` to `HYBRID/ONLINE` mode), make sure the following environment variables are populated and the service restarted:

- `RAPIDAPI_KEY` – required for `RapidAPIClient`, `SeatAvailabilityManager`, and the Data Provider.
- `LIVE_FARES_API`, `LIVE_DELAY_API`, `LIVE_SEAT_API`, `LIVE_BOOKING_API` – set each to the corresponding RapidAPI or partner endpoint. The system treats an empty value as “use database only.”
- `OFFLINE_MODE=false`, `REAL_TIME_ENABLED=true`, `BOOKING_ENABLED=true` – ensure the master feature flags allow realtime verification.
- `LIVE_API_TIMEOUT_MS`, `LIVE_API_RETRY_COUNT` – tune these if the RapidAPI endpoints are slower than desired; defaults are 500ms/1 retry.
- `GRAPH_HMAC_SECRET` and `ROUTE_GRAPH_REDIS_KEY` – if the new graph insights are signed/stored in Redis, these must match your redis-backed keyspace.

After populating the `.env` file or deploying these variables, restart the FastAPI backend so `Config.get_mode()` reports `HYBRID` or `ONLINE` in the startup logs and `DataProvider.detect_available_features()` marks the APIs as available. The `SearchService.unlock_journey_details` response will then include `verification_summary` entries that reference actual `RapidAPI` sources and `route_graph` nodes with accurate transfer metadata.

> ⚠️ **Payment & Booking Deferred** – the current rollout focuses strictly on route search, graph construction and live verification. Booking/payment endpoints are deliberately disabled (`BOOKING_ENABLED=false`) and `LIVE_BOOKING_API` left blank; these will be integrated in a later phase after the core workflow is validated.
>
> 📍 **Domain configuration** – once your public domain is registered, set `FRONTEND_API_URL`/`FRONTEND_BASE_URL` in the env files. All API clients (mobile, web) should use that host instead of localhost.

## 6. Next Steps
- Implement the schema + service updates to return the new `route_graph` + `verification_summary` payloads.
- Collaborate with frontend/chatbot owners to iterate on the JSON shape (transfer naming, station info, etc.).
- Once graph data is stabilized, revisit the payment/webhook tests to finish the Phase 2 checklist.
- After the API changes land, run the targeted payment webhook tests, then finalize the Phase 2 gap audit report (this document can be referenced in that audit).

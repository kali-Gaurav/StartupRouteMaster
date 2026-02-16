"""
RouteMaster Agent v2 - Complete Integration Architecture

This document shows how all components work together:
- Core intelligence engines
- Manager orchestrator
- Dashboard API
- Backend integration
- Frontend data serving
- Scheduled operations
- Live data fetching
"""

ARCHITECTURE = """

╔══════════════════════════════════════════════════════════════════════════╗
║                      ROUTEMASTER AGENT V2 - COMPLETE SYSTEM              ║
╚══════════════════════════════════════════════════════════════════════════╝


1. GRAFANA DASHBOARD
   ├─ User selects command (e.g., "Unlock Route Details")
   ├─ Sends to Dashboard API
   └─ Receives real-time updates via WebSocket


2. DASHBOARD API (api_dashboard.py)
   ├─ POST /api/agent/dashboard/execute-command
   ├─ GET  /api/agent/dashboard/metrics
   ├─ GET  /api/agent/dashboard/operations
   ├─ POST /api/agent/unlock-route-details         ← LIVE FETCHING
   ├─ POST /api/agent/check-availability           ← LIVE FETCHING
   ├─ GET  /api/agent/route/{train}/{src}/{dst}... ← FRONTEND DATA
   └─ WS   /api/agent/ws/dashboard                 ← REAL-TIME UPDATES


3. MANAGER ORCHESTRATOR (manager.py)
   ├─ Scheduled Operations
   │  ├─ collect_monthly_schedule_updates()    (Monthly at 2 AM)
   │  └─ collect_daily_live_status()           (Daily at 3 AM)
   │
   ├─ Live Data Fetching
   │  ├─ unlock_route_details()                (On-demand)
   │  └─ check_availability_live()             (On-demand)
   │
   └─ Dashboard Commands
      ├─ execute_dashboard_command()
      ├─ get_dashboard_metrics()
      └─ get_operation_status()


4. CORE INTELLIGENCE ENGINES
   ├─ ReasoningLoop
   │  ├─ OBSERVE   → Screenshot + DOM
   │  ├─ THINK     → Gemini analysis
   │  ├─ DECIDE    → Strategy selection
   │  ├─ ACT       → Navigation
   │  ├─ VERIFY    → Extraction
   │  ├─ STORE     → Database update
   │  └─ LEARN     → Memory update
   │
   ├─ NavigatorAI
   │  ├─ find_element_by_visual_label()
   │  ├─ find_button_by_intent()
   │  └─ navigate_pagination()
   │
   ├─ VisionAI
   │  ├─ analyze_page_structure()
   │  ├─ detect_table_structure()
   │  └─ understand_page_intent()
   │
   ├─ ExtractionAI
   │  ├─ extract_with_confidence()
   │  └─ extract_table_data()
   │
   ├─ DecisionEngine
   │  ├─ decide_data_validity()
   │  ├─ decide_storage_action()
   │  └─ decide_retry_strategy()
   │
   └─ GeminiClient
      ├─ analyze_page_layout()
      ├─ extract_field()
      └─ infer_data_schema()


5. DATABASE
   ├─ trains_master          (Train metadata)
   ├─ train_stations         (Schedule)
   ├─ train_live_status      (Current position)
   ├─ seat_availability      (Booking info)
   ├─ schedule_change_log    (History)
   └─ rma_alerts             (Alerts)


6. BACKEND API (main.py integration)
   ├─ POST /api/enrich-trains
   ├─ POST /api/unlock-route-details
   ├─ POST /api/admin/run-rma-tests
   └─ POST /api/admin/detect-changes


7. FRONTEND
   ├─ Route Display
   │  ├─ Train info
   │  ├─ Schedule with stations
   │  ├─ Live status with delays
   │  ├─ Seat availability
   │  └─ Fare information
   │
   └─ Booking Integration
      ├─ Check availability real-time
      ├─ Lock seats
      └─ Proceed to payment


╔══════════════════════════════════════════════════════════════════════════╗
║                         DATA FLOW SCENARIOS                              ║
╚══════════════════════════════════════════════════════════════════════════╝


SCENARIO 1: MONTHLY SCHEDULED UPDATE
╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌

Time: 1st of month @ 2:00 AM
Trigger: Scheduler (scheduler.py)

Flow:
1. Scheduler calls manager.collect_monthly_schedule_updates()
2. Manager gets list of all trains from DB
3. For each train:
   a. Create task: "extract schedule for train X"
   b. ReasoningLoop executes autonomously
   c. OBSERVE → page structure
   d. THINK → Gemini analyzes
   e. DECIDE → extraction strategy
   f. ACT → navigate NTES website
   g. VERIFY → extract stations
   h. STORE → update database
   i. LEARN → update memory
4. Collect all results
5. Detect changes (compare with previous version)
6. Store in schedule_change_log
7. Generate report
8. Return to scheduler

Result:
✓ All train schedules updated
✓ Changes detected and logged
✓ Metrics updated
✓ Dashboard shows success


SCENARIO 2: LIVE DATA FETCHING (User Unlocks Route)
╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌

Time: On-demand (user action)
Trigger: Frontend clicks "Unlock Route Details" → API call

Flow:
1. Frontend sends: POST /api/agent/unlock-route-details
   {
     "train_number": "12951",
     "source": "NDLS",
     "dest": "CNB",
     "date": "2026-02-17"
   }

2. API checks cache (5 min TTL)
   - If fresh cached data exists → return immediately
   - Else → fetch fresh data

3. Manager calls unlock_route_details()

4. Parallel fetching:
   a. Fetch schedule (from NTES via ReasoningLoop)
   b. Fetch live status (from NTES via ReasoningLoop)
   c. Fetch availability (from IRCTC/AskDisha via ReasoningLoop)

5. For each fetch:
   - Execute full reasoning loop
   - Get data with confidence scores
   - Return results

6. Compile response:
   {
     "train_info": {...},
     "schedule": [...],
     "live_status": {...},
     "availability": [...],
     "fares": [...],
     "alerts": [...],
     "confidence_scores": {...}
   }

7. Cache result (5 min)

8. Return to frontend

Frontend receives:
✓ Complete route information
✓ Current status
✓ Availability
✓ Fares
✓ Confidence scores on each field
✓ Alerts if any


SCENARIO 3: GRAFANA DASHBOARD COMMAND
╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌

Time: On-demand (operator action)
Trigger: Grafana dashboard command

Flow:
1. Operator clicks "Update Live Status" in dashboard

2. Dashboard sends:
   POST /api/agent/dashboard/execute-command
   {
     "command": "update_live_status",
     "parameters": {}
   }

3. API routes to manager.execute_dashboard_command()

4. Manager executes collect_daily_live_status()

5. Operation runs in background

6. WebSocket sends progress updates:
   - "operation_started"
   - "processing_train_X"
   - "trains_updated: 10"
   - "operation_completed"

7. Dashboard updates in real-time
   - Success rate: 95%
   - Trains updated: 185
   - Alerts: 3
   - Duration: 45 seconds

Dashboard shows:
✓ Live metrics
✓ Operation progress
✓ Final results
✓ Alerts if any


╔══════════════════════════════════════════════════════════════════════════╗
║                      COMPONENT INTERACTIONS                              ║
╚══════════════════════════════════════════════════════════════════════════╝


1. Scheduler ← → Manager
   - Scheduler calls scheduled methods on Manager
   - Manager reports metrics back to Scheduler

2. Dashboard API ← → Manager
   - Dashboard API calls Manager methods
   - Manager returns results
   - Dashboard API formats for Grafana/Frontend

3. Manager ← → ReasoningLoop
   - Manager creates tasks
   - ReasoningLoop executes autonomously
   - Returns extracted data with confidence

4. ReasoningLoop ← → Core Engines
   - Orchestrates all engines
   - NavigatorAI finds elements
   - VisionAI understands layout
   - ExtractionAI pulls data
   - DecisionEngine validates
   - GeminiClient reasons

5. Engines ← → Database
   - Read from: train_master, historical data
   - Write to: live_status, schedules, availability, logs

6. Database ← → Backend API
   - Backend queries database for user requests
   - Returns formatted data to frontend

7. Backend API ← → Frontend
   - Frontend makes requests
   - Backend returns data
   - Frontend displays to user


╔══════════════════════════════════════════════════════════════════════════╗
║                        INTEGRATION STEPS                                 ║
╚══════════════════════════════════════════════════════════════════════════╝


STEP 1: Wire Manager to Scheduler
────────────────────────────────

In scheduler.py, update scheduled tasks:

    async def _execute_monthly_update(self):
        # OLD:
        # await self.controller.execute_task(task_def)
        
        # NEW:
        from routemaster_agent.manager import RouteMasterAgentManager
        manager = RouteMasterAgentManager(self.reasoning_loop, db)
        result = await manager.collect_monthly_schedule_updates()
        print(f"Monthly update: {result['report']}")


STEP 2: Wire Dashboard API to main.py
────────────────────────────────────

In main.py:

    from routemaster_agent.api_dashboard import router as dashboard_router
    from routemaster_agent.manager import RouteMasterAgentManager
    
    app.include_router(dashboard_router)
    
    # Create manager instance
    @app.on_event("startup")
    async def startup():
        global manager
        manager = RouteMasterAgentManager(
            reasoning_loop=autonomous_scheduler.controller.reasoning_loop,
            db_session=SessionLocal()
        )


STEP 3: Wire Manager to API Routes
─────────────────────────────────

In api_dashboard.py, inject manager:

    @app.post("/api/agent/unlock-route-details")
    async def unlock_route_details(request: UnlockRouteRequest):
        # manager is injected by FastAPI dependency injection
        result = await manager.unlock_route_details(...)
        return result


STEP 4: Create Grafana Dashboard
───────────────────────────────

Dashboard panels:

Panel 1: Metrics
   - Query: GET /api/agent/dashboard/metrics
   - Display: Total operations, Success rate, Data collected
   - Refresh: 30 seconds

Panel 2: Recent Operations
   - Query: GET /api/agent/dashboard/operations
   - Display: Table of recent operations
   - Refresh: 60 seconds

Panel 3: Command Controls
   - Buttons for dashboard commands
   - POST /api/agent/dashboard/execute-command
   - Commands: Update Schedule, Update Live Status, etc.

Panel 4: Operation Status
   - WebSocket: ws://localhost:8000/api/agent/ws/dashboard
   - Real-time updates
   - Progress bars

Panel 5: Alerts
   - Query: GET /api/agent/dashboard/operations
   - Filter: Failed operations
   - Alert threshold: 5 failures


╔══════════════════════════════════════════════════════════════════════════╗
║                         FILE STRUCTURE                                   ║
╚══════════════════════════════════════════════════════════════════════════╝

routemaster_agent/
├── core/
│   ├── navigator_ai.py          ✓ (created)
│   ├── vision_ai.py             ✓ (created)
│   ├── extractor_ai.py          ✓ (created)
│   ├── decision_engine.py       ✓ (created)
│   ├── reasoning_loop.py        ✓ (created)
│   └── __init__.py              ✓ (created)
│
├── ai/
│   ├── gemini_client.py         ✓ (created)
│   ├── planner.py               ✓ (existing)
│   ├── reasoning_controller.py  ✓ (existing)
│   └── agent_state_manager.py   ✓ (existing)
│
├── manager.py                   ✓ (created) - ORCHESTRATOR
├── api_dashboard.py             ✓ (created) - DASHBOARD API
│
├── main.py                      (needs update)
├── scheduler.py                 (needs update)
├── command_interface.py         (needs update)
│
├── database/
│   ├── models.py                ✓ (existing)
│   └── db.py                    ✓ (existing)
│
├── pipeline/
│   ├── processor.py             ✓ (existing)
│   └── data_cleaner.py          ✓ (existing)
│
└── scrapers/
    ├── ntes_agent.py            ✓ (existing)
    └── disha_agent.py           ✓ (existing)


╔══════════════════════════════════════════════════════════════════════════╗
║                         QUICK START                                      ║
╚══════════════════════════════════════════════════════════════════════════╝

1. Set Gemini API Key
   export GEMINI_API_KEY="your-key"

2. Install dependencies
   pip install google-generativeai

3. Wire manager to main.py
   (See Step 2 above)

4. Run server
   uvicorn routemaster_agent.main:app --reload

5. Test endpoints
   curl -X POST http://localhost:8000/api/agent/dashboard/metrics

6. Setup Grafana
   - Add data source: http://localhost:8000
   - Create dashboard with panels above

7. Start using!
   - Dashboard commands available
   - Live data fetching ready
   - Frontend can call /api/agent/route/...
"""


if __name__ == "__main__":
    print(ARCHITECTURE)

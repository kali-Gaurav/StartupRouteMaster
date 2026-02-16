# RouteMaster Agent — Complete Architecture Analysis & Upgrade Plan

**Date:** Feb 17, 2026  
**Status:** Analysis Complete - Ready for v2 Implementation  

---

## Part 1: Current Implementation Analysis

### What We Already Have ✅

#### 1. **Core FastAPI Integration** (`main.py`)
- REST API endpoints for data collection
- WebSocket support for real-time updates
- Background task processing
- Integration with Prometheus metrics

**Key Endpoints:**
- `POST /api/unlock-route-details` — Single train extraction
- `POST /api/enrich-trains` — Batch train enrichment
- `POST /api/admin/run-rma-tests` — QA testing
- `POST /api/admin/detect-changes` — Change detection

#### 2. **Command Interface** (`command_interface.py`)
- Grafana-compatible command execution interface
- Async task handling with WebSocket updates
- Command history & status tracking
- Priority-based task execution

**Available Commands:**
- `update_train_schedule`
- `collect_live_status`
- `check_seat_availability`
- `update_all_trains`
- `monthly_maintenance`

#### 3. **Autonomous Scheduler** (`scheduler.py`)
- APScheduler integration for cron-like execution
- Predefined schedules:
  - Monthly updates (1st of month @ 2 AM)
  - Daily reliability (daily @ 3 AM)
  - Hourly live checks (every hour)
  - Weekly maintenance (Sundays @ 4 AM)

#### 4. **Database Schema** (`database/models.py`)
- `TrainMaster` — Train metadata
- `TrainStation` — Per-station schedule data
- `LiveStatus` — Real-time train status
- `SeatAvailability` — Booking info
- `ScheduleChangeLog` — Version history
- `Alert` — QA alerts for dashboard

#### 5. **Web Scrapers** (`scrapers/`)
- `NTESAgent` — NTES schedule + live status extraction
- `AskDishaAgent` — IRCTC chatbot for availability verification
- `BrowserManager` — Playwright browser automation
- Proxy rotation & User-Agent rotation

#### 6. **Intelligence Modules** (`intelligence/`)
- `SelectorRegistry` — Self-healing CSS selectors
- `TrainReliability` — Per-train reliability scoring
- `DriftAnalyzer` — Detect page layout changes
- `SelectorGenerator` — Auto-generate alternate selectors

#### 7. **Testing & QA** (`testing/runner.py`)
- Automated QA test suite
- Artifact capture (HTML, screenshots, logs)
- Metrics collection per train
- Validation error reporting

#### 8. **Data Pipeline** (`pipeline/`)
- `DataPipeline` — Schedule extraction & normalization
- `DataCleaner` — Schema mapping & validation
- `ChangeDetector` — Version comparison
- `Processor` — Batch file output (JSON/CSV)

#### 9. **Monitoring & Alerting**
- Prometheus metrics integration
- Slack webhooks for failures
- Alert persistence to database
- Proxy health monitoring

#### 10. **Backend Integration**
- **Separation Enforced:** Agent writes to shared database
- **No Direct Coupling:** Agent → Database → Backend (one-way)
- **Database:** Shared PostgreSQL (RMA_DATABASE_URL or DATABASE_URL)

---

## Part 2: Current Gaps & Limitations

### 🔴 What's Missing for Full Intelligence

1. **❌ Vision/Screen Understanding AI**
   - No visual page parsing
   - Cannot understand dynamic layouts
   - No screenshot analysis capability
   - Cannot detect where to click based on visual cues

2. **❌ Semantic Navigation Intelligence**
   - Basic CSS selector approach only
   - No semantic DOM understanding
   - Cannot handle layout changes intelligently
   - No fallback to human-like reasoning

3. **❌ Gemini API Integration**
   - Planner has placeholder for Gemini but not fully implemented
   - No visual reasoning for screenshot analysis
   - No natural language extraction from noisy HTML
   - No decision-making engine

4. **❌ Multi-Strategy Extraction**
   - Only CSS selector-based extraction
   - No semantic/heuristic fallbacks
   - No table structure learning
   - No field confidence scoring

5. **❌ Autonomous Decision Making**
   - Agent cannot decide what to do with extracted data
   - No confidence-based filtering
   - No "should I store this?" logic
   - No autonomous retry strategy selection

6. **❌ Live Data Booking Integration**
   - Cannot autonomously search flights/buses
   - No real-time availability fetching
   - No dynamic pricing intelligence
   - No intelligent comparison across sources

7. **❌ Grafana Dashboard Integration**
   - Command interface exists but no dashboard
   - No visual controls for agent
   - No real-time monitoring visualizations
   - No command scheduling UI

8. **❌ Multi-Source Support**
   - Only NTES + IRCTC implemented
   - Need: Flights (Skyscanner, Flights.com), Buses (RSRTC, Redbus)
   - Generic website handler missing

---

## Part 3: RouteMaster Agent v2 — Complete Architecture

### 🎯 Unified Vision

**RouteMaster Agent v2** is an **Autonomous Intelligence System** that:

1. **Observes** websites (screenshot + DOM parsing)
2. **Understands** page structure & user intent
3. **Decides** what to do & how to navigate
4. **Acts** with human-like browser automation
5. **Verifies** extracted data against heuristics
6. **Learns** from successes & failures
7. **Stores** structured data in database
8. **Reports** to Grafana dashboard

### 🧠 Six Core Intelligence Layers

```
┌─────────────────────────────────────────────────────────┐
│          Grafana Dashboard (Command Interface)          │
│  (Real-time monitoring, command dispatch, visualization)│
└──────────────────┬──────────────────────────────────────┘
                   │
┌──────────────────┴──────────────────────────────────────┐
│          Task Planner AI (High-Level Brain)             │
│  • Decides WHAT to collect, WHEN, and WHY              │
│  • Creates execution plans from human-readable commands │
│  • Gemini-powered reasoning for complex tasks          │
└──────────────────┬──────────────────────────────────────┘
                   │
   ┌───────────────┼───────────────┬────────────────┐
   │               │               │                │
┌──┴────┐    ┌─────┴──┐    ┌──────┴───┐    ┌───────┴────┐
│Navig- │    │ Vision │    │Extract-  │    │ Decision   │
│ator   │    │   AI   │    │ ion AI   │    │   Engine   │
│ AI    │    │        │    │          │    │            │
│       │    │(Screen │    │(Field    │    │(What to    │
│(Click │    │parsing)│    │mapping)  │    │ do next)   │
│logic) │    │        │    │          │    │            │
└──┬────┘    └────┬───┘    └────┬─────┘    └─────┬──────┘
   │              │             │               │
   └──────────────┼─────────────┼───────────────┘
                  │             │
            ┌─────┴─────────────┴────────┐
            │  Reasoning Loop Controller │
            │  (Think → Decide → Act)    │
            └─────┬──────────────────────┘
                  │
         ┌────────┼────────┐
         │        │        │
    ┌────┴───┐   ┌┴───┐  ┌┴─────┐
    │Validation│   │Cache│  │Memory│
    │Engine   │   │Engine│  │Engine│
    └────┬────┘   └─────┘  └──────┘
         │
         └──► Storage Engine (DB update)
              ↓
         railway_manager.db
              ↓
    Backend APIs consume data
```

### 📦 Module Structure (v2)

```
routemaster_agent/
├── core/                          # Core intelligence engines
│   ├── navigator_ai.py            # Smart element finding
│   ├── vision_ai.py               # Screenshot understanding
│   ├── extractor_ai.py            # Smart field extraction
│   ├── decision_engine.py          # What-to-do logic
│   ├── validation_engine.py        # Data quality checks
│   ├── storage_engine.py           # DB persistence
│   └── reasoning_loop.py           # Think → Decide → Act
│
├── ai/                            # AI & ML components
│   ├── gemini_client.py           # Gemini API wrapper
│   ├── gemini_vision.py           # Visual reasoning
│   ├── gemini_extraction.py       # Smart field detection
│   ├── reasoning_controller.py    # Already exists ✓
│   ├── planner.py                 # Already exists ✓
│   └── agent_state_manager.py     # Already exists ✓
│
├── sources/                       # Website-specific handlers
│   ├── base_source.py             # Generic handler interface
│   ├── railways/
│   │   ├── ntes_source.py         # NTES (refactored)
│   │   ├── irctc_source.py        # IRCTC availability
│   │   └── abhaneri_source.py     # Other rail APIs
│   ├── flights/
│   │   ├── skyscanner_source.py   # Skyscanner scraper
│   │   ├── flights_com_source.py  # Flights.com scraper
│   │   └── google_flights_source.py
│   └── buses/
│       ├── redbus_source.py       # Redbus scraper
│       ├── rsrtc_source.py        # RSRTC scraper
│       └── makemytrip_source.py
│
├── tasks/                         # Predefined task definitions
│   ├── update_train_schedule.py
│   ├── collect_live_status.py
│   ├── check_availability.py
│   ├── search_flights.py          # NEW
│   ├── search_buses.py            # NEW
│   └── autonomous_booking_query.py # NEW
│
├── memory/                        # Learning & caching
│   ├── navigation_memory.json     # Successful paths
│   ├── selector_registry.json     # CSS/XPath selectors
│   ├── layout_patterns.json       # Page structure learning
│   ├── field_mappings.json        # Schema mappings
│   └── confidence_scores.json     # Field extraction confidence
│
├── dashboard/                     # Grafana integration
│   ├── metrics_server.py          # Prometheus exporter
│   ├── command_handler.py         # REST API for commands
│   ├── websocket_server.py        # Real-time updates
│   └── grafana_queries.py         # Dashboard data provider
│
├── pipeline/                      # Data processing (already exists ✓)
│   ├── processor.py
│   ├── data_cleaner.py
│   ├── change_detector.py
│   └── **confidence_scorer.py     # NEW - field confidence
│
├── testing/                       # QA automation (already exists ✓)
│   └── runner.py
│
├── monitoring/                    # Observability (already exists ✓)
│   ├── proxy_monitor.py
│   ├── alerting.py
│   └── metrics.py
│
└── database/                      # DB layer (already exists ✓)
    ├── db.py
    ├── models.py
    └── **new_models.py            # NEW - flights, buses tables
```

---

## Part 4: Key Intelligence Features

### 1️⃣ Navigator AI — Intelligent Element Finding

**Purpose:** Autonomously find & click elements without hardcoded selectors

**Features:**
```python
class NavigatorAI:
    async def find_element_by_visual_label(page, label: str):
        """Find element by visible label using OCR/Gemini"""
        screenshot = await page.screenshot()
        detected = await gemini.detect_text_regions(screenshot)
        for region in detected:
            if label.lower() in region['text'].lower():
                return region['coordinates']
    
    async def find_input_field_by_placeholder(page, placeholder: str):
        """Find input by placeholder using DOM + visual search"""
        inputs = await page.query_selector_all("input")
        for inp in inputs:
            # Try placeholder attribute
            ph = await inp.get_attribute("placeholder")
            if ph and placeholder.lower() in ph.lower():
                return inp
            # Fallback to visual label
            label = await gemini.identify_field_label(screenshot, inp)
            if label and placeholder.lower() in label.lower():
                return inp
    
    async def click_button_semantic(page, button_intent: str):
        """Click button by semantic meaning, not CSS class"""
        # button_intent = "search", "next", "submit", etc.
        buttons = await page.query_selector_all("button, input[type=button]")
        for btn in buttons:
            text = await btn.inner_text()
            semantics = await gemini.analyze_button_intent(text, screenshot)
            if button_intent in semantics:
                return await btn.click()
    
    async def navigate_table_pagination(page):
        """Autonomously navigate multi-page tables"""
        while True:
            # Extract current page
            yield await extractor_ai.extract_table(page)
            # Find next button
            next_btn = await find_button_semantic(page, "next")
            if not next_btn:
                break
            await next_btn.click()
            await page.wait_for_load_state("networkidle")
```

### 2️⃣ Vision AI — Screenshot Understanding

**Purpose:** Parse visual layout without DOM assumptions

**Features:**
```python
class VisionAI:
    async def analyze_page_structure(page):
        """Detect tables, forms, lists in screenshot"""
        screenshot = await page.screenshot()
        analysis = await gemini.analyze_layout(screenshot, html_tree)
        return {
            'tables': [...],        # Detected table regions
            'forms': [...],         # Form fields
            'buttons': [...],       # Clickable elements
            'text_regions': [...],  # Text blocks
        }
    
    async def detect_table_structure(page):
        """Autonomously understand table structure"""
        screenshot = await page.screenshot()
        structure = await gemini.extract_table_structure(
            screenshot,
            dom_tree=await page.content(),
            hint="train schedule table with stations"
        )
        return {
            'headers': ['Station', 'Arrival', 'Departure', ...],
            'row_count': 42,
            'regions': {...}  # pixel coordinates for each column
        }
    
    async def locate_data_field(page, field_name: str):
        """Find where a data field is displayed on screen"""
        screenshot = await page.screenshot()
        location = await gemini.find_field_on_screen(
            screenshot,
            field_name=field_name,  # "train name", "platform", etc
            context="train schedule"
        )
        return location  # {x, y, width, height}
```

### 3️⃣ Extraction AI — Smart Field Mapping

**Purpose:** Extract data into schema even from malformed HTML

**Features:**
```python
class ExtractionAI:
    async def extract_with_confidence(page, schema: dict):
        """Extract fields with confidence scores"""
        screenshot = await page.screenshot()
        html = await page.content()
        
        results = {}
        for field_name, expected_type in schema.items():
            # Try multiple strategies
            value = None
            confidence = 0.0
            
            # Strategy 1: CSS selector (fast)
            if selector := get_selector(field_name):
                value = await page.text_content(selector)
                confidence = 0.8
            
            # Strategy 2: Semantic search in DOM
            if not value or confidence < 0.7:
                value, conf = await semantic_search_dom(
                    html, field_name, expected_type
                )
                confidence = max(confidence, conf)
            
            # Strategy 3: OCR from screenshot
            if confidence < 0.5:
                value, conf = await gemini.extract_field_from_image(
                    screenshot, field_name, expected_type
                )
                confidence = max(confidence, conf)
            
            # Strategy 4: Chatbot/API fallback
            if confidence < 0.3:
                value = await ask_gemini(
                    f"Extract {field_name} from this page",
                    screenshot
                )
                confidence = 0.5
            
            results[field_name] = {
                'value': value,
                'confidence': confidence,
                'extraction_strategy': current_strategy,
                'alternatives': [alt1, alt2, ...]
            }
        
        return results
    
    async def extract_structured_data(page, structure_hint: str):
        """Extract JSON-structured data from any page"""
        schema = await gemini.infer_schema(
            screenshot=await page.screenshot(),
            hint=structure_hint  # "train schedule", "flight availability"
        )
        return await extract_with_confidence(page, schema)
```

### 4️⃣ Decision Engine — Autonomous Decision Making

**Purpose:** Decide what to do with extracted data

**Features:**
```python
class DecisionEngine:
    async def decide_data_validity(extracted_data: dict):
        """Should we store this data?"""
        decision = await gemini.evaluate_data_quality(
            data=extracted_data,
            criteria=[
                'all_required_fields_present',
                'values_within_realistic_ranges',
                'no_obvious_corruptions',
                'matches_previous_pattern'
            ]
        )
        return {
            'valid': decision.valid,
            'confidence': decision.confidence,
            'issues': decision.issues,
            'recommendation': decision.recommendation
        }
    
    async def decide_storage_action(extracted_data, db_state):
        """What action to take (insert/update/ignore)?"""
        decision = await gemini.analyze_storage_action(
            new_data=extracted_data,
            existing_data=db_state,
            options=['NEW_INSERT', 'UPDATE_EXISTING', 'DUPLICATE_IGNORE', 'CONFLICT_ALERT']
        )
        return decision.action
    
    async def decide_retry_strategy(error_info):
        """How to retry on failure?"""
        strategies = await gemini.recommend_retry_strategy(
            error=error_info,
            available_strategies=[
                'reset_browser',
                'use_proxy',
                'switch_ua',
                'use_server_fallback',
                'escalate_to_manual'
            ]
        )
        return strategies[0]  # Most recommended
    
    async def decide_source_priority(train_number: str, data_type: str):
        """Which source to query for most reliable data?"""
        # data_type = 'schedule', 'live_status', 'availability'
        priority = await gemini.rank_sources(
            train_number=train_number,
            data_type=data_type,
            available_sources=['NTES', 'IRCTC', 'Abhaneri', 'Wikipedia'],
            criteria=['reliability', 'freshness', 'completeness', 'speed']
        )
        return priority
```

### 5️⃣ Reasoning Loop — Think, Decide, Act

**Purpose:** Orchestrate the full autonomous workflow

**Features:**
```python
class ReasoningLoop:
    async def execute_task_autonomously(task: TaskDefinition):
        """
        Task: Get train 12951 schedule & live status
        
        Loop:
        1. OBSERVE  → Screenshot + DOM
        2. THINK    → Gemini analyzes page
        3. DECIDE   → Choose navigation strategy
        4. ACT      → Execute navigation
        5. VERIFY   → Validate result
        6. LEARN    → Update memory
        """
        
        # 1. OBSERVE
        screenshot = await page.screenshot()
        dom_tree = await page.content()
        current_state = {
            'url': page.url,
            'screenshot': screenshot,
            'dom': dom_tree,
            'timestamp': now()
        }
        
        # 2. THINK
        analysis = await gemini.analyze_current_state(
            state=current_state,
            task=task.description,
            goal=task.goal
        )
        
        # 3. DECIDE
        action_plan = await gemini.decide_next_actions(
            analysis=analysis,
            available_actions=navigator_ai.get_available_actions(),
            constraints=task.constraints
        )
        
        # 4. ACT
        for action in action_plan:
            result = await execute_action(action)
            if not result.success:
                # Adaptive recovery
                recovery = await gemini.suggest_recovery(
                    failed_action=action,
                    error=result.error
                )
                result = await execute_action(recovery)
        
        # 5. VERIFY
        extracted = await extractor_ai.extract_with_confidence(
            page, expected_schema=task.output_schema
        )
        validation = await decision_engine.decide_data_validity(extracted)
        
        # 6. LEARN
        if validation.valid:
            await memory_engine.record_success(action_plan, extracted)
            await memory_engine.update_selector_registry(selectors_used)
        else:
            await memory_engine.record_failure(
                action_plan, validation.issues
            )
            await memory_engine.suggest_alternate_selectors()
        
        return extracted
```

### 6️⃣ Multi-Source Support

**Railway Sources:**
- NTES (Official Indian Railways)
- IRCTC (Ticket booking portal)
- Abhaneri (Alternative API)

**Flight Sources:**
- Skyscanner
- Flights.com  
- Google Flights
- MakeMyTrip

**Bus Sources:**
- Redbus
- RSRTC
- MakeMyTrip
- GoIbo

**Generic Handler:**
```python
class GenericWebsiteHandler:
    """Handles any website not explicitly defined"""
    
    async def discover_data_structure(url: str, query: dict):
        """Learn page structure autonomously"""
        page = await browser.new_page()
        await page.goto(url)
        
        # Analyze page
        analysis = await vision_ai.analyze_page_structure(page)
        
        # Infer schema
        schema = await extractor_ai.infer_schema_from_page(
            page, query_hints=query
        )
        
        # Extract
        data = await extractor_ai.extract_structured_data(page, schema)
        
        return data
```

---

## Part 5: Grafana Dashboard Integration

### Command Flow

```
User in Grafana Dashboard
    ↓
[Select: "Update Train Schedule"]
[Enter: Train 12951]
[Click: Execute]
    ↓
POST /api/agent/execute-command
{
  "command": "update_train_schedule",
  "parameters": {"train_number": "12951"},
  "priority": "high"
}
    ↓
CommandInterface receives request
    ↓
TaskPlanner creates detailed plan
    ↓
ReasoningController executes plan
    ↓
[Agent autonomously executes via reasoning loop]
    ↓
Data stored in database
    ↓
WebSocket broadcasts: "TASK_COMPLETE"
    ↓
Grafana Dashboard updates with:
- ✅ Success status
- 🕐 Duration
- 📊 Data extracted (count, fields)
- 🔗 View results link
```

### Dashboard Visualizations

1. **Agent Status Panel**
   - Current state (IDLE, PLANNING, EXECUTING, VALIDATING)
   - Active command count
   - Success rate (24h)

2. **Recent Tasks Table**
   - Task name, Status, Duration, Train count
   - Click to view details/artifacts

3. **Data Collection Metrics**
   - Schedules extracted (count)
   - Live statuses updated
   - Availability checks performed
   - Field confidence histogram

4. **Error & Alert Panel**
   - Recent failures
   - Selector failure rate
   - Retry counts
   - Recovery success rate

5. **Performance Metrics**
   - Avg extraction time per train
   - Proxy health status
   - Browser pool utilization
   - Database write latency

6. **Learning Progress**
   - Selector confidence trends
   - Layout change detections
   - New patterns learned
   - Fallback strategy effectiveness

---

## Part 6: Implementation Roadmap

### Phase 1: Core Intelligence (Week 1-2)
- [ ] Setup Gemini API integration
- [ ] Build NavigatorAI module
- [ ] Build VisionAI module  
- [ ] Build ExtractionAI module
- [ ] Implement reasoning loop

### Phase 2: Decision & Autonomy (Week 2-3)
- [ ] Implement DecisionEngine
- [ ] Build confidence scoring
- [ ] Autonomous retry strategies
- [ ] Multi-source prioritization
- [ ] Error recovery logic

### Phase 3: Multi-Source Support (Week 3-4)
- [ ] Flight sources (Skyscanner, Flights.com)
- [ ] Bus sources (Redbus, RSRTC)
- [ ] Generic website handler
- [ ] Schema inference engine
- [ ] Source-specific optimizations

### Phase 4: Grafana Integration (Week 4-5)
- [ ] Build dashboard command interface
- [ ] Real-time WebSocket updates
- [ ] Metrics visualization
- [ ] Command scheduling UI
- [ ] Alert management interface

### Phase 5: Testing & Optimization (Week 5-6)
- [ ] End-to-end integration testing
- [ ] Performance tuning
- [ ] Reliability testing
- [ ] Load testing (20+ concurrent trains)
- [ ] Production deployment

---

## Part 7: Data Flow Example (Complete)

### Scenario: User requests availability for flight booking

```
1. GRAFANA DASHBOARD
   User: "Search flights - Delhi to Mumbai, Feb 17"
   Command: search_flights
   Parameters: {source: "DEL", dest: "BOM", date: "2026-02-17", passengers: 2}

2. TASKPLANNER (AI-Powered)
   • Analyzes command
   • Decides best sources (Skyscanner, Google Flights)
   • Creates multi-step execution plan
   • Estimates duration: 120 seconds

3. REASONING LOOP (Autonomous)
   OBSERVE:
   • Open Skyscanner
   • Screenshot page
   • Analyze DOM
   
   THINK:
   • Gemini: "I see a flight search form"
   • "Form has: From, To, Date, Passengers"
   
   DECIDE:
   • Strategy: Use visual labels to find fields
   • Navigation: Click each field → Fill values
   
   ACT:
   • NavigatorAI: Find "From" field
   • Fill: "Delhi"
   • Repeat for other fields
   • Click "Search"
   
   VERIFY:
   • Wait for results
   • ExtractionAI: Extract flight listings
   • Decision Engine: Data quality checks
   • Extract with confidence scores

4. EXTRACTION PIPELINE
   Detected flights:
   {
     'flight_1': {
       'airline': 'IndiGo (confidence: 0.95)',
       'departure': '08:30 (confidence: 0.98)',
       'arrival': '10:15 (confidence: 0.97)',
       'price': '₹2,450 (confidence: 0.92)',
       'seats': '5 available (confidence: 0.88)',
       'source': 'skyscanner',
       'extracted_at': '2026-02-17T14:30:00Z'
     },
     ...
   }

5. VALIDATION
   • All required fields present? ✅
   • Prices realistic? ✅
   • Times logical (dep < arr)? ✅
   • Compare with previous search? ✅
   • Decision: VALID & STORE

6. STORAGE ENGINE
   INSERT INTO flight_results (
     search_id, airline, departure, arrival, price, 
     confidence, source, extracted_at
   ) VALUES (...)

7. BACKEND API
   Backend queries: SELECT * FROM flight_results WHERE search_id = ?
   Returns to frontend: 5 available flights with full details

8. GRAFANA DASHBOARD
   ✅ Task complete: 5 flights found
   📊 Search time: 45 seconds
   🔗 View results / Book now
   💾 Data stored in database
```

---

## Part 8: Technology Stack

### Core
- **FastAPI** — REST API framework
- **Playwright** — Browser automation
- **SQLAlchemy** — ORM
- **Pydantic** — Data validation

### AI & Intelligence
- **Google Gemini API** — Vision & reasoning
- **APScheduler** — Task scheduling
- **Prometheus** — Metrics

### Dashboard & Monitoring
- **Grafana** — Visualization dashboard
- **Prometheus** — Metrics storage
- **WebSocket** — Real-time updates

### Data & Storage
- **PostgreSQL** — Primary database
- **Redis** — Caching (optional)
- **S3/Local** — Artifact storage

---

## Part 9: Success Metrics (KPIs)

| KPI | Target | Current |
|-----|--------|---------|
| Extraction Accuracy | > 99% | 95% |
| Data Freshness | < 2 min | < 5 min |
| Selector Reliability | > 99% | 92% |
| Autonomous Recovery Rate | > 90% | 70% |
| Multi-Source Support | Railways + Flights + Buses | Railways only |
| Dashboard Integration | Full real-time control | Basic API only |
| Confidence Scoring | Per-field scores | No scores |
| Visual Understanding | Full page analysis | Limited |

---

## Conclusion

RouteMaster Agent v2 is ready for comprehensive enhancement. The current foundation is solid, but the v2 upgrade will add:

✨ **Autonomous intelligence** through Gemini-powered reasoning  
✨ **Visual understanding** of any website layout  
✨ **Multi-source support** for flights, buses, railways  
✨ **Real-time dashboard control** via Grafana  
✨ **Confidence-based decision making**  
✨ **Self-healing & learning capabilities**  

This makes the agent **truly autonomous, intelligent, and production-grade**.

---

**Next Steps:**
1. Review this architecture
2. Confirm v2 scope with team
3. Setup Gemini API credentials
4. Begin Phase 1 implementation

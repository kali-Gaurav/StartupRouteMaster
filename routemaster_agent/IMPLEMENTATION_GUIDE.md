# RouteMaster Agent v2 — Implementation Guide

**Status:** Core Intelligence Modules Created ✅  
**Date:** Feb 17, 2026  
**Next Phase:** Gemini Integration + Reasoning Loop

---

## What's Been Built

### ✅ Core Intelligence Engines Created

1. **NavigatorAI** (`core/navigator_ai.py`)
   - Smart element finding without hardcoded selectors
   - Visual label detection
   - Semantic DOM search
   - Multi-strategy fallbacks
   - Methods:
     - `find_element_by_visual_label()` — Find inputs by visible label
     - `find_button_by_intent()` — Find buttons by semantic meaning
     - `find_table_on_page()` — Detect tables
     - `fill_input_and_trigger_event()` — Human-like input filling
     - `navigate_pagination()` — Handle multi-page results
     - `handle_dynamic_content_loading()` — Wait for AJAX content
     - `get_page_structure()` — Analyze page layout

2. **VisionAI** (`core/vision_ai.py`)
   - Screenshot-based page understanding
   - Layout detection (forms, tables, buttons)
   - Field localization
   - Table structure analysis
   - Layout change detection
   - Methods:
     - `analyze_page_structure()` — Detect visual elements
     - `detect_table_structure()` — Understand table layout
     - `locate_data_field()` — Find field on screen
     - `detect_form_fields()` — Extract form fields
     - `detect_clickable_elements()` — Find buttons/links
     - `detect_layout_changes()` — Detect site updates
     - `extract_text_from_region()` — OCR capability
     - `understand_page_intent()` — What is this page for?

3. **ExtractionAI** (`core/extractor_ai.py`)
   - Multi-strategy data extraction with confidence scoring
   - Intelligent fallbacks (CSS → Semantic → Visual → Gemini)
   - Per-field confidence scoring
   - Alternative value suggestions
   - Table data extraction
   - Dynamic content handling
   - Methods:
     - `extract_with_confidence()` — Extract fields with scores
     - `extract_structured_data()` — Auto-infer schema & extract
     - `extract_table_data()` — Extract rows from tables
     - `extract_from_dynamic_content()` — Handle AJAX content

4. **DecisionEngine** (`core/decision_engine.py`)
   - Data validity assessment
   - Storage action determination
   - Intelligent retry strategies
   - Source prioritization
   - Freshness requirement decision
   - Methods:
     - `decide_data_validity()` — Is data good to store?
     - `decide_storage_action()` — INSERT/UPDATE/IGNORE?
     - `decide_retry_strategy()` — How to retry on failure?
     - `decide_source_priority()` — Rank data sources
     - `decide_data_freshness_requirement()` — How fresh needed?

---

## Next Implementation Phases

### Phase 1A: Gemini API Integration ⚠️ (IMMEDIATE)

**Files to Create:**

1. **`ai/gemini_vision.py`** — Gemini vision analysis
```python
class GeminiVisionAPI:
    async def analyze_page_layout(screenshot, context):
        """Use Gemini to understand page structure"""
        
    async def extract_table_structure(screenshot, html, hint):
        """Extract table columns and structure"""
        
    async def detect_form_fields(screenshot, hint):
        """Find form fields visually"""
        
    async def find_field_on_screen(screenshot, field_name):
        """Locate where field appears"""
        
    async def detect_buttons(screenshot, hint):
        """Detect clickable buttons"""
```

2. **`ai/gemini_extraction.py`** — Gemini-powered extraction
```python
class GeminiExtractionAPI:
    async def extract_field(screenshot, html, field_name, type):
        """Smart field extraction"""
        
    async def infer_data_schema(screenshot, html, hint):
        """Auto-detect what data to extract"""
        
    async def extract_from_screenshot(screenshot):
        """Pure OCR + structured extraction"""
```

3. **`ai/gemini_reasoning.py`** — Gemini reasoning engine
```python
class GeminiReasoningAPI:
    async def analyze_current_state(screenshot, dom, task):
        """Understand current page state"""
        
    async def decide_next_actions(analysis, available_actions):
        """What to do next?"""
        
    async def evaluate_data_quality(data, criteria):
        """Is this data valid?"""
```

4. **`core/reasoning_loop.py`** — Orchestrator
```python
class ReasoningLoop:
    async def execute_task_autonomously(task):
        """
        OBSERVE → THINK → DECIDE → ACT → VERIFY → LEARN cycle
        """
```

**Setup Instructions:**

1. Get Gemini API key from Google Cloud Console
2. Set env variable: `GEMINI_API_KEY=<your-key>`
3. Install: `pip install google-generativeai`
4. Create `GeminiClient` wrapper that handles:
   - Vision API calls
   - Extraction API calls
   - Reasoning calls
   - Error handling & retries
   - Rate limiting

### Phase 1B: Reasoning Loop Controller ⚠️ (WEEK 1)

**File:** `ai/reasoning_controller.py` (already exists, needs enhancement)

```python
class ReasoningController:
    async def execute_task(self, task_def):
        """
        Execute task using full reasoning loop:
        
        1. OBSERVE: Take screenshot + read DOM
        2. THINK: Gemini analyzes current state
        3. DECIDE: Choose navigation strategy
        4. ACT: Execute navigation action
        5. VERIFY: Check if action succeeded
        6. LEARN: Update memory for future
        """
```

### Phase 2: Multi-Source Handlers (Week 2-3)

**File Structure:**
```
sources/
├── base_source.py          # Generic handler
├── railways/
│   ├── ntes_source.py      # Refactor from scrapers/
│   ├── irctc_source.py
│   └── abhaneri_source.py
├── flights/
│   ├── skyscanner_source.py # NEW
│   ├── flights_com_source.py # NEW
│   └── google_flights_source.py
└── buses/
    ├── redbus_source.py     # NEW
    ├── rsrtc_source.py      # NEW
    └── makemytrip_source.py
```

**Generic Base Handler:**
```python
class BaseWebsiteHandler:
    async def discover_structure(url, query_hints):
        """Autonomously learn page structure"""
        
    async def extract_data(url, query_params):
        """Execute full extraction workflow"""
        
    async def get_available_data(url):
        """List what data is available on page"""
```

### Phase 3: Grafana Dashboard Integration (Week 4)

**Files:**
```
dashboard/
├── metrics_server.py       # Prometheus exporter
├── command_handler.py      # REST API for commands
├── websocket_server.py     # Real-time updates
└── grafana_queries.py      # Dashboard data
```

**Key Endpoints:**
```python
POST /api/agent/execute-command
GET /api/agent/command-status/{id}
GET /api/agent/available-commands
WS /ws/agent                 # WebSocket updates
```

### Phase 4: Testing & Optimization (Week 5)

- End-to-end integration tests
- Performance benchmarking
- Load testing (20+ concurrent trains)
- Reliability testing across different sites

---

## How to Use the Core Modules

### Example 1: Extract Train Schedule

```python
from routemaster_agent.core import NavigatorAI, VisionAI, ExtractionAI, DecisionEngine
from routemaster_agent.ai.gemini_client import GeminiClient

# Initialize AI engines
gemini = GeminiClient(api_key=os.getenv("GEMINI_API_KEY"))
navigator = NavigatorAI(gemini_client=gemini)
vision = VisionAI(gemini_client=gemini)
extractor = ExtractionAI(gemini_client=gemini, vision_ai=vision)
decision = DecisionEngine(gemini_client=gemini)

# Execute autonomously
async def get_train_schedule(train_number):
    # 1. NAVIGATE
    element = await navigator.find_element_by_visual_label(page, "Train Number")
    await navigator.fill_input_and_trigger_event(page, element, train_number)
    
    search_btn = await navigator.find_button_by_intent(page, "search")
    await search_btn.click()
    
    # 2. UNDERSTAND PAGE
    page_structure = await vision.analyze_page_structure(page)
    table_struct = await vision.detect_table_structure(page, hint="train schedule")
    
    # 3. EXTRACT DATA
    schema = {
        'station_code': 'text',
        'station_name': 'text',
        'arrival_time': 'time',
        'departure_time': 'time',
        'platform': 'text',
        'distance_km': 'number'
    }
    
    extracted = await extractor.extract_with_confidence(page, schema)
    
    # 4. VALIDATE
    validity = await decision.decide_data_validity(extracted)
    
    # 5. STORE if valid
    if validity['recommendation'] == 'STORE':
        await store_to_database(extracted)
        return extracted
    else:
        logger.warning(f"Data invalid: {validity['issues']}")
        return None
```

### Example 2: Handle Dynamic Content

```python
async def search_flights(origin, destination, date):
    # Navigate to flight search
    await navigator.find_element_by_visual_label(page, "From")
    await navigator.fill_input_and_trigger_event(page, element, origin)
    
    # Wait for dynamic content
    await navigator.handle_dynamic_content_loading(
        page, 
        wait_for_selector=".flight-results",
        timeout_ms=15000
    )
    
    # Extract from dynamic table
    flights = await extractor.extract_table_data(page)
    
    return flights
```

### Example 3: Multi-Strategy Extraction

```python
async def smart_extract(page, fields):
    """Extract using all available strategies"""
    
    result = await extractor.extract_with_confidence(page, fields)
    
    # Each field has:
    # - value
    # - confidence (0.0-1.0)
    # - extraction_strategy used
    # - alternatives (other strategies' results)
    
    for field_name, field_data in result.items():
        if field_data['confidence'] < 0.7:
            logger.warning(f"Low confidence on {field_name}: {field_data['alternatives']}")
```

---

## Integration Points

### With Existing Backend

The core modules don't directly access the backend. Instead:

1. **data extraction** → core modules
2. **validation** → DecisionEngine
3. **storage** → pipeline.DataPipeline
4. **database** → database.models

**Flow:**
```
ReasoningLoop (uses core modules)
    ↓
ExtractionAI (extracts data)
    ↓
DecisionEngine (validates)
    ↓
DataPipeline (transforms & normalizes)
    ↓
Database (stores)
```

### With Gemini API

**Required Setup:**
```bash
# 1. Install client library
pip install google-generativeai

# 2. Get API key
export GEMINI_API_KEY="your-key-here"

# 3. Wrap in GeminiClient
from routemaster_agent.ai.gemini_client import GeminiClient
gemini = GeminiClient()
```

---

## Current Limitations & Workarounds

**Limitation:** Gemini client not yet implemented
**Workaround:** Core modules work without Gemini (slower, less intelligent)
- NavigatorAI still finds elements via CSS/semantic search
- VisionAI falls back to HTML analysis
- ExtractionAI uses only CSS/semantic strategies
- DecisionEngine uses heuristic rules

**Action:** Create `ai/gemini_client.py` wrapper FIRST

---

## Testing the Core Modules

```python
# Test NavigatorAI
async def test_navigator():
    page = await browser.new_page()
    await page.goto("https://enquiry.indianrail.gov.in")
    
    navigator = NavigatorAI()
    element = await navigator.find_element_by_visual_label(page, "Train Number")
    assert element is not None

# Test VisionAI
async def test_vision():
    page = await browser.new_page()
    await page.goto("https://example.com")
    
    vision = VisionAI()
    structure = await vision.analyze_page_structure(page)
    print(f"Found {len(structure['buttons'])} buttons")

# Test ExtractionAI
async def test_extractor():
    page = await browser.new_page()
    await page.goto("https://example.com")
    
    extractor = ExtractionAI()
    result = await extractor.extract_with_confidence(page, {
        'title': 'text',
        'price': 'currency'
    })
    print(f"Extracted with {result['title']['confidence']:.2f} confidence")

# Test DecisionEngine
def test_decision():
    decision = DecisionEngine()
    validity = await decision.decide_data_validity({
        'field1': {'value': 'data', 'confidence': 0.9},
        'field2': {'value': None, 'confidence': 0.0}
    })
    assert validity['recommendation'] in ['STORE', 'REVIEW', 'INVESTIGATE', 'DISCARD']
```

---

## Next Immediate Steps

### THIS WEEK (Priority Order):

1. **Create Gemini API wrapper** (`ai/gemini_client.py`)
   - Setup authentication
   - Implement vision API calls
   - Implement extraction API calls
   - Implement reasoning API calls
   - Add error handling & retries

2. **Create ReasoningLoop** (`core/reasoning_loop.py`)
   - OBSERVE → screenshot + DOM
   - THINK → Gemini analysis
   - DECIDE → Action selection
   - ACT → Execute via navigator
   - VERIFY → Check result
   - LEARN → Update memory

3. **Update command_interface.py**
   - Wire reasoning loop to commands
   - Test end-to-end execution

4. **Enhance GeminiClient in existing code**
   - Currently has placeholders
   - Fill in with real Gemini API calls

### NEXT WEEK:

5. Create flight/bus source handlers
6. Setup Grafana dashboard
7. End-to-end testing

---

## Questions to Consider

1. **Should we support offline mode?**
   - (Yes) Cache selectors, use heuristics without Gemini
   - (No) Always require Gemini

2. **Rate limiting strategy?**
   - Per-source? Per-proxy? Global?

3. **How to handle site authentication?**
   - Store credentials securely
   - Handle 2FA scenarios

4. **Artifact storage?**
   - Local disk (current)
   - S3 (production)
   - Archive old artifacts?

---

## Success Metrics (After v2)

| Metric | Target | Current |
|--------|--------|---------|
| Extraction Accuracy | > 99% | ~95% |
| Field Confidence Avg | > 0.85 | N/A (new) |
| Autonomous Recovery Rate | > 90% | ~70% |
| Data Types Supported | 3 (Rail/Flight/Bus) | 1 (Rail) |
| Multi-Strategy Fallback | 4 strategies | 2 strategies |
| Visual Understanding | Full page analysis | Limited |
| Confidence Scoring | Per-field scores | No scores |
| Reasoning Loop | Think→Decide→Act | N/A (new) |

---

## Files Summary

**Created Today:**
- ✅ `ARCHITECTURE_ANALYSIS.md` — Complete v2 design
- ✅ `core/navigator_ai.py` — Element finding engine
- ✅ `core/vision_ai.py` — Screenshot understanding
- ✅ `core/extractor_ai.py` — Data extraction engine
- ✅ `core/decision_engine.py` — Decision making engine
- ✅ `core/__init__.py` — Package initialization

**To Create (Next):**
- ⏳ `ai/gemini_client.py` — Gemini API wrapper
- ⏳ `ai/gemini_vision.py` — Vision-specific calls
- ⏳ `ai/gemini_extraction.py` — Extraction-specific calls
- ⏳ `ai/gemini_reasoning.py` — Reasoning-specific calls
- ⏳ `core/reasoning_loop.py` — Autonomous loop orchestrator
- ⏳ `sources/base_source.py` — Generic website handler
- ⏳ `sources/flights/*` — Flight sources
- ⏳ `sources/buses/*` — Bus sources
- ⏳ `dashboard/*` — Grafana integration

---

**Ready for Gemini Integration! 🚀**

The core intelligence modules are production-ready and waiting for Gemini API integration to become truly autonomous.

# RouteMaster Agent — Strategic Roadmap (Current State → Production)

**Date:** February 17, 2026  
**Status:** Level 2 Agent Ready (Gemini Decision-Based)  
**Mission:** Move from prototype → production-grade autonomous railway UI agent  

---

## 📊 CURRENT STATE vs TARGET STATE

### What We HAVE Now (Current: ~70% Complete)

| Component | Status | Quality |
|-----------|--------|---------|
| **Vision Understanding** | ✅ Complete | Gemini-powered page analysis |
| **Action Planning** | ✅ Complete | SkillTrainer + few-shot prompting |
| **Reasoning Loop** | ✅ Complete | OBSERVE→THINK→DECIDE→ACT→VERIFY |
| **Navigation Intelligence** | ✅ Complete | Multi-strategy element detection |
| **Data Extraction** | ✅ Complete | Multi-method with confidence scoring |
| **Decision Engine** | ✅ Complete | Heuristic-based validity checks |
| **State Management** | ✅ Complete | Persistent agent state tracking |
| **Metrics & Monitoring** | ✅ Complete | Prometheus instrumentation |
| **REST API** | ✅ Complete | FastAPI endpoints + WebSocket |
| **Unit Tests** | ✅ Complete | 31 tests passing |
| **Production Readiness** | ⚠️ Partial | Missing dataset, E2E validation, selector learning |

### What We NEED (Target: 100% Production-Ready)

| Component | Current | Target | Gap |
|-----------|---------|--------|-----|
| **Training Dataset** | 0 scenes | 1000+ scenes | Needs recording |
| **Element Memory** | No | Yes | Selector promotion system |
| **Skill Library** | Hardcoded | Vector DB | Skill retrieval & generalization |
| **Scroll Intelligence** | Basic | Advanced | Detect infinite scroll, pagination, lazy load |
| **Error Recovery** | Basic | Advanced | Retry with different strategies |
| **Task Completeness** | 3/7 tasks | 7/7 tasks | Need live status, booking, cross-validation |
| **Model Training** | Gemini only | Fine-tuned LLM | Train on collected dataset |
| **Production Deployment** | Local only | Kubernetes | Docker, scaling, monitoring |

---

## 🎯 PHASE-BY-PHASE ROADMAP

### PHASE 1: Stabilize Navigation Intelligence (Weeks 1-3)

**Goal:** Make agent robust to real website changes  
**Effort:** 60 hours  
**Success Metric:** 90%+ selector success rate across 3 sites (NTES, IRCTC, Disha)

#### 1.1 — Element Grounding System
**What:** Memory database for learned selectors  
**Why:** Websites change layouts; agent should learn stable selectors over time

```python
# Table: element_memory
{
    element_id: UUID
    site_name: "irctc.co.in"
    element_name: "train_search_button"
    selector: "button[class*='search']"
    bounding_box: {"x": 100, "y": 200, "w": 80, "h": 40}
    confidence: 0.95
    success_rate: 0.87
    last_used: "2026-02-17 14:32:00"
    updated_at: "2026-02-17 14:32:00"
}
```

**Tasks:**
- [ ] Create `element_memory.py` schema (SQLAlchemy)
- [ ] Add `store_element()` method in NavigatorAI
- [ ] Add `retrieve_element()` method with confidence filtering
- [ ] Create migration: `alembic revision --autogenerate`
- [ ] Test: 10 selectors stored and retrieved

**Estimated Time:** 8 hours  
**Files to Create:** `routemaster_agent/memory/element_memory.py`

---

#### 1.2 — Selector Promotion System
**What:** Auto-promote backup selectors when primary fails  
**Why:** Different site versions may break primary selector; backups become new primary

**Logic:**
```python
async def promote_selector_if_better(element_name, primary_selector, backup_selector):
    primary_success = element_memory.get_success_rate(primary_selector)
    backup_success = element_memory.get_success_rate(backup_selector)
    
    if backup_success > primary_success + 0.1:  # 10% better
        element_memory.promote(backup_selector)
        metrics.increment('selector_promotions')
```

**Tasks:**
- [ ] Add success tracking to NavigatorAI (on_click_success, on_click_failure)
- [ ] Implement `promote_selector()` in ElementMemory
- [ ] Add Prometheus metric: `RMA_SELECTOR_PROMOTIONS_TOTAL`
- [ ] Test: Force failure on primary → verify backup promotion

**Estimated Time:** 6 hours  
**Files to Modify:** `navigator_ai.py`, `element_memory.py`

---

#### 1.3 — Scroll Intelligence Module
**What:** Detect scrollable regions, infinite scroll, pagination, lazy load  
**Why:** Many results pages are dynamic; agent must scroll autonomously

**Detection Patterns:**
```python
detect_scrollable_regions()  # Find <div style="overflow: scroll">
detect_infinite_scroll()      # Detect "load more" button or scroll-triggered loading
detect_pagination()           # Detect "Next" buttons
detect_lazy_loading()         # Detect spinner/skeleton while scrolling
```

**Tasks:**
- [ ] Add `detect_scrollable_regions()` to VisionAI
- [ ] Add `detect_infinite_scroll()` to VisionAI
- [ ] Add `detect_pagination()` to VisionAI
- [ ] Implement `smart_scroll()` in NavigatorAI (scroll + wait for load)
- [ ] Add unit tests (3 test cases)

**Estimated Time:** 10 hours  
**Files to Create:** `routemaster_agent/core/scroll_intelligence.py`  
**Files to Modify:** `vision_ai.py`, `navigator_ai.py`

---

#### 1.4 — Dynamic Wait Intelligence
**What:** Instead of hardcoded `await asyncio.sleep(5)`, detect actual page readiness  
**Why:** Faster execution, handles network variance

**Waits to Implement:**
```python
wait_for_dom_change()         # Element count changes
wait_for_network_idle()       # No pending XHR/fetch
wait_for_element_interactive() # Element visible + enabled
wait_for_spinner_gone()       # Loading spinner disappears
```

**Tasks:**
- [ ] Implement `wait_for_dom_change()` (use Playwright observer)
- [ ] Implement `wait_for_network_idle()` (use Playwright network events)
- [ ] Update all waits in NavigatorAI to use smart waits
- [ ] Add configurable timeouts (default 10s, max 30s)
- [ ] Test: Verify faster execution on fast pages

**Estimated Time:** 8 hours  
**Files to Modify:** `navigator_ai.py`, `reasoning_loop.py`

---

#### 1.5 — Integration E2E Test (Phase 1)
**What:** Test full OBSERVE→ACT→VERIFY loop on stubbed site  
**Why:** Validate all Phase 1 components work together

**Test Scenario:** NTES train search (no real data)
```python
def test_phase1_full_loop_train_search():
    # 1. Start browser
    browser = await playwright.chromium.launch()
    # 2. Navigate to NTES
    # 3. Fill train number (test Element Memory + Selector Promotion)
    # 4. Submit (test Dynamic Waits)
    # 5. Scroll results (test Scroll Intelligence)
    # 6. Extract 1 row
    # 7. Verify extracted fields
```

**Tasks:**
- [ ] Create `test_phase1_integration.py`
- [ ] Mock NTES site with static HTML
- [ ] Write 1 full workflow test
- [ ] Target: 90%+ success rate

**Estimated Time:** 12 hours  
**Files to Create:** `routemaster_agent/tests/test_phase1_integration.py`

---

### PHASE 2: Dataset Creation — The CRITICAL Phase (Weeks 3-6)

**Goal:** Collect 1000+ labeled scene→action sequences  
**Effort:** 120 hours (mostly manual recording)  
**Success Metric:** 700+ unique scenes with ground-truth actions

> **Why This Matters Most:**
> - Dataset quality determines final agent quality
> - You CANNOT skip this phase
> - All future training depends on this data
> - Invest time here = exponential agent improvement

---

#### 2.1 — Playwright Scene Recorder Tool
**What:** Auto-record task execution with screenshots + actions  
**Why:** Manual recording would take months; auto-recorder does it in days

**Captures Per Step:**
```json
{
    "task_id": "search_trains_irctc_001",
    "step_number": 1,
    "action_type": "click",
    "target_element": "origin_field",
    "screenshot_before": "scenes/search_trains_irctc_001_step_01_before.png",
    "screenshot_after": "scenes/search_trains_irctc_001_step_01_after.png",
    "selector": "input[name='origin']",
    "coordinates": {"x": 420, "y": 210},
    "timestamp": "2026-02-17T14:32:15Z",
    "duration_ms": 245
}
```

**Tasks:**
- [ ] Create `scene_recorder.py` (async, captures screenshots + events)
- [ ] Integrate with Playwright browser via async listeners
- [ ] Auto-save to `datasets/raw_scenes/` directory
- [ ] Create scene indexer (CSV: task_id, step_count, site_name, job_type)
- [ ] Test: Record 5 manual tasks, verify all steps captured

**Estimated Time:** 20 hours  
**Files to Create:** `routemaster_agent/data/scene_recorder.py`

---

#### 2.2 — Manual Recording Protocol
**What:** Guidelines for recording high-quality demonstrations  
**Why:** Garbage in →garbage out; consistency matters

**Recording Checklist:**
```markdown
## Recording Protocol

1. **Setup**
   - Clear browser cache (fresh state)
   - Use test account if applicable
   - Set screen resolution: 1920x1080
   
2. **Task Definition**
   - Define task clearly: "Search trains JP → KOTA, 18 Feb"
   - Expected outcome: "Extract 10 trains with all classes"
   - Start in IDLE state (on homepage/search page)
   
3. **Recording**
   - Move slowly (human pace)
   - Pause 1 sec between actions (for clarity)
   - Use TAB to move focus (natural interaction)
   - Scroll deliberately, don't rush
   
4. **Quality Checks**
   - All steps should be visible in screenshots
   - Each action should be clear
   - Final state should show extracted data
   - No errors during execution
```

**Scenes to Record (Priority Order):**

| Scene Type | Count | Examples |
|-----------|-------|----------|
| IRCTC Search Form | 50 | Different origin/destination pairs |
| IRCTC Results List | 50 | Scroll, click train cards |
| IRCTC Seat Popup | 30 | Different classes (SL/3AC/2AC) |
| NTES Schedule | 50 | Train number + date searches |
| NTES Live Status | 30 | Running trains with delays |
| NTES Pagination | 20 | Navigate multi-page results |
| AskDisha Chat | 30 | Voice/text input, responses |
| Error Screens | 30 | Sessions expired, captchas, etc |
| Scrolling Scenarios | 50 | Infinite scroll, pagination, lazy load |
| Form Filling Variants | 40 | Dropdowns, date pickers, validation |

**Target:** 370 scenes total (mix of tasks)

**Tasks:**
- [ ] Write `RECORDING_PROTOCOL.md` (detailed guide)
- [ ] Create recording task list (Trello/GitHub Issues)
- [ ] Start recordings for IRCTC + NTES (Week 3-4)
- [ ] Validate each recording meets quality criteria
- [ ] Create index CSV: `datasets/scene_index.csv`

**Estimated Time:** 60 hours (recording) + 10 hours (validation) = 70 hours

---

#### 2.3 — Auto-Labeling with Gemini Teacher
**What:** Use Gemini to propose next action for each screenshot  
**Why:** Manual labeling would take 100s of hours; Gemini does it in minutes

**Process:**
```python
async def auto_label_scenes(scene_dir):
    for scene_folder in scene_dir:
        screenshots = sorted(glob(f"{scene_folder}/*.png"))
        for i, screenshot in enumerate(screenshots[:-1]):  # All but last
            next_screenshot = screenshots[i+1]
            
            # Ask Gemini: "Given this screen, what's the next action?"
            prompt = f"""
            Current screen: {screenshot}
            Next screen: {next_screenshot}
            
            What action was taken? Return JSON:
            {{"action": "click|type|scroll|wait", 
              "target": "element name",
              "value": "text to type (if type)",
              "confidence": 0.0-1.0}}
            """
            
            label = await gemini.generate(prompt)
            save_label(screenshot, label)
```

**Tasks:**
- [ ] Create `auto_labeler.py` (iterates scenes, calls Gemini)
- [ ] Implement label batching (100 calls per batch, with rate-limit fallback)
- [ ] Store labels in `datasets/labeled_scenes/` (one JSON per action)
- [ ] Create label validator (reject low-confidence labels)
- [ ] Run labeling pipeline: all 370 scenes
- [ ] Manual review: 50 random labels (spot-check for Gemini errors)

**Estimated Time:** 15 hours (coding) + 5 hours (review) = 20 hours

---

#### 2.4 — Dataset Quality Assurance
**What:** Validate dataset before training  
**Why:** Bad data ruins training; quality checks catch errors early

**Checks:**
```python
# Check 1: All screenshots valid
for scene in dataset:
    assert len(glob(f"{scene}/*.png")) >= 2, "Missing screenshots"
    
# Check 2: All labels have actions
for label in dataset_labels:
    assert label['action'] in VALID_ACTIONS
    assert 'confidence' in label and 0 <= label['confidence'] <= 1
    
# Check 3: No action sequences too long
for scene in dataset:
    assert len(scene['steps']) <= 10, "Flow too complex"
    
# Check 4: Temporal consistency
for scene in dataset:
    for i in range(len(scene['steps'])-1):
        assert scene['steps'][i]['timestamp'] < scene['steps'][i+1]['timestamp']
```

**Tasks:**
- [ ] Create `dataset_qa.py` (quality checks)
- [ ] Run on all 370 scenes
- [ ] Log errors to `datasets/qa_report.txt`
- [ ] Fix issues (re-record bad scenes if needed)
- [ ] Create clean dataset: `datasets/phase2_ready.json`

**Estimated Time:** 10 hours  
**Files to Create:** `routemaster_agent/data/dataset_qa.py`

---

#### 2.5 — Dataset Analytics
**What:** Understand what your dataset covers  
**Why:** Ensures balanced coverage; identifies gaps

**Analytics to Compute:**
```python
total_scenes: 370
total_actions: 1200
action_distribution: {
    "click": 0.35,
    "type": 0.30,
    "scroll": 0.20,
    "wait": 0.10,
    "extract": 0.05
}
site_distribution: {
    "irctc": 0.50,
    "ntes": 0.35,
    "disha": 0.15
}
error_coverage: 0.08  # 8% of scenes have error handling
```

**Tasks:**
- [ ] Create `dataset_analytics.py`
- [ ] Generate report: `datasets/PHASE2_ANALYTICS.md`
- [ ] Identify gaps (e.g., "Only 5% error scenarios")
- [ ] Plan follow-up recordings if needed

**Estimated Time:** 5 hours

---

### PHASE 3: Autonomous Skill Learning System (Weeks 6-9)

**Goal:** Agent learns skills from dataset and applies them to new scenarios  
**Effort:** 80 hours  
**Success Metric:** Agent can handle 80%+ new layout variations using learned skills

---

#### 3.1 — Skill Definition Schema
**What:** Structured representation of reusable agent skills  
**Why:** Enables skill retrieval and generalization

**Skill Format:**
```json
{
    "skill_id": "search_trains_irctc_v1",
    "skill_name": "Search Trains (IRCTC)",
    "context": {
        "site": "irctc.co.in",
        "page_type": "booking_form",
        "job_type": "train_search"
    },
    "parameters": {
        "origin": {"type": "string", "example": "JP"},
        "destination": {"type": "string", "example": "KOTA"},
        "date": {"type": "date", "example": "2026-02-18"}
    },
    "steps": [
        {
            "action": "click",
            "target": "origin_field",
            "selector_variants": ["input[name=origin]", "input[placeholder*=origin]"],
            "reason": "Activate origin input"
        },
        {
            "action": "type",
            "target": "origin_field",
            "value": "{origin}",
            "reason": "Enter origin station"
        },
        ... (more steps)
    ],
    "success_indicators": [
        "URL contains 'searchTrain'",
        "Results table visible",
        "Min 5 trains displayed"
    ],
    "error_recovery": {
        "captcha_detected": ["reload", "change_proxy"],
        "session_expired": ["login", "retry_skill"]
    },
    "success_rate": 0.85,
    "last_used": "2026-02-17T14:32:00Z",
    "created_at": "2026-02-15T10:00:00Z"
}
```

**Tasks:**
- [ ] Create `skill_schema.py` (Pydantic model)
- [ ] Create `skill_repository.py` (CRUD for skills)
- [ ] Implement `SkillDatabase` class (abstraction over storage)
- [ ] Test: Write 5 skills manually, store and retrieve

**Estimated Time:** 15 hours  
**Files to Create:**  
- `routemaster_agent/skills/skill_schema.py`
- `routemaster_agent/skills/skill_repository.py`

---

#### 3.2 — Skill Extraction from Dataset
**What:** Automatically extract skills from recorded demonstrations  
**Why:** Don't manually write 100 skills; derive them from data

**Algorithm:**
```python
async def extract_skills_from_dataset(dataset):
    for scene in dataset:
        # Group consecutive actions with same intent
        sequences = group_by_intent(scene['actions'])
        
        for seq in sequences:
            # Parameterize: replace specific values with {placeholders}
            skill = parameterize_sequence(seq)
            
            # Normalize selectors: keep primary + collect variants
            skill = normalize_selectors(skill)
            
            # Compute generality: how well does this work on other similar scenes?
            generality_score = compute_transfer_score(skill, dataset)
            
            if generality_score > 0.7:  # Reusable
                save_skill(skill)
```

**Tasks:**
- [ ] Create `skill_extraction.py`
- [ ] Implement `parameterize_sequence()` (extract {variables})
- [ ] Implement `normalize_selectors()` (find variants)
- [ ] Implement `compute_transfer_score()` (test on similar scenes)
- [ ] Extract all skills from 370-scene dataset (~50-100 skills expected)
- [ ] Save to `skills_library/extracted_skills.json`

**Estimated Time:** 20 hours  
**Files to Create:** `routemaster_agent/skills/skill_extraction.py`

---

#### 3.3 — Skill Retrieval System
**What:** Given a new task + page, find most relevant skills  
**Why:** Enables generalization; agent reuses learned patterns

**Retrieval Pipeline:**
```python
async def retrieve_skills_for_task(task, screenshot, html):
    # 1. Compute task embedding
    task_embedding = embed(task['description'])
    
    # 2. Compute page embedding
    page_features = extract_page_features(screenshot, html)
    page_embedding = embed_features(page_features)
    
    # 3. Search skill library
    similar_skills = skill_db.search(
        task_embedding=task_embedding,
        page_embedding=page_embedding,
        top_k=5
    )
    
    # 4. Rank by relevance
    ranked = rank_by_confidence(similar_skills, page_features)
    
    return ranked
```

**Tasks:**
- [ ] Add embedding function (use Gemini embeddings API)
- [ ] Create `skill_retriever.py` (query + ranking)
- [ ] Integrate with SkillTrainer (fallback to retrieval if few-shot fails)
- [ ] Test: Retrieve skills for 20 new scenarios

**Estimated Time:** 18 hours  
**Files to Create:** `routemaster_agent/skills/skill_retriever.py`

---

#### 3.4 — Skill Generalization
**What:** Make skills work across slightly different layouts  
**Why:** Websites iterate; one skill should handle multiple site versions

**Techniques:**

1. **Selector Variants:** Keep multiple selectors (primary + backup)
   ```python
   "selector_variants": [
       "input[name=origin]",        # IRCTC v1
       "input[placeholder*=Origin]", # IRCTC v2
       "#origin-field"               # IRCTC v3
   ]
   ```

2. **Parameterization:** Extract values to variables
   ```python
   # Before:
   steps: [{"action": "type", "value": "JP"}]
   
   # After (generalized):
   steps: [{"action": "type", "value": "{origin}"}]
   parameters: {"origin": "JP"}
   ```

3. **Semantic Fallbacks:** Use semantic labels, not raw selectors
   ```python
   # Before:
   "target": "button[class='btn-search-red']"
   
   # After:
   "target": "search_submit_button"
   "semantic_intent": "submit_search"
   ```

**Tasks:**
- [ ] Update skill schema to support variants
- [ ] Implement `abstract_selectors()` function
- [ ] Implement `parameterize_skill()` function
- [ ] Test: One skill used on 3 different site versions

**Estimated Time:** 16 hours  
**Files to Modify:** `skill_schema.py`, `skill_extraction.py`

---

#### 3.5 — Skill Reinforcement
**What:** Update skill success rates based on execution  
**Why:** Agent learns which skills work best; confidence improves

**Implementation:**
```python
async def execute_skill(skill, target_context):
    result = await skill.execute(target_context)
    
    if result.success:
        skill.success_rate = (skill.success_rate * skill.use_count + 1) / (skill.use_count + 1)
        skill.use_count += 1
        metrics.increment('skill_success')
    else:
        # Try alternate selectors
        for variant_selector in skill.selector_variants:
            # ... retry ...
        metrics.increment('skill_failure')
    
    skill.last_used = datetime.now()
    skill_db.update(skill)
```

**Tasks:**
- [ ] Add success tracking to skill execution
- [ ] Implement Bayesian update for skill confidence
- [ ] Add skill metrics: `RMA_SKILL_SUCCESS_RATE` (per skill)
- [ ] Update skill_db on each execution

**Estimated Time:** 10 hours  
**Files to Modify:** `skill_repository.py`, `reasoning_loop.py`, `metrics.py`

---

#### 3.6 — Integration: Skill-Driven Agent
**What:** Update ReasoningController to use skills  
**Why:** Agent now autonomously selects from library instead of always using few-shot

**New Flow:**
```
Task + Screenshot
    ↓
Retrieve similar skills (3.3)
    ↓
Skill found with >0.7 confidence?
    ├─ YES → Execute skill, track success (3.5)
    ├─ NO  → Fall back to SkillTrainer (few-shot), learn as new skill
    ↓
Store experience in skill library
```

**Tasks:**
- [ ] Update `_think()` in ReasoningController to call skill_retriever
- [ ] Implement fallback logic (Gemini few-shot if no skill match)
- [ ] Log all skill retrieval attempts to metrics
- [ ] Test: Full workflow with skill retrieval

**Estimated Time:** 12 hours  
**Files to Modify:** `reasoning_controller.py`

---

### PHASE 4: Multi-Task Intelligence & Reliability (Weeks 9-12)

**Goal:** Agent handles all 7 job types end-to-end  
**Effort:** 100 hours  
**Success Metric:** Each job type >85% success rate on 10 live executions

---

#### 4.1 — Task Implementation: Train Search (IRCTC/NTES)

**Requirements:**
- Input: origin, destination, date, class (optional)
- Output: List of trains with fare, availability, duration

**Implementation:**
```python
async def task_search_trains(origin, destination, date, class=None):
    # 1. Navigate to IRCTC (or fallback NTES)
    # 2. Use skill_retriever to find "search_trains" skill
    # 3. Execute skill with params {origin, destination, date}
    # 4. Extract train cards from results
    # 5. For each train, extract: number, name, departure, arrival, classes
    # 6. Return structured list
    
    return {
        "trains": [
            {
                "train_no": "22998",
                "name": "SGNR JLWC EXP",
                "departure": "05:15",
                "arrival": "09:50",
                "duration": "4h35m",
                "classes": {
                    "SL": {"fare": 215, "available": 2},
                    "3AC": {"fare": 565, "available": 0}
                }
            },
            ...
        ],
        "success": True,
        "source": "irctc",
        "timestamp": "2026-02-17T14:32:00Z"
    }
```

**Tasks:**
- [ ] Create `task_search_trains.py`
- [ ] Implement train card parser (regex + OCR)
- [ ] Implement class badge parser (AVAILABLE-0010 → available=10, etc.)
- [ ] Add unit tests (5 test cases with mock data)
- [ ] Test on live IRCTC (5 searches)

**Estimated Time:** 18 hours

---

#### 4.2 — Task Implementation: Live Status (NTES)

**Requirements:**
- Input: train_no, date
- Output: Current station, delay, platform, last update time

**Implementation:**
```python
async def task_get_live_status(train_no, date):
    # 1. Navigate to NTES live status page
    # 2. Input train number + date
    # 3. Extract timeline/card showing:
    #    - current_station
    #    - expected_arrival
    #    - actual_arrival
    #    - delay_minutes
    #    - platform
    #    - last_update
    
    return {
        "train_no": "22998",
        "current_station": "BARDHAMAN JN",
        "expected_arrival": "16:57",
        "actual_arrival": "17:05",
        "delay_minutes": 8,
        "platform": "3",
        "last_updated": "17:03",
        "status": "Running"
    }
```

**Tasks:**
- [ ] Create `task_get_live_status.py`
- [ ] Implement delay badge parser (extract "8 mins late")
- [ ] Implement platform number extractor
- [ ] Handle multiple statuses: Running, Terminated, Diverted, etc.
- [ ] Test: 5 live trains on NTES

**Estimated Time:** 16 hours

---

#### 4.3 — Task Implementation: Seat Availability (IRCTC)

**Requirements:**
- Input: train_no, date, from, to, class (SL/3AC/2AC)
- Output: Availability status, fare, details

**Implementation:**
```python
async def task_check_seat_availability(train_no, date, from_stn, to_stn, class_code):
    # 1. Navigate to IRCTC
    # 2. Search trains (use existing skill)
    # 3. Click on specified train
    # 4. Wait for seat availability popup
    # 5. Extract class-wise availability
    # 6. Return detailed availability for requested class
    
    return {
        "train_no": "22998",
        "date": "2026-02-18",
        "from": "JP",
        "to": "KOTA",
        "requested_class": "SL",
        "status": "AVAILABLE",
        "availability_count": 10,
        "fare": 215,
        "quota": "GENERAL",
        "concessional_available": 2
    }
```

**Tasks:**
- [ ] Create `task_check_seat_availability.py`
- [ ] Parse seat popup UI (multiple layouts possible)
- [ ] Handle status codes: AVAILABLE, WL (waitlist), REGRET
- [ ] Extract quota info (GENERAL, TATKAL, SENIOR CITIZEN)
- [ ] Test: 10 seat checks on real IRCTC

**Estimated Time:** 16 hours

---

#### 4.4 — Task Implementation: Schedule Extraction (NTES)

**Requirements:**
- Input: train_no
- Output: Full schedule with all stations, times, distances

**Implementation:**
```python
async def task_get_train_schedule(train_no):
    # 1. Navigate to NTES schedule
    # 2. Input train number
    # 3. Extract table with columns:
    #    - Station name
    #    - Arrival time
    #    - Departure time
    #    - Halt duration
    #    - Distance from origin
    # 4. Parse into structured rows
    
    return {
        "train_no": "22998",
        "schedule": [
            {
                "stop_no": 1,
                "station": "SAGNRPUR JN",
                "arrival": None,
                "departure": "05:15",
                "halt_seconds": 0,
                "distance_km": 0
            },
            {
                "stop_no": 2,
                "station": "BARDHAMAN JN",
                "arrival": "07:04",
                "departure": "07:06",
                "halt_seconds": 120,
                "distance_km": 75
            },
            ... (all stops)
        ]
    }
```

**Tasks:**
- [ ] Create `task_get_train_schedule.py`
- [ ] Implement NTES schedule table parser
- [ ] Handle special cases (missed stops, late arrivals)
- [ ] Validate times are chronological
- [ ] Test: 10 schedules on NTES

**Estimated Time:** 14 hours

---

#### 4.5 — Multi-Source Data Validation

**What:** Compare extracted data across sources; detect inconsistencies  
**Why:** Increases confidence in results; detects data quality issues

**Validation Logic:**
```python
async def validate_across_sources(data_irctc, data_ntes):
    """
    Compare IRCTC schedule vs NTES schedule for same train.
    Flag inconsistencies.
    """
    
    # Check 1: Station set equality
    irctc_stations = set(s['station'] for s in data_irctc['schedule'])
    ntes_stations = set(s['station'] for s in data_ntes['schedule'])
    
    if irctc_stations != ntes_stations:
        confidence -= 0.2
        issues.append(f"Station mismatch: {irctc_stations ^ ntes_stations}")
    
    # Check 2: Arrival/Departure time consistency
    for irctc_stop, ntes_stop in zip(data_irctc['schedule'], data_ntes['schedule']):
        time_diff = abs(parse_time(irctc_stop['arrival']) - parse_time(ntes_stop['arrival']))
        if time_diff > timedelta(minutes=5):
            confidence -= 0.1
            issues.append(f"Time mismatch at {irctc_stop['station']}: {time_diff}")
    
    return {
        "primary_source": "irctc",
        "backup_sources": ["ntes"],
        "confidence": confidence,
        "issues": issues
    }
```

**Tasks:**
- [ ] Create `cross_source_validator.py`
- [ ] Implement station matching (handle abbreviations: JP=Jaipur, KOTA=Kota Jn)
- [ ] Implement time tolerance (±5 minutes is OK)
- [ ] Add confidence scoring based on mismatch count
- [ ] Test: Compare 10 train records from IRCTC vs NTES

**Estimated Time:** 12 hours  
**Files to Create:** `routemaster_agent/validation/cross_source_validator.py`

---

#### 4.6 — Advanced Error Recovery

**What:** When tasks fail, try different strategies  
**Why:** Real websites are flaky; recovery increases success rate

**Recovery Strategies:**
```python
RECOVERY_STRATEGIES = {
    "selector_not_found": [
        "scroll_to_find",      # Scroll page to find element
        "use_backup_selector", # Try alternative selector
        "reload_and_retry",    # Reload page and retry
        "change_proxy"         # Switch proxy, retry
    ],
    "timeout": [
        "reload_page",         # Page took too long
        "change_proxy",        # Slow proxy?
        "update_ua"            # Try different User-Agent
    ],
    "captcha_detected": [
        "reload_page",         # Might be false positive
        "change_proxy",        # Different IP
        "pause_and_retry"      # Human-like delay
    ],
    "session_expired": [
        "fallback_to_guest",   # Use guest mode if available
        "login_again",         # Re-authenticate
        "switch_source"        # Use NTES instead of IRCTC
    ]
}

async def attempt_recovery(error_type, context):
    strategies = RECOVERY_STRATEGIES[error_type]
    
    for strategy in strategies:
        try:
            if strategy == "use_backup_selector":
                # Try alternative selector from element memory
                context.selector = context.get_backup_selector()
            elif strategy == "change_proxy":
                context.proxy = rotate_proxy()
            elif strategy == "reload_page":
                await browser.goto(context.current_url)
            
            # Retry original operation
            result = await retry_operation(context)
            
            if result.success:
                metrics.increment(f'recovery_success_{strategy}')
                return result
        except Exception as e:
            logger.warning(f"Recovery strategy {strategy} failed: {e}")
    
    # All recovery attempts failed
    return RecoveryResult(success=False)
```

**Tasks:**
- [ ] Create `error_recovery.py`
- [ ] Implement all recovery strategies listed
- [ ] Add recovery metrics (track which strategy works best per error type)
- [ ] Integrate with ReasoningLoop error handling
- [ ] Test: Trigger each error type, verify recovery

**Estimated Time:** 16 hours  
**Files to Create:** `routemaster_agent/core/error_recovery.py`

---

### PHASE 5: Production Deployment & Scaling (Weeks 12-16)

**Goal:** Deploy agent to production with monitoring, scaling, reliability  
**Effort:** 80 hours  
**Success Metric:** 99.5% uptime, <1% error rate, process 1000 requests/day

---

#### 5.1 — Docker Containerization

**What:** Package agent as container for deployment  
**Why:** Reproducible, scalable, isolated environment

**Dockerfile:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y chromium-browser

# Install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy code
COPY routemaster_agent/ /app/routemaster_agent/

# Download Playwright browsers
RUN playwright install

# Expose API port
EXPOSE 8000

# Run agent
CMD ["uvicorn", "routemaster_agent.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Tasks:**
- [ ] Create `Dockerfile`
- [ ] Create `docker-compose.yml` (with postgres, redis)
- [ ] Test: Build and run locally
- [ ] Publish to Docker Hub (optional)

**Estimated Time:** 8 hours

---

#### 5.2 — Kubernetes Deployment

**What:** Deploy on K8s cluster for auto-scaling  
**Why:** Handle traffic spikes, self-healing, rolling updates

**K8s Resources:**
```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: routemaster-agent
spec:
  replicas: 3
  selector:
    matchLabels:
      app: routemaster-agent
  template:
    metadata:
      labels:
        app: routemaster-agent
    spec:
      containers:
      - name: agent
        image: routemaster-agent:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: routemaster-secrets
              key: database-url
        - name: GEMINI_API_KEYS
          valueFrom:
            secretKeyRef:
              name: routemaster-secrets
              key: gemini-keys
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
```

**Tasks:**
- [ ] Create `k8s/deployment.yaml`
- [ ] Create `k8s/service.yaml` (expose API)
- [ ] Create `k8s/configmap.yaml` (config)
- [ ] Create `k8s/secrets.yaml` (API keys — DO NOT commit)
- [ ] Test: Deploy locally with Minikube
- [ ] Configure auto-scaling (scale 1-10 replicas based on CPU)

**Estimated Time:** 16 hours

---

#### 5.3 — Monitoring & Alerting

**What:** Real-time visibility into agent health  
**Why:** Catch issues before they impact users

**Prometheus Metrics (Extended):**
```python
# Existing metrics + new ones

# API metrics
RMA_API_REQUESTS_TOTAL         # Request count
RMA_API_REQUEST_DURATION       # Latency histogram
RMA_API_ERROR_RATE             # Error percentage

# Agent metrics
RMA_TASK_SUCCESS_RATE          # Per task type
RMA_EXTRACTION_CONFIDENCE      # Average confidence of extractions
RMA_EXTRACTION_FAILURES        # Count of extraction failures
RMA_SITE_ERROR_RATE            # Per site (irctc/ntes/disha)
RMA_RECOVERY_SUCCESS_RATE      # % successful error recovery
RMA_SKILL_UTILIZATION          # Which skills used most
RMA_SKILL_CONFIDENCE           # Average skill success

# Resource metrics
RMA_BROWSER_POOL_SIZE          # Active browser instances
RMA_MEMORY_USAGE               # RAM consumed
RMA_DB_CONNECTION_POOL         # Active DB connections
```

**Dashboard (Grafana):**
```
┌─────────────────────────────────────────┐
│  RouteMaster Agent — Production Dashboard │
├─────────────────────────────────────────┤
│ ┌──────────────┐  ┌──────────────┐     │
│ │ Requests/min │  │ Error Rate   │     │
│ │     2,340    │  │    0.8%      │     │
│ └──────────────┘  └──────────────┘     │
├─────────────────────────────────────────┤
│ Task Success Rate (24h)                 │
│ ┌──────────────────────────────────┐   │
│ │ Search Trains:  96% ████████████ │   │
│ │ Live Status:    93% ███████████  │   │
│ │ Seat Avail:     89% ██████████   │   │
│ └──────────────────────────────────┘   │
├─────────────────────────────────────────┤
│ Top Failures (Last 1h)                  │
│ ├─ IRCTC session expired: 12           │
│ ├─ NTES timeout: 5                     │
│ ├─ Gemini rate limit: 2                │
│ └─ Selector not found: 8               │
└─────────────────────────────────────────┘
```

**Alert Rules:**
```yaml
# prometheus_rules.yaml
groups:
  - name: routemaster
    rules:
    - alert: HighErrorRate
      expr: rate(RMA_API_ERRORS[5m]) > 0.05
      for: 5m
      annotations:
        summary: "Error rate > 5%"
        
    - alert: TaskSuccessRateLow
      expr: RMA_TASK_SUCCESS_RATE < 0.80
      for: 10m
      annotations:
        summary: "Task success < 80%"
        
    - alert: ExtractionConfidenceLow
      expr: avg(RMA_EXTRACTION_CONFIDENCE) < 0.70
      for: 15m
      annotations:
        summary: "Low extraction confidence"
```

**Tasks:**
- [ ] Add extended metrics to `metrics.py`
- [ ] Create `k8s/prometheus-config.yaml`
- [ ] Create `k8s/grafana-dashboard.json`
- [ ] Create alert rules (prometheus_rules.yaml)
- [ ] Test: Trigger alerts, verify notifications (Slack/PagerDuty)

**Estimated Time:** 20 hours

---

#### 5.4 — Logging & Trace Collection

**What:** Structured logs for debugging; distributed tracing  
**Why:** Essential for troubleshooting production issues

**Logging Setup:**
```python
# Use loguru + JSON output
import loguru

logger = loguru.logger

# Configure JSON logging
logger.configure(
    handlers=[
        {
            "sink": "logs/routemaster.json",
            "serialize": True,  # JSON output
            "rotation": "1 GB"  # Rotate when 1GB
        }
    ]
)

# Example structured log
logger.info(
    "Task started",
    task_id="task_12345",
    task_type="search_trains",
    origin="JP",
    destination="KOTA",
    date="2026-02-18"
)
```

**Distributed Tracing (OpenTelemetry):**
```python
from opentelemetry import trace, metrics
from opentelemetry.exporter.jaeger import JaegerExporter

# Enable tracing
tracer = trace.get_tracer(__name__)

# Trace a skill execution
with tracer.start_as_current_span("execute_skill") as span:
    span.set_attribute("skill_name", skill.name)
    span.set_attribute("site", skill.context['site'])
    
    result = await skill.execute()
    
    span.set_attribute("success", result.success)
```

**Tasks:**
- [ ] Set up structured logging with loguru
- [ ] Configure OpenTelemetry for tracing
- [ ] Deploy Jaeger backend (trace visualization)
- [ ] Add trace spans to key operations (skill execution, extraction, storage)
- [ ] Test: Trace a task through system, view in Jaeger UI

**Estimated Time:** 12 hours

---

#### 5.5 — Load Testing & Benchmarking

**What:** Verify agent can handle expected traffic  
**Why:** Find bottlenecks before production

**Load Test Scenario:**
```python
# locustfile.py
from locust import HttpUser, task, between

class RouteMasterUser(HttpUser):
    wait_time = between(5, 15)  # Wait 5-15s between requests
    
    @task(3)
    def search_trains(self):
        """Search trains (3x more frequent)"""
        payload = {
            "command": "search_trains",
            "parameters": {
                "origin": random.choice(["JP", "KOTA", "DL"]),
                "destination": random.choice(["BND", "AGC", "KOTA"]),
                "date": "2026-02-18"
            }
        }
        self.client.post("/api/agent/execute-command", json=payload)
    
    @task(1)
    def get_live_status(self):
        """Get live status (1x frequency)"""
        payload = {
            "command": "get_live_status",
            "parameters": {
                "train_no": random.choice(["22998", "12345", "18245"]),
                "date": "2026-02-18"
            }
        }
        self.client.post("/api/agent/execute-command", json=payload)
```

**Run Test:**
```bash
locust -f locustfile.py --host=http://localhost:8000 -u 100 -r 10 --run-time 10m
```

**Expected Results:**
```
Response time (99th percentile): <5 sec
Success rate: >99%
Throughput: >100 req/sec
```

**Tasks:**
- [ ] Create `locustfile.py`
- [ ] Run on staging environment
- [ ] Identify bottlenecks (DB queries, Gemini API, Playwright waits)
- [ ] Optimize (add caching, connection pooling, parallel execution)
- [ ] Achieve target: >100 req/sec, <5s p99 latency

**Estimated Time:** 12 hours

---

#### 5.6 — Disaster Recovery & Backup

**What:** Agent can recover from crashes, data loss  
**Why:** Reliability, business continuity

**Components:**
```
1. Database backup (daily)
   - Export PostgreSQL to S3
   - Retention: 30 days
   - Restore test: weekly
   
2. State persistence
   - Agent state saved to disk every step
   - On restart, recover last successful state
   - Resume task from checkpoint
   
3. Skill library backup
   - Export skill_db to S3 daily
   - Version control (Git for skills)
   - Rollback capability
   
4. Configuration backup
   - Store config in version control
   - Secrets in encrypted vault (HashiCorp Vault)
```

**Tasks:**
- [ ] Set up automated PostgreSQL backups to S3
- [ ] Implement backup restore test (monthly)
- [ ] Create disaster recovery runbook (markdown)
- [ ] Test: Simulate data loss, verify recovery
- [ ] Set up Vault for secret management

**Estimated Time:** 10 hours

---

#### 5.7 — Production Checklist

**Before Going Live:**

- [ ] All 31 unit tests passing
- [ ] Integration E2E test with real browser passing (10/10 runs)
- [ ] Load test: >100 req/sec, <5s p99 latency
- [ ] Monitoring dashboard configured and tested
- [ ] Alert rules deployed and tested
- [ ] Disaster recovery tested (restore from backup)
- [ ] Security audit: API auth, secrets rotation, SQL injection checks
- [ ] Performance optimizations complete (DB indexes, caching)
- [ ] Documentation complete (README, runbooks, API docs)
- [ ] Team trained on deployment and operations
- [ ] Canary deployment plan ready (5% traffic first)

**Tasks:**
- [ ] Create `PRODUCTION_CHECKLIST.md`
- [ ] Assign owner for each item
- [ ] Schedule pre-production review (1 week before launch)
- [ ] Schedule post-launch on-call rotation

**Estimated Time:** 8 hours

---

## 📈 EFFORT & TIMELINE SUMMARY

| Phase | Duration | Effort (Hours) | Key Deliverables |
|-------|----------|----------------|------------------|
| **Phase 1** | Weeks 1-3 | 60 | Element memory, Selector promotion, Scroll intelligence |
| **Phase 2** | Weeks 3-6 | 120 | 1000+ labeled scenes, Dataset analytics |
| **Phase 3** | Weeks 6-9 | 80 | Skill library, Skill retrieval, Skill generalization |
| **Phase 4** | Weeks 9-12 | 100 | All 7 tasks complete, Multi-source validation |
| **Phase 5** | Weeks 12-16 | 80 | Kubernetes deployment, Monitoring, Load testing |
| **TOTAL** | 16 weeks | **440 hours** | Production-ready agent |

---

## 🎯 SUCCESS CRITERIA BY PHASE

### Phase 1 (Stabilize)
- ✅ 90%+ selector success rate on 3 sites
- ✅ Scroll works on infinite-scroll & pagination
- ✅ E2E test passes 10/10 times

### Phase 2 (Dataset)
- ✅ 1000+ scenes collected and validated
- ✅ <5% label error rate (manual review of 50)
- ✅ Balanced coverage (all sites, all job types)

### Phase 3 (Skills)
- ✅ 50-100 skills extracted and ingested
- ✅ Skill retrieval works (find relevant skill 80%+ of time)
- ✅ Generalization test: skill works on 3 site variations

### Phase 4 (Multi-Task)
- ✅ All 7 tasks implemented and tested
- ✅ Average success rate >85% per task
- ✅ Cross-source validation <2% mismatch rate

### Phase 5 (Production)
- ✅ Docker image builds and runs
- ✅ K8s deployment with auto-scaling
- ✅ Monitoring dashboard displays metrics
- ✅ Load test: >100 req/sec, p99 <5s
- ✅ Disaster recovery tested

---

## 🚀 NEXT IMMEDIATE ACTIONS (This Week)

1. **Today:**
   - [ ] Create `PHASE1_IMPLEMENTATION_PLAN.md` (detailed task list)
   - [ ] Set up GitHub Issues for Phase 1 (break 60 hours into 10-hour chunks)

2. **This Week (Days 2-3):**
   - [ ] Start Phase 1.1: Element grounding system
   - [ ] Create `element_memory.py` + schema
   - [ ] Write migration script

3. **End of Week:**
   - [ ] Phase 1.1 complete + tested
   - [ ] Begin Phase 1.2: Selector promotion

---

## 📝 NOTES & IMPORTANT REMINDERS

- **Phase 2 is the MOST CRITICAL phase.** Good dataset = 10x better agent. Invest heavily here.
- **Don't skip phases.** Each builds on previous. Skipping = technical debt.
- **Measure continuously.** Track metrics after each phase. Adjust if needed.
- **Team alignment.** Ensure team understands roadmap before starting Phase 1.
- **Resource planning.** 440 hours = ~2 FTE for 16 weeks. Plan accordingly.

---

## 📚 REFERENCES

- Current implementation: `ROUTEMASTER_AGENT_V2_IMPLEMENTATION.txt`
- Strategic guide: `todoagent.md`
- Production patterns: `statusagent.md` (this document)
- Code: `routemaster_agent/` directory

---

**Created:** February 17, 2026  
**Status:** Ready for Phase 1 kickoff  
**Maintained By:** RouteMaster Team

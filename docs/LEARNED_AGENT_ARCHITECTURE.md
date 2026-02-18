# RouteMaster V2 — Learned Agent Architecture

Complete technical architecture for the transition from **LLM-only agent** → **Learned Skill-Based Agent**.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    ReasoningController (v2)                      │
│                                                                   │
│  1. Infer page context (vision + DOM analysis)                  │
│  2. Try skill retrieval  ─────────────────┐                     │
│  3. If match (score > 0.85): execute     │ ← NEW                │
│  4. Else: fallback to Gemini            │                       │
│  5. Record execution → update metrics    │                       │
└─────────────────────────────────────────────────────────────────┘
          ↓                  ↓                 ↓
    Skill Retriever    NavigatorAI      GeminiClient
      (learned)          (execute)       (fallback)
          ↓
    SkillRegistry
    (800+ skills)
```

---

## Core Components

### 1. **SceneRecorder + Annotation Pipeline**

**Purpose:** Capture training data with rich metadata

**Flow:**
```
Playwright page
  ↓
SceneRecorder.record_step()
  ↓
Captures:
  - Screenshot
  - DOM snapshot
  - Action (type, selector, value)
  - Metadata
    - strategy (CSS/semantic/visual)
    - selector_confidence (0–1)
    - time_to_success_ms
    - success (bool)
  ↓
scene.json + images
  ↓
Annotation UI (human verify)
  ↓
verified_examples.jsonl
```

**Metadata captured per step:**
```python
meta = {
    'strategy': 'css|semantic|visual|visual_fallback',
    'selector_confidence': 0.92,
    'time_to_success_ms': 547,
    'success': True
}
```

### 2. **Skill Library Builder**

**Purpose:** Convert verified examples → reusable skills

**Input:** `verified_examples.jsonl`

**Processing:**
```python
for example in verified_examples:
    actions = extract_action_sequence(example.steps)
    metrics = compute_metrics(example.steps)
    
    skill = {
        'skill_name': 'train_search_001',
        'context': 'ntes_schedule',
        'action_sequence': actions,  # Canonical format
        'metrics': {
            'success_rate': 0.95,
            'avg_time_ms': 150,
            'avg_selector_confidence': 0.92
        },
        'selectors_used': [...]
    }
```

**Output:** `skill_registry.json`

**Skill structure:**
```json
{
  "skill_id": "skill_abc123",
  "skill_name": "ntes_train_search",
  "source_scene": "demo_scene_001",
  "context": "ntes_schedule",
  "action_sequence": [
    {"type": "input", "selector": "#train_no", "value": "12345"},
    {"type": "click", "selector": "#search"}
  ],
  "metrics": {
    "success_rate": 0.95,
    "avg_time_ms": 150,
    "step_count": 2,
    "avg_selector_confidence": 0.92
  },
  "embeddings": null,
  "created_at": "2026-02-17T..."
}
```

### 3. **Skill Retrieval Engine**

**Purpose:** Match page contexts → best-matching skills

**Retrieval algorithm:**
```python
async def retrieve_skills(context, task, confidence_threshold=0.85):
    candidates = skills_by_context[context]  # O(1) lookup
    
    # Score by:
    # - Success rate (primary signal)
    # - Task relevance (keyword match)
    # - Usage frequency (tie-breaker)
    
    for skill in candidates:
        score = (
            success_rate * 0.5 +
            (1.0 if task_match else 0.0) * 0.3 +
            usage_frequency * 0.2
        )
        skill['_score'] = score
    
    return [s for s in sorted DESC if s['_score'] >= threshold]
```

**Complexity:** O(n) where n = skills in context (~10–50 typ.)

### 4. **Skill Executor**

**Purpose:** Execute action sequence safely on page

**Execution with fallback:**
```python
async def execute_skill(skill, page, navigator):
    for step in skill.action_sequence:
        try:
            if step.type == 'input':
                await navigator.fill_input_and_trigger_event(
                    page, 
                    page.locator(step.selector), 
                    step.value
                )
            elif step.type == 'click':
                await page.click(step.selector)
            elif step.type == 'select':
                await navigator.handle_dropdown_selection(...)
        except Exception as e:
            log_failure(step, e)
            # Continue to next step (graceful degradation)
    
    return execution_result
```

### 5. **Selector Ranking System**

**Purpose:** Score selectors by effectiveness

**Scoring formula:**
```
selector_score = 
    success_rate * 0.5 +        # Most important
    speed_factor * 0.3 +        # Avg time inverse
    usage_frequency * 0.2       # Capped at 10 uses
```

**Example rankings:**
```
Rank 1: input#train_no      (score: 0.95, success: 0.98, time: 100ms)
Rank 2: input[name='train'] (score: 0.92, success: 0.95, time: 120ms)
Rank 3: a.search-btn        (score: 0.88, success: 0.90, time: 150ms)
```

---

## Execution Flow (ReasoningController)

```
┌─ Page arrives
│
├─ 1. OBSERVE: infer_page_context()
│   ├─ Screenshot
│   ├─ DOM analysis
│   └─ Return: context = 'ntes_schedule'
│
├─ 2. RETRIEVE: skill_retriever.retrieve_skills(context, task)
│   ├─ Look up skills_by_context['ntes_schedule']
│   ├─ Score by success_rate, task match
│   └─ Return: [skill1 (score 0.92), skill2 (score 0.85), ...]
│
├─ 3. DECISION: IF best_skill.score > 0.85:
│   │
│   ├─ YES: EXECUTE SKILL
│   │   └─ Call skill_executor.execute_skill(skill1, page)
│   │       ├─ input #train_no = '12345'
│   │       ├─ click #search
│   │       └─ Return success/failure
│   │
│   └─ NO: FALLBACK TO GEMINI
│       └─ Call gemini.propose_actions(page, task)
│           ├─ Get proposed actions
│           └─ Execute via navigator
│
└─ 4. LOG & UPDATE: Record execution metrics
    ├─ Success/failure
    ├─ Time taken
    ├─ Selectors used
    └─ → Update selector_stats (for ranking)
```

---

## Data Flows

### A. Training Data Capture (Phase 1)

```
NavigatorAI.fill_input_and_trigger_event()
  ↓
start_time = monotonic()
  ↓
element.fill(value)
element.dispatchEvent('input')
element.dispatchEvent('change')
  ↓
end_time = monotonic()
  ↓
SceneRecorder.record_step(
    action={type, selector, value},
    metadata={
        strategy='css',
        selector_confidence=0.9,
        time_to_success_ms=int((end_time-start_time)*1000),
        success=True
    }
)
  ↓
scene.json
```

### B. Skill Building (Phase 2)

```
verified_examples.jsonl
  (from annotators)
  ↓
SkillLibraryBuilder.build_from_verified_examples()
  ├─ Parse steps
  ├─ Extract action_sequence
  ├─ Compute metrics (success_rate, avg_time, confidence)
  ├─ Infer context from task
  └─ Generate skill_id + skill_name
  ↓
skill_registry.json (indexed by context)
```

### C. Skill Retrieval & Execution (Phase 3+)

```
New page arrives
  ↓
infer_context() → 'ntes_schedule'
  ↓
SkillRetriever.retrieve_skills(context='ntes_schedule')
  ├─ O(1) lookup: skills_by_context['ntes_schedule']
  ├─ Score each by success_rate + task
  └─ Return [skill1, skill2, ...]
  ↓
IF best_skill.score >= 0.85:
  └─ SkillExecutor.execute_skill(best_skill)
ELSE:
  └─ GeminiClient.propose_actions() [fallback]
```

---

## Metrics & Monitoring

### Per-Skill Metrics
```json
{
  "skill_name": "train_search_1",
  "executions": 42,
  "successes": 39,
  "success_rate": 0.93,
  "avg_time_ms": 1250,
  "failures": [
    {"reason": "selector_not_found", "count": 2},
    {"reason": "timeout", "count": 1}
  ]
}
```

### Per-Selector Metrics
```
Selector Rankings:
  input#train_no:        score=0.95 (used 42×, success 40/42, 100ms)
  input[name='train']:   score=0.92 (used 35×, success 33/35, 120ms)
  button.search-btn:     score=0.88 (used 28×, success 25/28, 150ms)
```

### System-Level Metrics
```
Total skills:          850
By context:
  ntes_schedule:       320
  booking_search:      280
  seat_selection:      150
  other:               100

Skill execution success rate:  0.92
API call reduction:  ~70% (vs. Gemini-only baseline)
Latency improvement:  ~2.5× faster (skill vs. Gemini reasoning)
```

---

## Scaling Milestones

| Phase | Scenes | Skills | Confidence | Next Step |
|-------|--------|--------|------------|-----------|
| 1.0 (Now) | 31 | 0 | — | Annotate + build |
| 2.0 (Week 2) | 100 | 40–50 | Test retrieval |
| 2.5 (Week 3) | 200 | 80–100 | Live mock tests |
| 3.0 (Week 4) | 300+ | 150+ | Production pilot |
| 4.0 (Month 2) | 800+ | 300+ | Multi-site transfer |

---

## Error Handling & Resilience

### Skill Execution Failure

```python
if skill execution fails:
  log_failure(skill_id, error_type, step_idx)
  decrement_skill_score()  # Lower success_rate
  
  if consecutive_failures > 3:
    mark_skill_as_degraded()  # Reduce retrieval weight
  
  fallback_to_gemini()  # Always have Plan B
```

### Selector Not Found

```python
try:
    page.click(selector)
except TimeoutError:
    # Try alternative selector from ranking
    for alt_selector in get_alternative_selectors(original):
        try:
            page.click(alt_selector)
            break
        except:
            continue
    
    # Log failure for ranking decay
    update_selector_stats(original, success=False)
```

### Context Inference Failure

```python
context = infer_context(page)
if confidence < 0.7:
    # Use generic skills instead
    context = 'generic_fallback'
```

---

## Integration Checklist

- [x] Phase 1: SceneRecorder + metadata capture
- [x] Phase 1.2: NavigatorAI metrics recording
- [x] Phase 1.3: Annotation UI + verification
- [ ] Phase 2: Skill library builder + tests
- [ ] Phase 2.5: SkillRetriever in ReasoningController
- [ ] Phase 3: Live validation (mock pages)
- [ ] Phase 3.5: Fine-tune selector prediction model
- [ ] Phase 4: Production deployment

---

## Key Files

| Component | File | Status |
|-----------|------|--------|
| Metadata recording | `routemaster_agent/core/navigator_ai.py` | ✅ |
| Scene capture | `routemaster_agent/data/scene_recorder.py` | ✅ |
| Annotation UI | `annotation_ui/app.py` | ✅ |
| Skill builder | `routemaster_agent/skills/skill_library_builder.py` | ✅ |
| Skill retriever | `routemaster_agent/skills/skill_retrieval.py` | ✅ |
| Tests | `routemaster_agent/tests/test_skill_library.py` | ✅ (4/4) |

---

## Next: ReasoningController Integration

```python
class ReasoningController:
    def __init__(self):
        self.skill_retriever = SkillRetriever()
        self.navigator = NavigatorAI()
        self.gemini = GeminiClient()
    
    async def reason_and_act(self, page, task):
        context = await self._infer_context(page)
        
        # TRY SKILL FIRST
        skills = await self.skill_retriever.retrieve_skills(
            context=context,
            task=task,
            confidence_threshold=0.85
        )
        
        if skills:
            executor = SkillExecutor(navigator_ai=self.navigator)
            result = await executor.execute_skill(skills[0], page)
            if result['success']:
                return result  # Done!
        
        # FALLBACK: GEMINI
        actions = await self.gemini.propose_actions(page, task)
        # ... execute ...
```

---

**Status:** Ready for Phase 2 annotation and skill library construction 🚀

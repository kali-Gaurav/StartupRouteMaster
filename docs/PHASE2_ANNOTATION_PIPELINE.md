# Phase 2 — Annotation & Skill Library Pipeline

Complete end-to-end guide for converting recorded demo scenes into a trained skill library.

## Architecture Overview

```
Raw Scenes (30×)
    ↓
Annotation UI (human verify)
    ↓
verified_examples.jsonl
    ↓
Skill Library Builder
    ↓
skill_registry.json
    ↓
Skill Retriever
    ↓
NavigatorAI + SkillExecutor
    ↓
Live validation (controlled)
```

## Step-by-Step Workflow

### Step 1: Annotation & Verification (CRITICAL)

**Start annotation UI:**
```bash
streamlit run annotation_ui/app.py
```

**Annotator actions:**
- Review screenshot + proposed actions
- Verify metadata (strategy, confidence, time)
- ✅ Approve / ✏️ Edit / ❌ Reject

**Output:** `datasets/verified_examples.jsonl`

**Check progress:**
```python
from annotation_ui.verification_utils import verification_stats
stats = verification_stats()
print(f"Verified: {stats['approved']} / {stats['total_verified']}")
```

**Example verified example:**
```json
{
  "scene_id": "demo_scene_001",
  "status": "approved",
  "steps": [...],
  "task": "train_search",
  "screenshot": "datasets/raw_scenes/demo_scene_001/step_001.png"
}
```

---

### Step 2: Skill Library Construction

**Build skill registry from verified examples:**
```python
import asyncio
from routemaster_agent.skills.skill_library_builder import build_skill_library

result = asyncio.run(build_skill_library(
    verified_file='datasets/verified_examples.jsonl',
    output_file='datasets/skill_registry.json'
))
print(f"Built {result['skill_count']} skills")
```

**Output:** `datasets/skill_registry.json`

**Skill structure:**
```json
{
  "skill_id": "abc123",
  "skill_name": "train_search_001",
  "source_scene": "demo_scene_001",
  "context": "ntes_schedule",
  "action_sequence": [
    {"type": "input", "selector": "#train_no", "value": "12345"},
    {"type": "click", "selector": "#search"}
  ],
  "metrics": {
    "success_rate": 0.95,
    "avg_time_ms": 150,
    "step_count": 2
  }
}
```

---

### Step 3: Skill Retrieval & Execution

**Retrieve skills by context:**
```python
import asyncio
from routemaster_agent.skills.skill_retrieval import SkillRetriever

retriever = SkillRetriever('datasets/skill_registry.json')
skills = asyncio.run(retriever.retrieve_skills(
    context='ntes_schedule',
    task='search_trains',
    max_results=3
))
```

**Execute a skill:**
```python
from routemaster_agent.skills.skill_retrieval import SkillExecutor
from routemaster_agent.core.navigator_ai import NavigatorAI

executor = SkillExecutor(navigator_ai=NavigatorAI())
result = asyncio.run(executor.execute_skill(skills[0], page=playwright_page))
# Returns: {'success': True, 'steps_executed': 2, 'errors': []}
```

---

### Step 4: Integration with ReasoningController

**Updated reasoning loop:**
```python
class ReasoningController:
    def __init__(self):
        self.skill_retriever = SkillRetriever()
        self.navigator = NavigatorAI()
        self.gemini = GeminiClient()

    async def reason_and_act(self, page, task):
        # STEP 1: Try skill retrieval
        context = await self._infer_page_context(page)
        skills = await self.skill_retriever.retrieve_skills(
            context=context,
            task=task,
            confidence_threshold=0.85
        )

        if skills:
            # STEP 2: Execute high-confidence skill
            executor = SkillExecutor(navigator_ai=self.navigator)
            result = await executor.execute_skill(skills[0], page=page)
            if result['success']:
                return result
            else:
                logger.info(f"Skill execution failed: {result['reason']}")

        # STEP 3: Fallback to Gemini reasoning
        actions = await self.gemini.propose_actions(page, task)
        # ... execute proposed actions
```

---

## Files & Directories

```
datasets/
├── raw_scenes/              ← Raw recorded scenes (31)
│   ├── demo_scene_001/
│   │   ├── scene.json
│   │   ├── step_001.png
│   │   └── ...
├── labeling_manifest.jsonl  ← Input to annotation UI
├── few_shot_examples.jsonl  ← Converted examples
├── verified_examples.jsonl  ← Output from annotation UI ✓
├── qa_report.json          ← QA status
└── skill_registry.json     ← Generated skills ✓

annotation_ui/
├── app.py                   ← Streamlit annotation UI
├── verification_utils.py    ← Stats & batch operations
└── README.md

routemaster_agent/skills/
├── skill_library_builder.py ← Convert verified → skills
├── skill_retrieval.py       ← Retrieve & execute skills
└── __init__.py
```

---

## Metrics & Monitoring

**Verification progress:**
```bash
python annotation_ui/verification_utils.py stats
```

**Skill effectiveness rankings:**
```python
from routemaster_agent.skills.skill_library_builder import SkillLibraryBuilder

builder = SkillLibraryBuilder()
rankings = builder.get_selector_rankings()
# Returns: [{selector, success_rate, avg_time_ms, score}, ...]
```

**Skill retrieval validation:**
```python
from routemaster_agent.skills.skill_retrieval import SkillRetriever

retriever = SkillRetriever()
summary = retriever.get_context_summary('ntes_schedule')
# Returns: {context, skill_count, avg_success_rate, avg_time_ms}
```

---

## Testing Pipeline

```bash
# Test skill library builder
pytest routemaster_agent/tests/test_skill_library.py::test_skill_library_builder -v

# Test skill retriever
pytest routemaster_agent/tests/test_skill_library.py::test_skill_retriever -v

# Test full pipeline
pytest routemaster_agent/tests/test_skill_library.py::test_build_skill_library_integration -v
```

---

## Scaling Guide

| Milestone | Scenes | Use Case | Actions Required |
|-----------|--------|----------|---|
| **Init** | ~30 | Test pipeline | Annotate + build skills |
| **Beta** | ~100 | Internal validation | Add retrieval, test on mock NTES |
| **V1** | ~300 | Reliable automation | Train fine-tuning model, add selector ranking |
| **Production** | 800+ | Production usage | Multi-site knowledge transfer, cost optimization |

---

## Next Actions (14-Day Plan)

**Days 1–3:** ✅ Annotation (this guide)
- [ ] Annotate 31 scenes
- [ ] Achieve 90%+ approval rate
- [ ] Generate verified_examples.jsonl

**Days 4–6:** Skill Library
- [ ] Build initial skill_registry.json
- [ ] Analyze selector effectiveness
- [ ] Document top 20 high-performing selectors

**Days 7–10:** Skill Retrieval Integration
- [ ] Wire skill_retriever into ReasoningController
- [ ] Test skill execution on mock pages
- [ ] Measure skill success rate vs. Gemini fallback

**Days 11–14:** Live Validation
- [ ] Record 50–100 new scenes (with skill execution)
- [ ] Run controlled tests on NTES public site
- [ ] Measure speed improvements (skill vs. Gemini)

---

## Cost & Performance Analysis

**Current state:**
- 31 scenes × 2–4 steps/scene = ~80 total steps
- Each step uses Gemini vision (if no registry match)

**After skill library:**
- High-confidence skill execution = ~0 API calls
- Fallback to Gemini only for novel pages

**Estimated savings:**
- 60–80% reduction in Gemini vision API calls
- 40–60% faster execution (skill direct vs. Gemini reasoning)

---

## Risk Mitigation

1. **Bad annotation data** → Filter by confidence, manual spot-check top 10
2. **Skill overfitting** → Diversify scenes, test on different sites
3. **Selector brittleness** → Score selectors by success, retire failures
4. **Fallback failures** → Always have Gemini ready, log failures
5. **Performance regression** → Track metrics continuously, alert on drops

---

## References

- [Annotation UI README](annotation_ui/README.md)
- [Skill Library Builder Docstring](routemaster_agent/skills/skill_library_builder.py)
- [Skill Retrieval Docstring](routemaster_agent/skills/skill_retrieval.py)
- [Test Suite](routemaster_agent/tests/test_skill_library.py)

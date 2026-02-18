# Phase 2 Quick Start — Annotation & Skill Library

**Objective:** Convert 31 recorded demo scenes into verified examples and a production-ready skill library.

**Timeline:** 14 days (Days 1–3 for annotation, Days 4–6 for skills, Days 7–14 for integration & validation)

---

## ⚡ The 3-Step Fast Track

### **Step 1: Start Annotation UI (5 min setup)**

```bash
pip install streamlit pandas
streamlit run annotation_ui/app.py
```

- Opens http://localhost:8501
- Shows one scene at a time
- Annotator: ✅ Approve / ✏️ Edit / ❌ Reject
- Output: `datasets/verified_examples.jsonl`

**Annotation checklist per scene:**
- [ ] Screenshot visible and clear?
- [ ] Step actions correct?
- [ ] No missing actions?
- [ ] Metadata reasonable (confidence, timing)?

**Target:** Annotate 31 scenes in **2–3 hours** (5 min/scene average)

---

### **Step 2: Build Skill Library (1-2 hours)**

Once annotated:

```python
import asyncio
from routemaster_agent.skills.skill_library_builder import build_skill_library

# Build skills from verified examples
result = asyncio.run(build_skill_library())
print(f"✅ Built {result['skill_count']} skills")
```

**Output:** `datasets/skill_registry.json`

**Validate skills:**
```bash
python annotation_ui/verification_utils.py stats
```

---

### **Step 3: Test Skill Retrieval (30 min)**

```python
import asyncio
from routemaster_agent.skills.skill_retrieval import SkillRetriever

async def test():
    retriever = SkillRetriever()
    skills = await retriever.retrieve_skills('ntes_schedule', task='train_search')
    for skill in skills[:3]:
        print(f"- {skill['skill_name']} (success: {skill['metrics']['success_rate']})")

asyncio.run(test())
```

---

## 📊 Success Metrics

| Metric | Target | What it means |
|--------|--------|---|
| Annotation completion | 100% (31/31 scenes) | High-quality verified data |
| Approval rate | ≥ 90% | Good initial recording quality |
| Skill build success | 100% | No conversion errors |
| Avg skill success rate | ≥ 0.85 | Reliable skill execution |
| Skill retrieval recall | ≥ 0.80 | Can match most pages |

---

## 🚀 Runbook

### **Days 1–3: Annotation**

```
Day 1: Set up + annotate ~10 scenes
Day 2: Annotate ~11 scenes
Day 3: Annotate remaining 10 scenes + QA review
```

**Per session (1 hour = ~12 scenes):**
1. Start UI: `streamlit run annotation_ui/app.py`
2. Review screenshot + steps
3. Approve or edit
4. Move to next scene
5. Monitor progress: `python annotation_ui/verification_utils.py stats`

### **Days 4–6: Skill Library Construction**

**Prerequisite:** All 31 scenes annotated

**Day 4:**
```python
asyncio.run(build_skill_library())  # Build registry
```

**Day 5:**
```python
# Validate selectors
from routemaster_agent.skills.skill_library_builder import SkillLibraryBuilder
builder = SkillLibraryBuilder()
rankings = builder.get_selector_rankings()
# Save top selectors for reuse
```

**Day 6:**
```python
# Unit tests
pytest routemaster_agent/tests/test_skill_library.py -v
```

### **Days 7–10: Skill Retrieval Integration**

Integrate skills into ReasoningController (instructions in [PHASE2_ANNOTATION_PIPELINE.md](PHASE2_ANNOTATION_PIPELINE.md))

### **Days 11–14: Live Validation**

1. Record 50–100 new scenes using skill execution
2. Run controlled tests on NTES mock pages
3. Measure: speed improvement (skill vs. Gemini)

---

## 🔑 Key Files

| File | Purpose | Status |
|------|---------|--------|
| `annotation_ui/app.py` | Streamlit annotation interface | ✅ Ready |
| `annotation_ui/verification_utils.py` | Stats + batch operations | ✅ Ready |
| `routemaster_agent/skills/skill_library_builder.py` | Convert verified → skills | ✅ Ready |
| `routemaster_agent/skills/skill_retrieval.py` | Retrieve + execute skills | ✅ Ready |
| `routemaster_agent/tests/test_skill_library.py` | Unit tests | ✅ Ready (4/4 passing) |
| `datasets/verified_examples.jsonl` | Output from annotation | ⏳ To be generated |
| `datasets/skill_registry.json` | Output from skill builder | ⏳ To be generated |

---

## 🛠️ Advanced Options

### Batch-approve scenes (for testing):
```python
from annotation_ui.verification_utils import batch_approve_scenes
batch_approve_scenes(['demo_scene_001', 'demo_scene_002'])
```

### View selector rankings:
```python
from routemaster_agent.skills.skill_library_builder import SkillLibraryBuilder
builder = SkillLibraryBuilder()
rankings = builder.get_selector_rankings()
for rank in rankings[:10]:
    print(f"{rank['selector']}: {rank['score']}")
```

### Skill execution test:
```python
from routemaster_agent.skills.skill_retrieval import SkillExecutor
executor = SkillExecutor(navigator_ai=NavigatorAI())
result = asyncio.run(executor.execute_skill(skill, page=page))
print(f"Executed: {result['steps_executed']}/{result['total_steps']}")
```

---

## ⚠️ Troubleshooting

**"Streamlit not found"**
```bash
pip install streamlit pandas
```

**"No verified_examples.jsonl"**
→ Complete annotation first

**"Skill retriever returns no skills"**
→ Check skill_registry.json exists and is valid:
```bash
python -c "import json; json.load(open('datasets/skill_registry.json'))" && echo "✅ Valid"
```

**Tests failing**
```bash
pytest routemaster_agent/tests/test_skill_library.py -v
```

---

## 🎯 Next Phase (After Days 14)

- Fine-tune selector prediction model
- Add reinforcement learning from feedback
- Multi-site knowledge transfer
- Cost-optimized inference routing

---

## References

- [Full Pipeline Guide](PHASE2_ANNOTATION_PIPELINE.md)
- [Annotation UI Documentation](annotation_ui/README.md)
- [Skill Builder Docstring](routemaster_agent/skills/skill_library_builder.py)
- [Skill Retriever Docstring](routemaster_agent/skills/skill_retrieval.py)
- [Test Suite](routemaster_agent/tests/test_skill_library.py)

---

**Start now:** `streamlit run annotation_ui/app.py` 🚀

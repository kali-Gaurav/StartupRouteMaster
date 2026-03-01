# Annotation UI — Scene Verification System

Simple Streamlit-based interface for human annotators to review and verify recorded automation scenes before training.

## Features

- ✅ Screenshot preview
- ✅ Proposed actions table + details
- ✅ Metadata display (strategy, confidence, time)
- ✅ Approve / Edit / Reject workflow
- ✅ JSON editor for fine-tuning steps
- ✅ Progress tracking (verified / total)
- ✅ Export to `verified_examples.jsonl`

## Installation

```bash
# Install Streamlit + dependencies
pip install streamlit pandas

# Or use the main requirements:
pip install -r ../requirements.txt
```

## Usage

### Start Annotation UI

```bash
streamlit run annotation_ui/app.py
```

Opens browser at `http://localhost:8501`

### Annotator Workflow

1. **Review Screenshot** — See the recorded page state
2. **Check Actions** — Review proposed automation steps
3. **Verify Metadata** — Confirm strategy, confidence, timing
4. **Take Action**:
   - ✅ **Approve** — Accept steps as-is
   - ✏️ **Edit & Approve** — Modify steps in JSON editor
   - ❌ **Reject** — Mark scene as invalid/incomplete

### Output

Each verified scene is appended to:

```
datasets/verified_examples.jsonl
```

Format:
```json
{
  "scene_id": "demo_scene_001",
  "status": "approved|approved_with_edits|rejected",
  "steps": [...],
  "task": "demo_record",
  "screenshot": "path/to/screenshot.png",
  "timestamp": "2026-02-17T..."
}
```

## Verification Statistics

Check progress:

```bash
python annotation_ui/verification_utils.py stats
```

Output:
```json
{
  "total_verified": 15,
  "approved": 12,
  "approved_with_edits": 2,
  "rejected": 1
}
```

## Batch Operations

Quick-approve multiple scenes (for testing):

```python
from annotation_ui.verification_utils import batch_approve_scenes

batch_approve_scenes(['demo_scene_001', 'demo_scene_002', ...])
```

## Downstream Usage

After annotation:

1. **Skill Library Construction** — Convert verified steps → reusable skills
2. **SkillTrainer Ingestion** — Train few-shot prompt examples
3. **Skill Retrieval** — Match new pages → similar skills

## Notes

- Scenes are verified one-at-a-time (linear progress)
- Edit mode allows JSON fine-tuning of steps
- All output is append-only (safe for parallel runs)
- Rejected scenes can be re-recorded or fixed manually
- Metadata (strategy, confidence, time) informs skill ranking later

## Architecture

```
annotation_ui/
├── app.py                    (Streamlit UI)
├── verification_utils.py     (Stats + batch ops)
└── README.md

Input:
  datasets/labeling_manifest.jsonl    (from scene_ingest.py)

Output:
  datasets/verified_examples.jsonl    (→ SkillTrainer)
```

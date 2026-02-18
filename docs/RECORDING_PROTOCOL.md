# Phase 2 — Recording Protocol

Purpose
- Provide a clear, repeatable procedure and tooling for capturing high-quality scene→action demonstrations used to train the agent.

Goals & targets
- Primary target: 2,500 labeled scenes (you selected 2,500).
- Minimum: 1,000 scenes; collect diverse coverage across job types (search, live status, seats, schedules, booking, validation).

Naming & storage
- Local staging: `datasets/raw_scenes/{scene_id}/`
  - `scene.json` — metadata + ordered steps
  - `step_###.png` — screenshots for each step
  - `labels.json` — auto / human labels (one file per scene)
- Canonical upload: `s3://<bucket>/datasets/phase2/{version}/raw_scenes/{scene_id}/`

Scene JSON schema (example)
{
  "scene_id": "irctc_search_0001",
  "meta": {"site":"irctc","job_type":"search","task":{"origin":"DEL","dest":"BOM"}},
  "created_at": "2026-02-17T12:00:00Z",
  "steps": [
    {"step":1, "action":{"type":"input","selector":"input[name=from]","value":"DEL"}, "screenshot":"step_001.png", "dom":"<html>...", "timestamp":"..."}
  ]
}

Recorder (high-level)
- Use Playwright to capture: screenshot, DOM (`page.content()`), and exact user action (selector, input value).
- Save incremental `scene.json` after every step.
- Provide a dry-run mode (no browser) for unit tests.

Labeling pipeline
1. Auto-label with `SkillTrainer`/Gemini (prelabel)
2. Human verification UI (small web UI or spreadsheet) for QA
3. Export verified labels to `labels.json`

Quality checklist (per scene)
- At least 2 screenshots (before + after important steps)
- Steps <= 12, timestamp-ordered
- Clear `meta.job_type` and minimal task fields
- No PII in screenshots (mask if needed)

Acceptance criteria (Phase 2 deliverable)
- 2,500 labeled scenes uploaded to S3
- Dataset QA report: pass rate ≥ 98% (format/consistency)
- Labeled JSONs compliant with schema

How I will run collection (automation plan)
- Run `SceneRecorder` (Playwright) to capture scenes
- Run `auto_labeler` to prelabel with Gemini
- Human review pass → `dataset_qa.py` to validate
- Upload to S3 via `s3_uploader.py`

Files created by this protocol
- `routemaster_agent/data/scene_recorder.py`
- `routemaster_agent/data/auto_labeler.py`
- `routemaster_agent/data/dataset_qa.py` (QA & analytics)
- `datasets/` folder + upload script

Tips
- Start with a 100-scene pilot to validate pipeline before full 2,500 run.
- Use model-assisted labeling + 10% human verification sampling.

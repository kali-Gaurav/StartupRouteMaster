# Phase 2 — GitHub issue templates (copy → new issues)

## Issue: Recorder PoC — `scene_recorder` (3 days)
- **Description:** Implement Playwright-compatible `SceneRecorder` that captures screenshots, DOM and action metadata and writes `scene.json`.
- **Acceptance:** Unit test records dummy page and writes `scene.json` + screenshots.
- **Estimate:** 3 days

## Issue: Playwright integration for Recorder (5 days)
- **Description:** Wire `SceneRecorder` into a Playwright script that can run headless to capture demonstrations.
- **Acceptance:** `scripts/record_scene.py --task=irctc_search` records one scene end-to-end.
- **Estimate:** 5 days

## Issue: Auto-labeler (Gemini teacher) (4 days)
- **Description:** Implement `auto_labeler` to call `SkillTrainer` and write `labels.json` for each scene.
- **Acceptance:** 100 scenes auto-labeled; sample verified by human reviewer.
- **Estimate:** 4 days

## Issue: Dataset QA & analytics (2 days)
- **Description:** Implement QA checks and dataset analytics dashboard/report for coverage gaps.
- **Acceptance:** `dataset_qa.py` run produces `qa_report.json` and coverage.md.
- **Estimate:** 2 days

## Issue: Label verification UI (3 days)
- **Description:** Small web UI or spreadsheet export to let humans approve/patch labels.
- **Acceptance:** Reviewer can accept/reject labels; export updates `labels.json`.
- **Estimate:** 3 days

## Issue: Data storage & upload (S3) (1 day)
- **Description:** Implement `s3_uploader` and document S3 bucket structure.
- **Acceptance:** `upload_directory_to_s3('datasets/phase2_ready', <bucket>, 'phase2/v1')` succeeds.
- **Estimate:** 1 day

---
Priority: Recorder PoC → Playwright integration → Auto-labeler → QA → Verification UI → Upload

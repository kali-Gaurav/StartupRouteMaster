Datasets folder (Phase 2)

Layout
- `datasets/raw_scenes/{scene_id}/scene.json` — recorded steps + metadata
- `datasets/labeled_scenes/{scene_id}/labels.json` — auto/human labels
- `datasets/qa_report.json` — QA summary

How to use
1. Run Playwright-based `SceneRecorder` to populate `raw_scenes/`
2. Run `auto_labeler` to prelabel each scene
3. Run `dataset_qa.py` to validate
4. Upload to S3 using `s3_uploader.py`

Storage
- Local staging for development; production storage should be S3 (recommended).

Target: 2,500 labeled scenes (distribution across job types).

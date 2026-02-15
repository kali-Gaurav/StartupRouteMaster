RouteMaster AI Agent — minimal scaffold

Run locally:

1) create & activate virtualenv
2) pip install -r requirements.txt
3) playwright install chromium
4) uvicorn main:app --reload --port 8000

Notes:
- The scrapers use Playwright and require browser binaries (step 3).
- DB defaults to a local SQLite file created at runtime.

API Endpoints:
- POST /api/unlock-route-details  — single train verification (NTES + Disha)
- POST /api/enrich-trains       — batch enrich (schedules, live status, optional Disha checks)

Example: POST /api/enrich-trains
{
  "train_numbers": ["12345","11603"],
  "date": "today",
  "use_disha": true,
  "per_segment": false,
  "concurrency": 5
}

Output files (saved to `output/`):
- schedules_YYYYMMDD.json / schedules_YYYYMMDD.csv
- live_status_YYYYMMDD.json / live_status_YYYYMMDD.csv
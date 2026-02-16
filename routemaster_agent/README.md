RouteMaster AI Agent — minimal scaffold

Run locally:

1) create & activate virtualenv
2) pip install -r requirements.txt
3) playwright install chromium
4) uvicorn main:app --reload --port 8000

Notes:
- The scrapers use Playwright and require browser binaries (step 3).
- DB defaults to a local SQLite file created at runtime.

Architecture boundary (MANDATORY):
- `routemaster_agent` is a data-intelligence & ingestion service only — it writes validated data to the shared database and exposes admin/inspection endpoints.
- **Do not** import or call backend application logic from inside `routemaster_agent`.
- Communication MUST be: Agent → Database → Backend (no direct Agent→Backend logic coupling).

API Endpoints:
- POST /api/unlock-route-details  — single train verification (NTES + Disha)
- POST /api/enrich-trains       — batch enrich (schedules, live status, optional Disha checks)
- POST /api/admin/run-rma-tests  — run QA test runner (admin)
- POST /api/admin/detect-changes — run change detection for trains

Example: POST /api/enrich-trains
{
  "train_numbers": ["12345","11603"],
  "date": "today",
  "use_disha": true,
  "per_segment": false,
  "concurrency": 5
}

Alerting (env vars):
- RMA_SLACK_WEBHOOK_URL — Slack incoming webhook for test failures
- RMA_SELECTOR_FAILURE_THRESHOLD — threshold for selector-failure alerts (default 5)

Proxy & UA rotation (env vars):
- RMA_USE_PROXY — true/false to enable proxy usage for scraper and fallback requests
- RMA_PROXY_LIST — comma-separated proxy URLs (e.g. http://host:3128)
- RMA_PROXY_FILE — file path with one proxy URL per line
- RMA_UA_LIST — comma-separated user agents to rotate (overrides built-in list)

Output files (saved to `output/`):
- schedules_YYYYMMDD.json / schedules_YYYYMMDD.csv
- live_status_YYYYMMDD.json / live_status_YYYYMMDD.csv

Test artifacts (QA runner):
- test_output/YYYYMMDD/<train_number>/attempt_N.html
- test_output/YYYYMMDD/<train_number>/attempt_N.png
- test_output/YYYYMMDD/<train_number>/validation_errors_attempt_N.json
- logs/testing_metrics_YYYYMMDD.json (metrics per train run)
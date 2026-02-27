# RouteMaster Backend

This service powers the RouteMaster API.  It uses FastAPI, SQLAlchemy and
Supabase (PostgreSQL + Auth + Realtime).

## Environment

Copy `.env.example` to `.env` and fill in the fields.  Required variables:

- `SUPABASE_URL` – your project URL
- `SUPABASE_KEY` – anon or service key (read‑only for frontend; backend may
  optionally provide `SUPABASE_SERVICE_KEY` for privileged operations)
- `DATABASE_URL` – connection string for the Supabase Postgres pooler (used by
  SQLAlchemy).  You can find this under **Database → Connection** in the
  dashboard; choose **Pooler** if you need IPv4 compatibility.
- `REDIS_URL` – Redis instance (default redis://localhost:6379/0)

Other configuration options live in this file or are documented in
`database/config.py`.

**Never commit real secrets** (Anon key, service key, database URL) to source
control.  Add them to your deployment environment instead.

## Running

Use the virtual environment located in `backend/.venv`:

```powershell
cd backend
& .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head     # apply any new migrations
uvicorn app:app --reload  # start server
```

The startup routine will validate configuration and attempt a quick
Supabase query; any connectivity errors are logged.  All database operations
use SQLAlchemy against `DATABASE_URL`.

## Supabase integration

- Authentication is handled by Supabase.  The `/api/auth` router simply
returns `HTTP 410` to remind clients to use Supabase clients.
- `supabase_client.py` exports the initialized client.  The backend uses the
  service key when available.
- User records are synced locally; see `api/dependencies.py` and
  `services/user_service.py` for details.
- Additional tables (`profiles`, `risk_zones`, `live_locations`) are created
  via Alembic migration `20260226_supabase_profiles_and_triggers.py`.

## Database migrations

All schema changes are managed with Alembic.  Run `alembic upgrade head` after
starting the container or before deploying to ensure the Supabase database is
up‑to‑date.

## Remaining work

The following areas still require implementation or verification:

- route search and booking API endpoints using Supabase data tables
- payment gateway integration (Razorpay/Stripe)
- realtime listeners and WebSocket broadcasting from `live_locations`
- row-level security policies in Supabase for every table

Additional documentation is available in the top-level project files.

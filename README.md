# StartupRouteMaster

A short README with quick references, a rendered Mermaid sequence (search/chat path), a docker-compose example for local development, and CI smoke tests for the API.

---

## Architecture (quick view)
The canonical workflow and algorithm details are in `DOW.md` — see the "Sequence diagram (overview)" section for a Mermaid diagram. Below is the same sequence diagram rendered for quick reference.

```mermaid
sequenceDiagram
  actor User
  participant Frontend
  participant ChatUI as "Chat UI"
  participant Backend
  participant RouteEngine
  participant Cache as "Redis Cache"
  participant DB
  User->>Frontend: Enter origin/destination/date (or use chatbot)
  Frontend->>Backend: POST /api/search {source,destination,date}
  Backend->>Cache: GET route:{md5(query)}
  alt cache hit
    Cache-->>Backend: routes JSON
    Backend-->>Frontend: 200 OK {routes}
  else cache miss
    Backend->>RouteEngine: search_routes(...)
    RouteEngine->>DB: (segments/stations preloaded at startup)
    RouteEngine-->>Backend: matching paths
    Backend->>Cache: SET route:{md5} = routes
    Backend-->>Frontend: 200 OK {routes}
  end
  User->>ChatUI: "Find trains Delhi to Mumbai on 14-02-2026"
  ChatUI->>Backend: POST /chat {message, session_id}
  Backend->>Backend: parse intent/entities
  Backend-->>ChatUI: reply + trigger_search (collected)
  ChatUI->>Frontend: emit event → frontend triggers `/api/search`
```

---

## Docker Compose (example)
Use the existing `docker-compose.yml` for `db` and `redis`. Add the `docker-compose.dev.yml` below (also included in the repo) to run the backend API in a container bound to your local source tree:

```yaml
# docker-compose.dev.yml (example)
version: '3.8'

services:
  api:
    image: python:3.11-slim
    container_name: startupv2_api
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./backend:/app
    working_dir: /app
    environment:
      DATABASE_URL: postgresql://postgres:postgres@db:5432/postgres
      REDIS_URL: redis://redis:6379/0
      LOG_LEVEL: info
    command: /bin/sh -c "pip install -r requirements.txt && uvicorn app:app --host 0.0.0.0 --port 8000"
    ports:
      - "8000:8000"
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
      interval: 5s
      retries: 5

# Start: docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

---

## CI: API smoke tests
A GitHub Actions workflow validates `/health`, `/chat`, and `/api/search` using the same curl examples in `DOW.md`. The workflow spins up Postgres + Redis, starts the backend, and runs smoke curl checks (see `.github/workflows/api-smoke-tests.yml`).

---

See `DOW.md` for the full design, algorithm, and developer guide.

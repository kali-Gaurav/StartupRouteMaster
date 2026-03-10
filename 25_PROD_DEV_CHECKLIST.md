# 25 High-Priority Tasks for Development & Production Integrity

This roadmap ensures a seamless transition from your local development environment (Local Frontend/Backend, SQLite, Upstash Redis URL) to a robust production environment on AWS or Google Cloud (GCP) using your startup credits. 

By completing these 25 tasks, your GitHub repository will be 100% "deployment-ready," meaning you can deploy without broken connections, missing environment variables, or architecture mismatches.

## Phase 1: Environment & Configuration Integrity
*Goal: Ensure the system knows EXACTLY whether it is running in Dev or Prod, preventing accidental local configurations from breaking the cloud deployment.*

*   [ ] **1. Unified Config Validation:** Implement strict validation for environment variables on startup. If a critical production key (like `PROD_DB_URL`) is missing in production, the app should fail instantly rather than breaking silently later.
*   [ ] **2. SQLite (Dev) vs. PostgreSQL (Prod) Toggle:** Update `backend/database/config.py` to automatically use local SQLite (`sqlite:///...`) when `ENV=development`, and AWS RDS/GCP Cloud SQL (PostgreSQL) when `ENV=production`.
*   [ ] **3. Alembic Multi-Dialect Compatibility:** Ensure database migrations (`alembic`) do not use Postgres-specific types (like `JSONB`) locally if testing on SQLite. Use SQLAlchemy's generic `TypeDecorator` or keep dev/prod schemas aligned.
*   [ ] **4. Frontend Dynamic API Mapping:** Ensure `vite.config.ts` and `apiClient.ts` use relative paths (`/api`) in Dev (proxied to localhost:8000) and absolute URLs injected via CI/CD for Prod (e.g., `https://api.yourdomain.com`).
*   [ ] **5. Cloud Secrets Management Prep:** Replace hardcoded or `.env`-dependent secrets in Prod with an integration to AWS Secrets Manager or GCP Secret Manager to securely load API keys at runtime.

## Phase 2: Database & State Resiliency
*Goal: Make data storage fast, secure, and crash-resistant.*

*   [ ] **6. Async SQLAlchemy Setup:** Ensure all database calls use async sessions (`AsyncSession`) to prevent blocking the FastAPI event loop under high production load.
*   [ ] **7. Redis Connection Pooling & Reconnection:** Enhance the Redis client in `multi_layer_cache.py` to handle intermittent cloud network drops without crashing the whole application.
*   [ ] **8. Local Mock Seeding Script:** Create a standard `seed.py` that populates the local SQLite database with test users, train routes, and mock AI data so any new developer can start in 1 minute.
*   [ ] **9. Automated Backup Strategy:** Configure automated daily snapshots for your upcoming AWS RDS/GCP Cloud SQL database and ensure the recovery protocol is documented.
*   [ ] **10. Distributed Lock Handling:** Ensure background tasks (like ETL or scrapers) use Redis locks so that if you deploy 3 backend instances on AWS, they don't all run the same scraper simultaneously.

## Phase 3: Backend Production Readiness
*Goal: Harden the FastAPI application to survive the public internet.*

*   [ ] **11. Production Web Server (Gunicorn/Uvicorn):** Replace the standard `uvicorn app:app` with a Gunicorn process manager running multiple Uvicorn workers (`gunicorn -k uvicorn.workers.UvicornWorker`).
*   [ ] **12. Strict CORS & Allowed Hosts:** Remove `allow_origins=["*"]` in production. Dynamically set this to only allow your exact Vercel/AWS CloudFront frontend domains.
*   [ ] **13. API Rate Limiting:** Implement Redis-based rate limiting on sensitive endpoints (Login, AI booking, Search) to protect against DDoS attacks and unexpected cloud billing spikes.
*   [ ] **14. Health Probes (Liveness/Readiness):** Create `/health/live` and `/health/ready` endpoints. AWS Application Load Balancer / GCP Load Balancers need these to know if your container is healthy or needs restarting.
*   [ ] **15. Centralized Structured Logging:** Switch standard Python print/logging to JSON format (e.g., using `structlog`). This makes it vastly easier to query logs in AWS CloudWatch or GCP Cloud Logging.

## Phase 4: Frontend Optimization & Delivery
*Goal: Deliver a blazing-fast, crash-free React UI to users.*

*   [ ] **16. Multi-Stage Dockerfile for Frontend:** Create a Dockerfile that builds the React app via Node, then serves the static `dist` folder using a lightweight NGINX alpine container (if hosting frontend on AWS/GCP instead of Vercel).
*   [ ] **17. NGINX Compression & Cache Headers:** Configure NGINX (or your CDN) to serve Brotli/Gzip compressed assets and set aggressive Cache-Control headers for images and CSS.
*   [ ] **18. Global Error Boundary & Telemetry:** Implement a React Error Boundary combined with a telemetry service (like Sentry) to catch and report frontend crashes in production before users complain.
*   [ ] **19. Graceful API Degradation:** If the backend takes too long (e.g., a cold start on AWS Cloud Run), the UI should show a graceful "Waking up server..." skeleton rather than a hard timeout error.

## Phase 5: Containerization & CI/CD Pipeline
*Goal: Automate deployments directly from GitHub so you never have to manually copy files to servers.*

*   [ ] **20. Production Backend Dockerfile:** Create a hardened `Dockerfile` for the backend. Use a non-root user, multi-stage builds to minimize image size, and remove all development dependencies.
*   [ ] **21. Exact Replica Docker Compose:** Create a `docker-compose.prod.yml` that strictly mimics production (e.g., using a Postgres container instead of SQLite) so you can test the exact production image locally before deploying.
*   [ ] **22. GitHub Actions: Continuous Integration (CI):** Create a workflow `.github/workflows/ci.yml` that runs automatically on PRs. It must: run PyTest, verify TypeScript builds, and check formatting.
*   [ ] **23. GitHub Actions: Continuous Deployment (CD):** Create a workflow `.github/workflows/cd.yml` that builds Docker images and pushes them to AWS ECR / GCP Artifact Registry upon merging to the `main` branch.

## Phase 6: Cloud Infrastructure (AWS/GCP Prep)
*Goal: Utilize your startup credits effectively with modern, auto-scaling architecture.*

*   [ ] **24. Infrastructure as Code (IaC) Foundations:** Write basic Terraform or setup configurations for your target cloud (e.g., AWS ECS Fargate or GCP Cloud Run for Serverless containers) so the infrastructure is version-controlled.
*   [ ] **25. DNS, SSL, and CDN Setup:** Map your custom domain, set up managed SSL certificates (via AWS Certificate Manager or Google Managed SSL), and route traffic through a CDN to protect your backend IP.

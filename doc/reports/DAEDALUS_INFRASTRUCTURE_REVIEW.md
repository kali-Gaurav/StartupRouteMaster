# Infrastructure & DevOps Deep-Dive Review Report
**Reviewer:** DAEDALUS
**Department:** DevOps & Infrastructure
**Date:** 2026-05-22
**Scope:** Docker configurations, Kubernetes manifests, CI/CD pipelines, Monitoring, and Logging.

## Executive Summary
The RouteMaster infrastructure demonstrates a solid foundation with containerization, Kubernetes orchestration, and a comprehensive monitoring stack. The use of modern tools like Prometheus, Grafana, Loki, and GitHub Actions shows a commitment to observability and automation. 

However, there are critical architecture and configuration flaws that need immediate attention. The CI/CD pipelines are fragmented and pushing to multiple registries simultaneously. The Kubernetes manifests contain conflicting resources that will cause deployment failures or data corruption. Furthermore, logging configurations are not set up to actually capture container logs, and Nginx Ingress routing is misconfigured. Addressing these issues will significantly improve the stability, security, and maintainability of the platform.

## Insights

### Category 1: Docker Configuration & Best Practices

#### Insight #1: Fake Multi-Stage Build in Backend Dockerfile
- **Severity:** 🟡 Medium
- **Type:** Optimization
- **File(s):** `Dockerfile`
- **Finding:** The backend `Dockerfile` claims to be a multi-stage build (`FROM python:3.11-slim as builder`) but it never starts a second stage. It installs dependencies globally and runs from the `builder` stage, defeating the purpose of multi-stage builds and resulting in a larger image size containing build dependencies.
- **Recommendation:** Implement a true multi-stage build by installing dependencies into a virtual environment or user directory (`pip install --user`), and then copying only those built artifacts into a fresh, minimal second stage.
- **Impact:** Reduces Docker image size and attack surface in production.

#### Insight #2: Root User in Frontend Production Image
- **Severity:** 🟠 High
- **Type:** Security
- **File(s):** `Dockerfile.frontend`
- **Finding:** The frontend Dockerfile correctly uses a multi-stage build, but the final stage installs `serve` globally and runs the node process as the default `root` user. 
- **Recommendation:** Add a non-root user (e.g., `USER node`) in the final stage before the `CMD` instruction to run the server with restricted privileges.
- **Impact:** Prevents potential privilege escalation if the container is compromised.

#### Insight #3: Missing Database Service in Dev Compose
- **Severity:** 🔴 Critical
- **Type:** Bug
- **File(s):** `docker-compose.dev.yml` (Line 74)
- **Finding:** The `grafana` service defines a `depends_on: - db` constraint, but there is no `db` service defined anywhere in the `docker-compose.dev.yml` file (since it relies on external Supabase). Running `docker-compose -f docker-compose.dev.yml up` will immediately fail.
- **Recommendation:** Remove `db` from the `depends_on` list of the `grafana` service in the development compose file.
- **Impact:** Fixes the broken local development environment setup.

#### Insight #4: Missing Healthchecks on Critical Infrastructure
- **Severity:** 🟡 Medium
- **Type:** Best Practice
- **File(s):** `docker-compose.yml`
- **Finding:** While the Postgres and Redis services have healthchecks, the `kafka` and `zookeeper` services do not. This can lead to dependent services starting before the message broker is fully ready to accept connections.
- **Recommendation:** Add standard healthchecks for Kafka (using `kafka-topics` or `nc`) and Zookeeper (using `echo ruok | nc localhost 2181`) to ensure proper startup sequencing.
- **Impact:** Prevents crash-looping of backend services during local environment startup.

### Category 2: Kubernetes Manifest Correctness

#### Insight #5: Conflicting Postgres and Redis Deployments
- **Severity:** 🔴 Critical
- **Type:** Bug / Architecture
- **File(s):** `k8s/postgres.yaml`, `k8s/redis.yaml`, `k8s/production-deployments.yaml`
- **Finding:** The `k8s/` directory contains conflicting definitions. `production-deployments.yaml` defines a `StatefulSet` and `Service` for both Postgres and Redis. However, `postgres.yaml` and `redis.yaml` define a `Deployment` and `Service` for the same components. When `kubectl apply -f k8s/` is run via CI/CD, this will cause resource collisions, overwritten services, and multiple uncoordinated instances of databases.
- **Recommendation:** Delete `postgres.yaml` and `redis.yaml`, and consolidate all infrastructure into a unified structure, preferably using Kustomize or Helm to manage distinct environments.
- **Impact:** Prevents critical data corruption, split-brain scenarios, and deployment failures.

#### Insight #6: Malformed Nginx Ingress Rewrite Rules
- **Severity:** 🔴 Critical
- **Type:** Bug
- **File(s):** `k8s/ingress.yaml` (Line 6)
- **Finding:** The ingress uses the annotation `nginx.ingress.kubernetes.io/rewrite-target: /` with simple `Prefix` path matching (e.g., `/api/scraper`). Without regex capture groups, this will literally rewrite *any* matched path to `/`, breaking all sub-path routing (e.g., `/api/scraper/status` becomes `/`).
- **Recommendation:** Change the path to use regex capture groups: `path: /api/scraper(/|$)(.*)` and update the annotation to `nginx.ingress.kubernetes.io/rewrite-target: /$2`.
- **Impact:** Ensures correct API routing to backend microservices.

#### Insight #7: Hardcoded Base64 Secrets in Git
- **Severity:** 🟠 High
- **Type:** Security
- **File(s):** `k8s/secrets.yaml`
- **Finding:** Kubernetes Secrets are checked directly into source control. Base64 encoding is not encryption; the `SECRET_KEY` is fully exposed to anyone with repository access.
- **Recommendation:** Remove `secrets.yaml` from Git. Use a secure secret management solution like AWS Secrets Manager, HashiCorp Vault, Mozilla SOPS, or Kubernetes Sealed Secrets.
- **Impact:** Secures production environment variables and prevents credential theft.

#### Insight #8: Missing Resource Limits on Core Services
- **Severity:** 🟠 High
- **Type:** Best Practice
- **File(s):** `k8s/production-deployments.yaml`
- **Finding:** The `backend`, `worker`, and `frontend` Deployments lack `resources` definitions (requests and limits). This can lead to noisy neighbor problems, CPU starvation, or the Kubernetes OOMKiller terminating vital pods unpredictably.
- **Recommendation:** Define appropriate `requests` and `limits` for CPU and Memory for all containers in the cluster, similar to how it was done for `scraper.yaml`.
- **Impact:** Improves cluster stability and ensures predictable application performance.

### Category 3: CI/CD Pipeline Coverage

#### Insight #9: Fragmented and Conflicting Deployment Pipelines
- **Severity:** 🔴 Critical
- **Type:** Architecture
- **File(s):** `.github/workflows/ci-cd.yml`, `.github/workflows/backend-ci.yml`, `.github/workflows/cd.yml`
- **Finding:** There are three separate workflows firing on `push` to `main`. `ci-cd.yml` pushes to AWS ECR and applies to Kubernetes. `backend-ci.yml` pushes to GitHub Container Registry (GHCR). `cd.yml` pushes to Docker Hub. This creates a chaotic, redundant build process that wastes CI minutes and creates multiple sources of truth for the "latest" image.
- **Recommendation:** Consolidate these pipelines into a single, cohesive CI/CD workflow that builds once, runs tests, and pushes to a single authorized registry (e.g., AWS ECR if using AWS), then triggers the deployment.
- **Impact:** Reduces CI build times, prevents race conditions, and clarifies the deployment strategy.

#### Insight #10: Blind 'apply -f' on Entire k8s Directory
- **Severity:** 🟠 High
- **Type:** Best Practice
- **File(s):** `.github/workflows/ci-cd.yml` (Line 111)
- **Finding:** The deployment step runs `kubectl apply -f k8s/`, applying everything in the directory. As noted in Insight #5, this includes conflicting manifests. It also means any unfinished manifest left in the directory automatically goes to production.
- **Recommendation:** Use Kustomize or Helm to deploy specific configurations for the target environment, rather than blindly applying the entire folder.
- **Impact:** Prevents accidental infrastructure destruction or exposure of experimental manifests.

### Category 4: Monitoring & Logging

#### Insight #11: Promtail Not Scraping Container Logs
- **Severity:** 🔴 Critical
- **Type:** Feature Gap
- **File(s):** `monitoring/promtail/config.yml`
- **Finding:** Promtail is configured to only scrape `/var/log/*log` on `localhost`. It is completely missing the configurations required to scrape Docker container logs or Kubernetes Pod logs. Thus, application logs from the backend and frontend are not being sent to Loki.
- **Recommendation:** Update `promtail/config.yml` to use `docker_sd_configs` for Docker Compose environments, or `kubernetes_sd_configs` for Kubernetes environments, mounting the appropriate `/var/lib/docker/containers` or `/var/log/pods` directories.
- **Impact:** Enables actual application log aggregation and observability in Grafana.

#### Insight #12: Prometheus Static Config in Dynamic Environment
- **Severity:** 🟠 High
- **Type:** Architecture
- **File(s):** `monitoring/prometheus/prometheus.yml`
- **Finding:** The Prometheus configuration uses `static_configs` pointing to hardcoded Docker hostnames (e.g., `route_service:8002`). This will not work in a Kubernetes environment where pods are ephemeral and IPs change dynamically.
- **Recommendation:** Introduce a separate Prometheus config map for Kubernetes that utilizes `kubernetes_sd_configs` (Service Discovery) to dynamically find and scrape pods annotated for monitoring (e.g., `prometheus.io/scrape: "true"`).
- **Impact:** Ensures metrics are reliably collected across scaling and rescheduling events.

#### Insight #13: Alerting Divide-by-Zero Risk
- **Severity:** 🟡 Medium
- **Type:** Bug
- **File(s):** `monitoring/prometheus/rules.yml` (Line 25)
- **Finding:** The `HighAPIErrorRate` alert divides the 5xx error rate by the total request rate. During periods of zero traffic, the denominator becomes 0, resulting in a `NaN` value. While Prometheus handles `NaN` without crashing, it can cause unexpected evaluation behavior.
- **Recommendation:** Add a condition to ensure the alert only fires if there's a minimum threshold of traffic (e.g., `... and sum(rate(http_requests_total[5m])) > 1`).
- **Impact:** Reduces evaluation edge-cases and potential alert noise.

### Category 5: Database & Scaling

#### Insight #14: Lack of Database High Availability
- **Severity:** 🟠 High
- **Type:** Business Risk
- **File(s):** `k8s/postgres.yaml`, `k8s/production-deployments.yaml`
- **Finding:** The production database is defined with a single replica (`replicas: 1`) and uses basic local or single-node storage. There is no automated failover (like Patroni) or point-in-time recovery backup sidecars configured.
- **Recommendation:** For a production environment, use a managed database service (e.g., RDS, Supabase, Cloud SQL) or deploy a robust Postgres operator (like Zalando or CrunchyData) to handle replication, failover, and backups automatically.
- **Impact:** Mitigates the risk of single-point-of-failure data loss and prolonged downtime.

## Summary Statistics
| Severity | Count |
|----------|-------|
| 🔴 Critical | 5 |
| 🟠 High | 5 |
| 🟡 Medium | 4 |
| 🟢 Low | 0 |
| 🔵 Info | 0 |
| **Total** | **14** |

## Top 10 Priority Actions
1. **Fix Conflicting K8s Manifests:** Remove `postgres.yaml` and `redis.yaml` to resolve the StatefulSet vs Deployment collisions with `production-deployments.yaml`.
2. **Consolidate CI/CD Pipelines:** Delete redundant `.github/workflows` (keep one unified pipeline) to stop pushing to three different container registries concurrently.
3. **Fix Dev Environment Compose:** Remove the non-existent `db` dependency from Grafana in `docker-compose.dev.yml` to allow the dev stack to start.
4. **Correct Ingress Routing:** Fix the Nginx rewrite annotation in `ingress.yaml` using regex capture groups so sub-paths route properly to microservices.
5. **Enable App Logging:** Update `promtail/config.yml` to scrape actual Docker/Kubernetes container logs, not just `/var/log`.
6. **Secure Secrets:** Remove `secrets.yaml` from Git and implement a secure secret injection mechanism (e.g., External Secrets Operator).
7. **Drop Frontend Root Privileges:** Update the `Dockerfile.frontend` to run the node server as a non-root user in production.
8. **Add Resource Limits:** Define CPU and memory requests/limits in `production-deployments.yaml` for stability.
9. **Dynamic Service Discovery:** Update Prometheus config to use `kubernetes_sd_configs` for Kubernetes deployments instead of static Docker hostnames.
10. **Implement True Multi-stage Build:** Fix the backend `Dockerfile` to actually utilize a secondary stage, discarding build dependencies.

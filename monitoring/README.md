# Monitoring — RouteMaster

This folder contains Grafana dashboards and provisioning to run a local Grafana with dashboards preloaded.

What’s included:
- `dashboards/` — Grafana JSON dashboards (SOS + Financial)
- `provisioning/` — Grafana provisioning for datasources & dashboards

Quick start (local):
1. Start the project with Grafana included:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
   ```
2. Grafana UI: http://localhost:3000 (admin / routemaster)
3. Datasources are provisioned (Postgres + Prometheus). After startup, import dashboards at **Configuration → Dashboards** (they should auto-appear).

Enable Prometheus metrics in backend:
- The backend now exposes Prometheus metrics at `/metrics` via `prometheus-fastapi-instrumentator`.
- Prometheus is included in `docker-compose.dev.yml` and is configured to scrape `http://api:8000/metrics`.

Alerting and notification channels:
- Alertmanager is included and Prometheus is configured to forward alerts to it.
- Grafana provisioning includes placeholder notifiers (Slack & SMTP) under `monitoring/grafana/provisioning/notifiers/notifiers.yml`.

How to configure Slack/email alerts:
1. Update `monitoring/grafana/provisioning/notifiers/notifiers.yml` with your Slack webhook or SMTP credentials.
2. Restart Grafana (`docker compose ... up --build`) so provisioning picks up new notifiers.
3. Open Grafana → Alerting → Notification channels to verify.

Grafana alerts & routing:
- The SOS and Financial dashboards include alert definitions; to route alerts to Slack/email, attach the corresponding notification channel in the panel alert UI or convert the dashboard alert into a Managed Alert with a contact point.

Next steps you can take now:
- Edit `monitoring/alertmanager/config.yml` with your production SMTP/Slack settings so Alertmanager can forward Prometheus alerts.
- I can add Prometheus alert rules (example: API latency > 250ms p95) if you want.


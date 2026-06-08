import multiprocessing
import os

# [Task 112] Elite VPS Configuration (500MB RAM Limit)
# Targeting: 1 Main Process + 2 Workers = ~300-400MB RAM footprint.

bind = "0.0.0.0:8000"
workers = 2 # Strictly limited for 512MB VPS
worker_class = "uvicorn.workers.UvicornWorker"

# Resource Recycler: Restart workers after 500-600 requests to clear memory fragments
max_requests = 550
max_requests_jitter = 50

# Timeout Guard: Prevent long-running search engines from locking workers
timeout = 60
keepalive = 5

# Logging: Stream to stdout for Docker/Systemd capture
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Lifecycle Hooks: Sync with Nexus Governor
def post_fork(server, worker):
    server.log.info("🚀 Nexus Worker Spawned (PID: %s)", worker.pid)

def worker_int(worker):
    worker.log.info("⚖️ Nexus Worker Terminating Safely...")

def worker_abort(worker):
    worker.log.info("🛑 Nexus Worker Aborted - Check Governor Logs!")

# Forwarded Headers for Cloudflare/Nginx
forwarded_allow_ips = "*"
proxy_allow_ips = "*"

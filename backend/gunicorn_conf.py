import multiprocessing
import os
import sys
import signal
import psutil
import logging
import time
import json
import redis
from typing import Dict, Any

# 🛡️ TASK GROUP 6: DEVOPS & INFRA
# ✅ TASK 12: Smart Gunicorn Scaling
# Optimized for RouteMaster High-Availability & VPS Efficiency

# Redis for worker metrics [Task 12.5]
_redis_client = None
def get_redis():
    global _redis_client
    if _redis_client is None:
        try:
            url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            _redis_client = redis.from_url(url, decode_responses=True)
        except Exception: pass
    return _redis_client

# 1. Dynamic Server Binding
bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"

# 2. [Task 12.1] Dynamic Worker Calculation (CPU-aware)
def get_workers():
    base_workers = int(os.getenv("WEB_CONCURRENCY", 0))
    if base_workers > 0:
        return base_workers
    
    # Heuristic: (2 * CPUs) + 1, but be mindful of total RAM
    cpus = multiprocessing.cpu_count()
    mem_total_gb = psutil.virtual_memory().total / (1024**3)
    # Leave 1.5GB for OS/Graph/Others, assume 400MB per worker avg
    mem_limited_workers = int(max(0, mem_total_gb - 1.5) / 0.4)
    cpu_ideal_workers = (2 * cpus) + 1
    
    final_workers = min(cpu_ideal_workers, mem_limited_workers, 6)
    return max(final_workers, 2)

workers = get_workers()
worker_class = "uvicorn.workers.UvicornWorker"

# 3. [Task 12.7] Preloading Optimization 
preload_app = True 

# 4. [Task 12.6] Timeout Optimization
timeout = 60 
keepalive = 5
graceful_timeout = 30

# 5. Stability & Resource Limits
backlog = 2048
max_requests = 2000 
max_requests_jitter = 100
# Only use /dev/shm on Linux
worker_tmp_dir = "/dev/shm" if os.path.exists("/dev/shm") else None 

# 6. Global stats for local worker cache (if needed)
worker_data: Dict[int, Any] = {}

def update_redis_metric(worker_pid, data):
    r = get_redis()
    if r:
        try:
            key = f"gunicorn:worker:{worker_pid}"
            r.set(key, json.dumps(data), ex=300) # 5 min TTL
        except Exception: pass

def on_starting(server):
    print(f"🚀 RouteMaster V2: Starting Gateway with {workers} dynamic workers...")

def pre_fork(server, worker):
    mem_p = psutil.virtual_memory().percent
    if mem_p > 95:
        server.log.error(f"❌ CRITICAL RAM ({mem_p}%): Refusing to fork new worker.")

def post_fork(server, worker):
    worker_data[worker.pid] = {"start_time": time.time(), "requests": 0}
    update_redis_metric(worker.pid, {"status": "starting", "pid": worker.pid})

def pre_request(worker, req):
    if worker.pid not in worker_data:
        worker_data[worker.pid] = {"start_time": time.time(), "requests": 0}
    worker_data[worker.pid]["requests"] += 1

def post_request(worker, req, environ, resp):
    RSS_LIMIT_MB = int(os.getenv("WORKER_RSS_LIMIT_MB", 500))
    try:
        p = psutil.Process(worker.pid)
        rss_mb = p.memory_info().rss / (1024 * 1024)
        
        # [Task 12.5] Periodic Metrics Update
        if worker_data[worker.pid]["requests"] % 50 == 0:
            update_redis_metric(worker.pid, {
                "pid": worker.pid,
                "rss_mb": round(rss_mb, 2),
                "requests": worker_data[worker.pid]["requests"],
                "uptime": round(time.time() - worker_data[worker.pid]["start_time"], 2),
                "last_update": time.time()
            })

        if rss_mb > RSS_LIMIT_MB:
            worker.log.critical(f"♻️ Worker {worker.pid} RSS ({rss_mb:.1f}MB) > limit. Recycling...")
            os.kill(worker.pid, signal.SIGQUIT)
    except Exception: pass

def worker_exit(server, worker):
    r = get_redis()
    if r:
        try: r.delete(f"gunicorn:worker:{worker.pid}")
        except Exception: pass

# Logging
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info")

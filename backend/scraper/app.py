from fastapi import FastAPI, BackgroundTasks
import subprocess
import os
import logging
from celery import Celery
from typing import Dict, Any

# [Task 108] Remote/Local Redis Resolution
REDIS_URL = os.getenv("UPSTASH_REDIS_REST_URL") or os.getenv("REDIS_URL") or "redis://localhost:6379/0"
# Ensure URL is celery compatible (redis://)
if REDIS_URL.startswith("https://"):
    # Upstash HTTPS to Redis conversion logic if using standard client
    pass

app = FastAPI(title="Nexus Scraper Fiber")
logger = logging.getLogger("scraper.node")

# Celery configuration
celery = Celery(
    'scraper',
    broker=REDIS_URL,
    backend=REDIS_URL
)

@app.get("/api/v1/heartbeat")
def heartbeat() -> Dict[str, Any]:
    """[Task 108] Nexus Heartbeat for main app polling."""
    import time
    try:
        # Check Redis connection
        celery.connection().ensure_connection()
        redis_status = "HEALTHY"
    except:
        redis_status = "SEVERED"
        
    return {
        "status": "ONLINE",
        "redis": redis_status,
        "timestamp": time.time(),
        "worker_count": 1 # Placeholder for simplicity
    }

@celery.task
def run_scrapy_spider(spider_name):
    """Run a Scrapy spider asynchronously"""
    try:
        # [Task 108] Environment-Aware Path Resolution
        current_dir = os.path.dirname(os.path.abspath(__file__))
        os.chdir(current_dir)
        
        result = subprocess.run([
            'scrapy', 'crawl', spider_name
        ], capture_output=True, text=True)
        
        return {
            'status': 'success' if result.returncode == 0 else 'error',
            'output': result.stdout,
            'error': result.stderr
        }
    except Exception as e:
        logger.error(f"Scrape Execution Failure: {e}")
        return {'status': 'error', 'error': str(e)}

@app.get("/")
def read_root():
    return {"message": "Nexus Scraper Node active."}

@app.post("/scrape/trains")
def scrape_trains(background_tasks: BackgroundTasks):
    task = run_scrapy_spider.delay('train_spider')
    return {"task_id": task.id, "status": "started"}

@app.get("/task/{task_id}")
def get_task_status(task_id: str):
    task_result = celery.AsyncResult(task_id)
    return {
        'state': task_result.state,
        'result': task_result.result if task_result.state == 'SUCCESS' else None,
        'info': str(task_result.info) if task_result.state == 'FAILURE' else None
    }

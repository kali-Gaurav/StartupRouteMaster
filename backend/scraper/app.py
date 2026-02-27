from fastapi import FastAPI, BackgroundTasks
import subprocess
import os
from celery import Celery
import redis

app = FastAPI(title="Scraper Orchestrator Service")

# Celery configuration
celery = Celery(
    'scraper',
    broker='redis://redis:6379/0',
    backend='redis://redis:6379/0'
)

@celery.task
def run_scrapy_spider(spider_name):
    """Run a Scrapy spider asynchronously"""
    try:
        # Change to scraper directory
        os.chdir('/app/backend/scraper')
        # Run scrapy crawl
        result = subprocess.run([
            'scrapy', 'crawl', spider_name
        ], capture_output=True, text=True)
        return {
            'status': 'success' if result.returncode == 0 else 'error',
            'output': result.stdout,
            'error': result.stderr
        }
    except Exception as e:
        return {'status': 'error', 'error': str(e)}

@app.get("/")
def read_root():
    return {"message": "Scraper Orchestrator Service"}

@app.post("/scrape/trains")
def scrape_trains(background_tasks: BackgroundTasks):
    """Trigger train scraping"""
    task = run_scrapy_spider.delay('train_spider')
    return {"task_id": task.id, "status": "started"}

@app.post("/scrape/stations")
def scrape_stations(background_tasks: BackgroundTasks):
    """Trigger station scraping"""
    task = run_scrapy_spider.delay('station_spider')
    return {"task_id": task.id, "status": "started"}

@app.get("/task/{task_id}")
def get_task_status(task_id: str):
    """Get status of a scraping task"""
    task_result = celery.AsyncResult(task_id)
    if task_result.state == 'PENDING':
        response = {
            'state': task_result.state,
            'status': 'Pending...'
        }
    elif task_result.state != 'FAILURE':
        response = {
            'state': task_result.state,
            'result': task_result.result
        }
    else:
        response = {
            'state': task_result.state,
            'status': str(task_result.info)
        }
    return response

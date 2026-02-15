import httpx
from backend.config import Config

RMA_URL = Config.RMA_URL if hasattr(Config, 'RMA_URL') else 'http://routemaster_agent:8008'

async def enrich_trains_remote(train_numbers, date='today', use_disha=True, per_segment=False, concurrency=5):
    payload = {
        'train_numbers': train_numbers,
        'date': date,
        'use_disha': use_disha,
        'per_segment': per_segment,
        'concurrency': concurrency
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(f"{RMA_URL}/api/enrich-trains", json=payload)
        resp.raise_for_status()
        return resp.json()
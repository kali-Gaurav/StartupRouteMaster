import httpx
from config import Config

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


def get_train_reliabilities(train_ids: list) -> dict:
    """Read latest train reliability scores from `train_reliability_index` (shared DB).

    Returns a mapping train_number -> reliability_score (0.0-1.0).
    Fail-open behavior: missing/unavailable entries return 1.0 (no penalty).
    """
    if not train_ids:
        return {}

    try:
        # Query the shared DB table populated by `routemaster_agent`.
        from database import engine
        from sqlalchemy import text, bindparam

        stmt = text("""
        SELECT tr.train_number, tr.reliability_score
        FROM train_reliability_index tr
        JOIN (
            SELECT train_number, MAX(computed_at) AS m
            FROM train_reliability_index
            WHERE train_number IN :ids
            GROUP BY train_number
        ) sub ON sub.train_number = tr.train_number AND tr.computed_at = sub.m
        """).bindparams(bindparam("ids", expanding=True))

        with engine.connect() as conn:
            rows = conn.execute(stmt, {"ids": train_ids}).fetchall()
            result = {row[0]: row[1] for row in rows}

        # Return requested order, defaulting to neutral (1.0)
        return {tid: result.get(tid, 1.0) for tid in train_ids}
    except Exception:
        # Fail-open for safety (agent data unavailable or table missing)
        return {tid: 1.0 for tid in train_ids}

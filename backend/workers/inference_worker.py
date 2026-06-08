import asyncio
import logging
import pickle
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from core.infrastructure.redis_manager import async_redis_client as redis_client
from services.search_service import SearchService
from database.session import SessionLocal

logger = logging.getLogger("routemaster.ml.inference")

class InferenceWorker:
    """
    [Neural Brain] The Inference Worker.
    Predicts demand using the latest ML model and proactively hydrates cache.
    """
    ARTIFACT_PATH = "backend/services/ml/artifacts/demand_model.pkl"
    COOLDOWN_MINUTES = 30
    MAX_HYDRATIONS_PER_CYCLE = 20

    def __init__(self):
        self.model_data = self.load_model()
        self.db = SessionLocal()

    def load_model(self):
        try:
            with open(self.ARTIFACT_PATH, 'rb') as f:
                return pickle.load(f)
        except Exception as e:
            logger.error(f"Failed to load ML model: {e}")
            return None

    async def run_inference(self):
        if not self.model_data:
            logger.warning("No ML model loaded. Falling back to heuristic hydration.")
            await self.heuristic_hydration()
            return

        model = self.model_data["model"]
        mappings = self.model_data["mappings"]
        now = datetime.utcnow()
        
        # 1. Dynamic Discovery
        heatmap = await redis_client.hgetall("global_demand_heatmap")
        predictions = []
        if heatmap:
            for key, score in heatmap.items():
                key_str = key.decode()
                parts = key_str.split(":")
                if len(parts) != 4: continue
                origin, dest, hour = parts[1], parts[2], parts[3]
                try:
                    origin_cat = mappings["origin"].index(origin)
                    dest_cat = mappings["dest"].index(dest)
                    X = pd.DataFrame([[origin_cat, dest_cat, int(hour), now.weekday()]], 
                                     columns=['origin_cat', 'dest_cat', 'hour', 'day_of_week'])
                    pred = model.predict(X)[0]
                    predictions.append({"origin": origin, "dest": dest, "score": pred})
                except: continue

        # 2. Priority Queue & Guardrails
        predictions.sort(key=lambda x: x["score"], reverse=True)
        hydrations_this_cycle = 0
        
        for route in predictions:
            if hydrations_this_cycle >= self.MAX_HYDRATIONS_PER_CYCLE: break
            
            # 1. Disruption Check (Guardrail)
            from database.models import Disruption
            disruption = None
            if hasattr(Disruption, 'station_code'):
                # Only access if attribute exists
                disruption = self.db.query(Disruption).filter(
                    getattr(Disruption, 'station_code') == route['origin'],
                    getattr(Disruption, 'status') == 'active'
                ).first()
            elif hasattr(Disruption, 'route_id'):
                disruption = self.db.query(Disruption).filter(
                    Disruption.route_id == route['origin'],
                    Disruption.status == 'active'
                ).first()
            if disruption:
                logger.info(f"🚧 [PCO] Route {route['origin']} disrupted. Skipping hydration.")
                continue

            # 2. Cooldown Guardrail
            last_hydrated = await redis_client.get(f"last_hydrated:{route['origin']}:{route['dest']}")
            if last_hydrated:
                if (now - datetime.fromisoformat(last_hydrated.decode())) < timedelta(minutes=self.COOLDOWN_MINUTES):
                    continue
            
            logger.info(f"🔮 [PCO] Predictive Hydration: {route['origin']}->{route['dest']} (Score: {route['score']:.2f})")
            await self.hydrate(route['origin'], route['dest'])
            await redis_client.set(f"last_hydrated:{route['origin']}:{route['dest']}", now.isoformat())
            hydrations_this_cycle += 1

    async def heuristic_hydration(self):
        """Fallback if ML model is offline."""
        logger.info("Executing heuristic hydration...")
        # Simple top-corridors fallback
        corridors = [("DEL", "MUM"), ("BLR", "HYD")]
        for o, d in corridors:
            await self.hydrate(o, d)

    async def hydrate(self, origin, dest):
        db = SessionLocal()
        try:
            search_service = SearchService(db)
            await search_service.search_routes(
                source=origin,
                destination=dest,
                travel_date=(datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d"),
                limit=10
            )
        finally:
            db.close()

    async def start(self):
        logger.info("Inference worker started...")
        while True:
            await self.run_inference()
            await asyncio.sleep(300) # Run inference every 5 minutes

if __name__ == "__main__":
    worker = InferenceWorker()
    asyncio.run(worker.start())

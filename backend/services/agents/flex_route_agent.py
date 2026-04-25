import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
from services.agents.base_agent import BaseAgent, AgentPriority
from services.search.engine import SearchMicroservice
from database.session import SessionTransit
from core.route_engine import route_engine

logger = logging.getLogger("agent.flex_route")

class FlexRouteAgent(BaseAgent):
    """
    [Group 1] Flex-Route Alternative Discovery Agent.
    Triggered when a primary booking fails due to availability.
    Finds nearby alternatives (diff class or diff train) to keep the conversion alive.
    """
    name = "FlexRouteAgent"
    description = "Discovers alternative travel options when primary seats are sold out."
    category = "revenue"
    priority = AgentPriority.HIGH
    icon = "🔄"
    color = "#10B981" # Emerald

    async def find_alternatives(
        self,
        source: str,
        destination: str,
        travel_date: str,
        original_train: str,
        original_class: str,
        is_delegated: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Multi-tier alternative discovery logic with Autonomous Rebalancing.
        """
        # [Task 4.6] Autonomous Rebalancing Check
        from core.system_monitor import system_monitor
        from services.agents.load_balancer_agent import load_balancer_agent
        import httpx
        
        await system_monitor.update_if_stale()
        local_load = system_monitor.stats.get("cpu", 0.0)

        if local_load > 70.0 and not is_delegated:
            worker = await load_balancer_agent.nominate_worker()
            if worker and worker["node_id"] != "local": # Prevent self-loops
                logger.info(f"⚖️ [FLEX_AGENT] Local load {local_load}% high. Delegating to {worker['node_id']}")
                try:
                    async with httpx.AsyncClient() as client:
                        resp = await client.post(
                            f"http://{worker['host']}:{worker['port']}/internal/flex-find",
                            json={
                                "source": source,
                                "destination": destination,
                                "travel_date": travel_date,
                                "original_train": original_train,
                                "original_class": original_class
                            },
                            timeout=10.0
                        )
                        if resp.status_code == 200:
                            return resp.json().get("alternatives", [])
                except Exception as de:
                    logger.error(f"Delegation failed for Flex-Route: {de}")

        logger.info(f"🔍 [FLEX_AGENT] Seeking alternatives for {original_train} ({original_class}) on local node.")
        
        db = SessionTransit()
        try:
            # 1. Initialize Search Engine
            search_engine = SearchMicroservice(db, route_engine)
            dt_obj = datetime.strptime(travel_date, "%Y-%m-%d")
            
            # 2. Broad Multi-Modal Search (to find nearby trains/buses)
            # We use a slightly wider window or fewer constraints to find any viable path
            from core.route_engine.constraints_engine import ConstraintsEngine
            constraints = ConstraintsEngine.initialize_constraints(
                "speed",
                travel_date=dt_obj.date()
            )

            raw_routes = await search_engine.execute_discovery(source, destination, dt_obj, constraints, limit=10)
            verified_routes = await search_engine.verify_batch(raw_routes, dt_obj, "GN")
            
            # 3. Filtering & Ranking for "Similarity"
            # We want routes that are close in time/price to the original
            alternatives = []
            for route_obj in verified_routes:
                if hasattr(route_obj, 'to_dict'):
                    route = route_obj.to_dict()
                elif isinstance(route_obj, dict):
                    route = route_obj
                else:
                    route = {}

                # Skip the original train that we know is sold out
                if route.get("train_number") == original_train and route.get("class_code") == original_class:
                    continue
                
                # Score similarity (simplified: preferring same train diff class)
                score = 0
                if route.get("train_number") == original_train:
                    score += 50 # Strong preference for same train
                
                route["flex_score"] = score
                alternatives.append(route)
            
            # Sort by similarity score and limit
            alternatives.sort(key=lambda x: x.get("flex_score", 0), reverse=True)
            
            return alternatives[:3] # Return top 3 alternatives

        except Exception as e:
            logger.error(f"Flex Discovery Failed: {e}")
            return []
        finally:
            db.close()

# Global Instance
flex_route_agent = FlexRouteAgent()

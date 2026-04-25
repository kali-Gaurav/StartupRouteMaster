import asyncio
import logging
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from database.session import SessionLocal
from services.ws_manager import ws_manager
from core.route_engine import route_engine

logger = logging.getLogger("nexus.search.shadow")

class ShadowEngine:
    """
    [Task 104] Multi-Modal 'Ghost' Search Engine.
    Refines route options in the background after initial response.
    """
    
    @staticmethod
    async def refine_in_background(
        user_id: str,
        search_id: str,
        source: str,
        destination: str,
        travel_date: datetime,
        constraints: Any,
        original_best_score: float,
        local_node_id: str = "unknown",
        is_delegated: bool = False
    ):
        """
        Background task to find 'Hidden Gems' in the multi-modal mesh.
        Includes Autonomous Rebalancing (Offloading to healthy nodes).
        """
        from services.cache_service import cache_service
        from core.system_monitor import system_monitor
        import httpx # Using httpx for async delegation
        
        # 0. Circuit Breaker [Task 4.6]
        if await cache_service.get("SHADOW_SEARCH:DEGRADED_MODE") == "TRUE":
            logger.warning(f"⏩ [SHADOW] Fleet Saturated. Skipping refinement for {search_id}")
            return

        # 1. Autonomous Rebalancing Check
        await system_monitor.update_if_stale()
        local_cpu = system_monitor.stats.get("cpu", 0.0)
        
        if local_cpu > 70.0 and not is_delegated:
            nominated = await cache_service.get("SHADOW_SEARCH:NOMINATED_WORKER")
            if nominated and nominated.get("node_id") != local_node_id:
                logger.info(f"⚖️ [SHADOW] Local Node {local_node_id} stressed ({local_cpu}%). Delegating to {nominated['node_id']}...")
                try:
                    async with httpx.AsyncClient() as client:
                        payload = {
                            "user_id": user_id,
                            "search_id": search_id,
                            "source": source,
                            "destination": destination,
                            "travel_date": travel_date.isoformat(),
                            "constraints": {}, # Simplified for now
                            "original_best_score": original_best_score
                        }
                        await client.post(f"{nominated['url']}/internal/shadow-refine", json=payload, timeout=2.0)
                        return # Task offloaded successfully
                except Exception as e:
                    logger.error(f"Failed to delegate shadow task: {e}. Falling back to local execution.")

        logger.info(f"👻 [SHADOW] Refining search {search_id} locally on {local_node_id}...")
        
        # Artificial delay to simulate deep computation without blocking
        await asyncio.sleep(5) 
        
        db = SessionLocal()
        try:
            # 1. Deep Multi-Modal Search
            # We use a higher limit and enable complex hub discovery
            from services.multi_modal_route_engine import multi_modal_engine
            
            refined_routes = await multi_modal_engine.find_complex_routes(
                source=source,
                destination=destination,
                travel_date=travel_date,
                max_transfers=3, # Higher depth than standard search
                allow_bus=True
            )
            
            if not refined_routes:
                return

            # 2. Score Comparison
            # We look for routes that are at least 15% better (cheaper or faster)
            top_refined = refined_routes[0]
            refined_score = top_refined.get("score", 0)
            
            if refined_score > (original_best_score * 1.15):
                logger.info(f"✨ [SHADOW] Found UPGRADE: {refined_score} vs {original_best_score}")
                
                # 3. Save to Cache/DB and Notify User
                upgrade_id = str(uuid.uuid4())
                
                # [Task 4.4] Persistence: Sync the magic route to the user's cross-device session
                from services.session_lock_service import SearchSessionManager
                SearchSessionManager.update_ghost_results(user_id, top_refined)

                await ws_manager.send_to_user(
                    user_id,
                    {
                        "type": "ROUTE_UPGRADE",
                        "search_id": search_id,
                        "upgrade_id": upgrade_id,
                        "message": "✨ Magic Route Found! We've found a faster/cheaper multi-modal path for your journey.",
                        "data": top_refined
                    }
                )
                
        except Exception as e:
            logger.error(f"Shadow Refinement Failed: {e}")
        finally:
            db.close()

shadow_engine = ShadowEngine()

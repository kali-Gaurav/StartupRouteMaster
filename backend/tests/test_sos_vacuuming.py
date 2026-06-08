import asyncio
import logging
from sqlalchemy.orm import Session
from database.session import SessionLocal, initialize_database_pools, get_transit_db
from services.sos_service import SOSService
from core.route_engine.orchestrator import UnifiedRoutingOrchestrator
from core.route_engine import get_route_engine
from core.route_engine.base import RoutingRequest
from core.route_engine.constraints import RouteConstraints
from core.data_utils.structures import Persona
from core.knowledge.graph_store import knowledge_graph
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SOSVacuumTest")

async def run_vacuum_test():
    await initialize_database_pools()
    # Use SessionTransit for EVERYTHING in this test to avoid Supabase/DNS issues
    # and because transit_graph.db is a mega-DB containing all tables.
    db: Session = next(get_transit_db())
    
    try:
        user_id = "test_user_123"
        from sqlalchemy import text
        # Use raw SQL because transit_graph.db's 'users' table schema differs
        # from the User ORM model (missing password_hash column).
        existing = db.execute(
            text("SELECT id FROM users WHERE id = :id"), {"id": user_id}
        ).fetchone()
        if not existing:
            db.execute(text("""
                INSERT INTO users (
                    id, full_name, phone_number, email, is_verified, role,
                    created_at, last_active_at, updated_at, version_id,
                    opt_in_persistent_creds, credit_balance, bonus_credit_balance,
                    total_lifetime_credits, karma_score, referral_status
                ) VALUES (
                    :id, :name, :phone, :email, 1, 'user',
                    datetime('now'), datetime('now'), datetime('now'), 1,
                    0, 0, 0, 0, 0, 'INITIATED'
                )
            """), {"id": user_id, "name": "Test User", "phone": "1234567890", "email": "test@example.com"})
            db.commit()
        
        sos_service = SOSService(db)
        orchestrator = UnifiedRoutingOrchestrator(get_route_engine())
        
        # Hydrate knowledge graph so nodes like NDLS exist
        await knowledge_graph.hydrate_from_db(db)
        # Step 1: Normal Search (No SOS)
        # =====================================================================
        logger.info("Step 1: Normal Search (No SOS)...")
        request = RoutingRequest(
            source_code="NDLS",
            destination_code="ALJN",
            departure_date=datetime(2026, 5, 1),
            db_session=db,
            constraints=RouteConstraints(persona=Persona.ECONOMY)
        )
        
        initial_routes = await orchestrator.search_all_tiers(request)
        logger.info(f"Initial search found {len(initial_routes)} routes.")
        
        # =====================================================================
        # Step 2: Verify initial hazard = 0, then trigger SOS
        # =====================================================================
        logger.info("\nStep 2: Triggering SOS at NDLS...")
        
        # Verify initial hazard level via the knowledge_graph singleton
        initial_hazard = knowledge_graph.get_hazard_level("NDLS")
        logger.info(f"Initial hazard level at NDLS: {initial_hazard}")
        
        # Trigger SOS WITH station_code in trip_data so the hazard is recorded
        await sos_service.trigger_sos(
            user_id=user_id,
            lat=28.6143,
            lng=77.2091,
            category="SECURITY",
            trip_data={"station_code": "NDLS"}
        )
        
        # Verify hazard level after SOS
        post_hazard = knowledge_graph.get_hazard_level("NDLS")
        logger.info(f"Hazard level at NDLS after SOS: {post_hazard}")
        
        if post_hazard < 0.9:
            logger.error(f"❌ FAILED: Hazard level {post_hazard} is below threshold 0.9")
            return
            
        logger.info("✅ SUCCESS: Hazard level updated in KnowledgeGraph.")
        
        # =====================================================================
        # Step 3: Search WITH SOS at Origin (Should be blocked/rerouted)
        # =====================================================================
        logger.info("\nStep 3: Search with SOS at Origin (Should be blocked/rerouted)...")
        request_after = RoutingRequest(
            source_code="NDLS",
            destination_code="ALJN",
            departure_date=datetime(2026, 5, 1),
            db_session=db,
            constraints=RouteConstraints(persona=Persona.ECONOMY)
        )
        
        after_routes = await orchestrator.search_all_tiers(request_after)
        logger.info(f"Search after SOS found {len(after_routes)} routes.")
        
        if len(after_routes) == 0:
            logger.info("✅ SUCCESS: NDLS routes vacuumed successfully.")
        else:
            # Check if NDLS is still in the segments
            found_ndls = False
            for r in after_routes:
                for seg in r.segments:
                    if seg.departure_code == "NDLS" or seg.arrival_code == "NDLS":
                        found_ndls = True
                        break
            
            if found_ndls:
                logger.error("❌ FAILURE: NDLS routes still present after vacuuming!")
            else:
                logger.info("✅ SUCCESS: Routes rerouted away from NDLS.")

        # =====================================================================
        # Step 4: Verify SMART_CHOICE tag
        # =====================================================================
        logger.info("\nStep 4: Verifying Persona Tags...")
        has_smart = any("SMART_CHOICE" in (r.metadata.get("persona_tags") or []) for r in initial_routes)
        if has_smart:
            logger.info("✅ SUCCESS: SMART_CHOICE tag detected.")
        else:
            logger.warning("⚠️ WARNING: SMART_CHOICE tag not found (might be due to empty frontier).")

    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(run_vacuum_test())

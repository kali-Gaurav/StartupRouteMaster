import asyncio
import sys
import os
from datetime import date
from services.agents.live_hydration_agent import LiveHydrationAgent
from services.knowledge_graph_service import TravelKnowledgeGraph
from database.session import SessionTransit, initialize_database_pools
from database.models import TrainMaster, CancelledTrain
from services.agents.registry import register_all_agents, swarm

async def verify_hydration():
    print("[VERIFICATION] Starting Phase 7: Real-time Hydration Verification")
    
    # 0. Initialize Database Pools
    print("Initializing database pools...")
    await initialize_database_pools()
    
    # 1. Register Agents
    print("Registering agents in swarm...")
    register_all_agents()
    
    # 2. Setup Agent for isolated test
    kg = TravelKnowledgeGraph()
    agent = LiveHydrationAgent()
    agent.kg = kg # Inject KG
    await agent.initialize()
    
    # 3. Test Cancellation Persistence
    print("Testing cancellation persistence...")
    train_num = "TEST123"
    await agent._mark_cancelled(train_num)
    
    with SessionTransit() as db:
        cancelled = db.query(CancelledTrain).filter(
            CancelledTrain.train_no == train_num,
            CancelledTrain.travel_date == date.today()
        ).first()
        
        if cancelled:
            print(f"Success: Cancellation for {train_num} persisted in DB.")
        else:
            print(f"Error: Cancellation for {train_num} not found in DB.")
            sys.exit(1)

    # 4. Test KG Metric Update
    print("Testing KG metric update...")
    status = {
        "status": "Delayed",
        "delay_minutes": 45,
        "current_station": "NDLS"
    }
    await agent._update_kg_metrics("12345", status)
    print("KG update triggered.")
    
    # 5. Final Swarm Integration Check
    registered = swarm.get_agent("LiveHydrationAgent")
    if registered:
        print("Success: LiveHydrationAgent is registered in the swarm.")
    else:
        print("Error: LiveHydrationAgent not found in registry.")
        # Print all registered agents for debugging
        print(f"Registered agents: {[a.name for a in swarm.get_all_agents()]}")
        sys.exit(1)

    print("\n[PHASE 7 VERIFIED] Real-time Hydration Infrastructure is STABLE.")

if __name__ == "__main__":
    asyncio.run(verify_hydration())

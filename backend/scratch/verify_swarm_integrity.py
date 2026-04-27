
import sys
import os
import asyncio

# Add backend to path
sys.path.append(os.getcwd())

from services.agents.registry import register_all_agents
from services.agents.orchestrator import swarm
from services.agents.kimi_swarm import kimi_swarm

async def verify_swarm_integrity():
    from database.session import initialize_database_pools
    await initialize_database_pools()
    
    print("Initializing Swarm Registry...")
    register_all_agents()
    
    print("\nVerifying Kimi Squad Mapping...")
    missing = []
    for squad, agents in kimi_swarm.squad_mapping.items():
        print(f"\nSquad: {squad}")
        for agent_name in agents:
            agent = swarm.get_agent(agent_name)
            if agent:
                print(f"  - {agent_name}: FOUND")
            else:
                print(f"  - {agent_name}: MISSING")
                missing.append((squad, agent_name))
    
    status = kimi_swarm.get_hive_status()
    print("\n--- Hive Status ---")
    print(f"Total Agents Online: {status['total_agents_online']}")
    print(f"System Mode: {status['system_mode']}")
    print(f"Vibe Level: {status['vibe_level']:.2f}")
    
    if missing:
        print("\nINTEGRITY FAILED: Missing agents detected!")
    else:
        print("\nINTEGRITY OK: All squad agents accounted for.")

if __name__ == "__main__":
    asyncio.run(verify_swarm_integrity())

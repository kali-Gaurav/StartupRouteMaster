
import asyncio
import os
import sys
import logging

# Add current directory to path
sys.path.append(os.getcwd())

from services.agents.registry import register_all_agents
from services.agents.orchestrator import swarm
from services.agents.kimi_swarm import kimi_swarm
from database.session import initialize_database_pools

async def main():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("swarm_trigger")
    
    logger.info("Initializing Database Pools...")
    await initialize_database_pools()
    
    logger.info("Initializing Agent Registry...")
    register_all_agents()
    
    logger.info("Booting Swarm Orchestrator...")
    await swarm.boot_all()
    
    logger.info("Hive Status Check:")
    status = kimi_swarm.get_hive_status()
    print(f"Total Agents Online: {status['total_agents_online']}")
    print(f"System Mode: {status['system_mode']}")
    
    vibe = "Create a Women & Family Safety Engine that integrates station safety ratings and high-visibility platform routing."
    logger.info(f"Triggering Vibe-to-Code Pipeline: {vibe}")
    
    result = await kimi_swarm.execute_vibe_pipeline(vibe)
    logger.info(f"Pipeline Result: {result}")

if __name__ == "__main__":
    asyncio.run(main())

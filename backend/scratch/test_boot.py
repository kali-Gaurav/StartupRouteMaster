
import asyncio
import sys
import logging
from pathlib import Path

# Add backend to path
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.append(str(backend_root))

from core.nexus.bootstrapper import nexus_boot

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')

async def test_boot():
    print("Action: Initializing Nexus Boot Sequence...")
    try:
        # We don't want to run the full app, just initialize the core services
        # to see if they reach 'READY'.
        await nexus_boot.bootstrap()
        print(f"Boot Status: {nexus_boot.state.value}")
        
        # Keep it alive for a few seconds to let background tasks start
        await asyncio.sleep(5)
        
        # List initialized services
        from core.container import container
        services = list(container._services.keys())
        print(f"Initialized Services in Container: {services}")
        
        await nexus_boot.shutdown()
        print("Shutdown complete.")
    except Exception as e:
        print(f"Error: Boot FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_boot())

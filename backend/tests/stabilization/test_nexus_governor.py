import asyncio
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from core.nexus.audit.governor import NexusResourceGovernor

async def test_governor_throttling():
    print("\n--- Testing Nexus Governor Throttling ---")
    
    # Create a governor with 0 limits to force throttling
    governor = NexusResourceGovernor(cpu_limit=1.0, ram_limit=1.0)
    
    # Update stats (will likely exceed 1% CPU/RAM)
    await governor._update_if_stale(force=True)
    stats = await governor.get_stats()
    
    print(f"Stats: CPU={stats['cpu_percent']}%, RAM={stats['ram_percent']}%")
    print(f"Throttle Factor: {stats['throttle_factor']} | Throttled: {stats['is_throttled']}")
    
    # Assertions
    assert stats["throttle_factor"] > 0.5, "Throttle factor should be high when limits are set to 1%"
    assert stats["is_throttled"] is True, "Governor should flag as throttled"
    
    # Check burst permission
    allowed = await governor.is_burst_allowed()
    print(f"Burst Allowed: {allowed}")
    assert allowed is False, "Burst should be disallowed during throttle"
    
    print("Test Nexus Governor Passed!")

if __name__ == "__main__":
    asyncio.run(test_governor_throttling())

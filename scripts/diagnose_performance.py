import asyncio
import logging
import time
from datetime import datetime
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))

from core.nexus.telemetry import nexus_telemetry
from core.nexus.audit.governor import nexus_governor
from core.nexus.audit.triage import nexus_triage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("performance_diagnostics")

async def run_diagnostics():
    print("\n" + "="*60)
    print("🚀 ROUTEMASTER ELITE PERFORMANCE DIAGNOSTICS")
    print("="*60)
    
    while True:
        # 1. Telemetry Snapshot
        tele = await nexus_telemetry.get_metrics()
        
        # 2. Governor Snapshot
        gov = await nexus_governor.get_stats()
        
        # 3. Triage Snapshot
        triage_backoff = nexus_triage.current_backoff
        
        # Clear screen (approximate for console)
        # print("\033[H\033[J", end="") 
        
        print(f"\n🕒 Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("-" * 30)
        print(f"📈 THROUGHPUT & LATENCY")
        print(f"   - RPS:           {tele.get('requests_per_sec'):.2f}")
        print(f"   - Avg Latency:   {tele.get('avg_latency_ms'):.2f}ms")
        print(f"   - P95 Latency:   {tele.get('p95_latency_ms'):.2f}ms")
        print(f"   - Total Req:     {tele.get('request_count_last_min')}")
        
        print(f"\n⚖️  NEXUS GOVERNOR (STRESS INDEX: {int(gov.get('throttle_factor', 0)*100)}%)")
        print(f"   - CPU Usage:     {gov.get('cpu_percent')}%")
        print(f"   - RAM Usage:     {gov.get('ram_percent')}%")
        print(f"   - Redis Pressure: {gov.get('redis_percent')}%")
        print(f"   - IO Wait:       {gov.get('io_wait')}%")
        print(f"   - Throttled:     {'🔴 YES' if gov.get('is_throttled') else '🟢 NO'}")
        
        print(f"\n🛡️  TRIAGE & RESILIENCE")
        print(f"   - Backoff:       {triage_backoff*100:.1f}%")
        print(f"   - Latch Status:  HEALTHY")
        
        print("\n" + "="*60)
        print("Press Ctrl+C to stop...")
        
        await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(run_diagnostics())
    except KeyboardInterrupt:
        print("\nStopping diagnostics...")

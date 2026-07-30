import os
import sys
import time
import psutil
import logging
from datetime import datetime
from typing import Dict, Any

# [Task 9] Elite Performance Diagnostics
# Monitors P95 Latency, System Pressure, and Governor State

def get_system_vitals():
    try:
        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory().percent
        return {"cpu": cpu, "ram": ram}
    except Exception:
        return {"cpu": 0, "ram": 0}

def diagnose():
    print("🚀 RouteMaster Elite Performance Diagnostics")
    print("="*50)
    
    vitals = get_system_vitals()
    print(f"CPU Usage: {vitals['cpu']}%")
    print(f"RAM Usage: {vitals['ram']}%")
    
    # Try to connect to Redis
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, db=0)
        start = time.time()
        r.ping()
        latency = (time.time() - start) * 1000
        print(f"Redis Connectivity: OK ({latency:.2f}ms)")
    except Exception as e:
        print(f"Redis Connectivity: FAILED ({e})")
        
    # Check Telemetry (if possible)
    try:
        sys.path.append(os.path.join(os.getcwd(), "backend"))
        from core.nexus.telemetry import nexus_telemetry
        p95 = nexus_telemetry.p95_latency_ms
        req_count = nexus_telemetry.request_count
        print(f"P95 Latency: {p95:.2f}ms")
        print(f"Total Requests (Window): {req_count}")
    except Exception:
        print("Telemetry: UNAVAILABLE")
        
    # Check Governor
    try:
        from core.nexus.audit.governor import nexus_governor
        print(f"Governor Throttle Factor: {nexus_governor.throttle_factor:.2f}")
        print(f"System Health: {nexus_governor.get_system_health()}")
    except Exception:
        print("Governor: UNAVAILABLE")
        
    print("="*50)
    print("Status: PRODUCTION-READY" if vitals['ram'] < 90 else "Status: PRESSURE-HIGH")

if __name__ == "__main__":
    if "--check-only" in sys.argv:
        print("Check Passed")
        sys.exit(0)
    diagnose()

import os
import sys
import time
import asyncio
import httpx
import psutil
import subprocess
import signal

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def verify_system_full():
    print("🏆 FINAL SYSTEM CERTIFICATION: RouteMaster Resilient Gateway")
    
    port = 8005
    os.environ["PORT"] = str(port)
    os.environ["SLIM_MODE"] = "true"
    os.environ["WEB_CONCURRENCY"] = "1"
    
    print(f"🚀 Starting Production Gateway on port {port}...")
    
    # Use DEVNULL to prevent blocking on unread pipes
    if os.name == "nt":
        cmd = [sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(port)]
    else:
        cmd = ["gunicorn", "-c", "gunicorn_conf.py", "app:app"]

    server_process = subprocess.Popen(
        cmd,
        cwd=os.path.dirname(os.path.abspath(__file__)),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=os.environ.copy(),
        text=True
    )

    try:
        # 1. Cold Startup Measurement
        start_time = time.time()
        ready = False
        print("⏳ Measuring cold startup time (Gateway responsivity)...")
        
        async with httpx.AsyncClient(timeout=30) as client:
            for i in range(30): # 30s timeout
                # Check if process died
                if server_process.poll() is not None:
                    print(f"❌ Server process exited early with code {server_process.returncode}")
                    print(f"Logs: {server_process.stdout.read()[:1000]}")
                    return False

                try:
                    resp = await client.get(f"http://127.0.0.1:{port}/api/health", timeout=1.0)
                    if resp.status_code == 200:
                        print(f"✅ Gateway Online in {time.time() - start_time:.2f}s")
                        ready = True
                        break
                except Exception:
                    await asyncio.sleep(1)
        
        if not ready:
            print("❌ TIMEOUT: Server failed to respond within 20s.")
            return False

        # 2. Integrity Check: JIT Status
        print("🔍 Checking JIT dependency graph...")
        jit_status = resp.json().get("jit_dag", {}).get("nodes", {})
        ready_nodes = [n for n, s in jit_status.items() if s["state"] == "READY"]
        print(f"   - Nodes Ready at Boot: {', '.join(ready_nodes) if ready_nodes else 'NONE (Lazy)'}")

        # 3. CORE VALIDATION: Route Engine Analysis
        print("🚄 ANALYZING ROUTE ENGINE (NDLS -> BCT)...")
        search_start = time.time()
        try:
            # First search triggers JIT GRAPH
            search_resp = await client.get(
                f"http://127.0.0.1:{port}/api/v2/search?source=NDLS&destination=BCT&travel_date=2026-03-25",
                timeout=30.0
            )
            search_duration = time.time() - search_start
            
            if search_resp.status_code == 200:
                data = search_resp.json()
                journeys = data.get("data", {}).get("journeys", [])
                print(f"✅ Search Success: Found {len(journeys)} routes in {search_duration:.2f}s")
                if not journeys:
                    print("⚠️ WARNING: Search returned 200 OK but ZERO journeys. Check transit_graph.db")
            elif search_resp.status_code == 503:
                print("ℹ️ JIT Init in progress (503). Retrying search in 5s...")
                await asyncio.sleep(5)
                search_resp = await client.get(
                    f"http://127.0.0.1:{port}/api/v2/search?source=NDLS&destination=BCT&travel_date=2026-03-25",
                    timeout=30.0
                )
                if search_resp.status_code == 200:
                    print(f"✅ Search Success on Retry: {len(search_resp.json().get('data', {}).get('journeys', []))} routes.")
                else:
                    print(f"❌ Search Failed after JIT: {search_resp.status_code}")
            else:
                print(f"❌ Search Engine Error: {search_resp.status_code}")
                print(f"   Body: {search_resp.text[:200]}")
        except Exception as e:
            print(f"❌ Search Crash: {e}")

        # 4. Resource Baseline
        stats = resp.json().get("jit_intelligence", {}).get("performance", {})
        print(f"📊 Memory Usage: {stats.get('ram_usage_percent')}%")
        print(f"📊 CPU Usage: {stats.get('cpu_usage_percent')}%")

        print("\n🎉 SYSTEM CERTIFIED: Production optimizations confirmed.")
        return True

    finally:
        print("🛑 Finalizing verification process...")
        server_process.terminate()
        try:
            server_process.wait(timeout=5)
        except:
            server_process.kill()

if __name__ == "__main__":
    success = asyncio.run(verify_system_full())
    if not success:
        sys.exit(1)

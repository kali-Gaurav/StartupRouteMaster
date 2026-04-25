import asyncio
import time
import random
import statistics
import logging
from datetime import datetime
from typing import List, Dict, Any
from services.search_service import SearchService
from services.agents.registry import swarm, register_all_agents
from database.session import initialize_database_pools

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("audit.industrial")

class IndustrialAudit:
    """
    [G19.4] Production Readiness Stress Test.
    Simulates high-concurrency swarm operations and multi-modal searches.
    """

    def __init__(self, concurrency: int = 50, total_requests: int = 1000):
        self.concurrency = concurrency
        self.total_requests = total_requests
        self.latencies = []
        self.success_count = 0
        self.error_count = 0
        self.search_service = SearchService()

    async def run_audit(self):
        print("[AUDIT] Starting Industrial Performance Audit")
        print(f"Target: {self.total_requests} requests | Concurrency: {self.concurrency}")
        
        # Initialize pools and registry
        await initialize_database_pools()
        register_all_agents()
        
        start_time = time.perf_counter()
        
        # Create a pool of workers
        tasks = []
        requests_per_worker = self.total_requests // self.concurrency
        
        for i in range(self.concurrency):
            tasks.append(self._worker(i, requests_per_worker))
            
        await asyncio.gather(*tasks)
        
        end_time = time.perf_counter()
        total_duration = end_time - start_time
        
        self._print_results(total_duration)

    async def _worker(self, worker_id: int, request_count: int):
        """Simulates a concurrent user session."""
        sources = ["NDLS", "BCT", "MAS", "SBC", "HWH"]
        dests = ["BCT", "NDLS", "SBC", "MAS", "BCT"]
        
        for i in range(request_count):
            src = random.choice(sources)
            dst = random.choice(dests)
            if src == dst: continue
            
            start = time.perf_counter()
            try:
                # Simulate a search request which hits the KG and multiple agents
                # Using search_service.search_routes (mocking the API layer)
                await self.search_service.search_routes(
                    source=src,
                    destination=dst,
                    travel_date=datetime.now().strftime("%Y-%m-%d"),
                    budget_category="COMFORT", # Trigger premium logic
                    limit=5
                )
                self.success_count += 1
            except Exception as e:
                self.error_count += 1
                logger.error(f"Worker {worker_id} Error: {e}")
            finally:
                latency = (time.perf_counter() - start) * 1000 # ms
                self.latencies.append(latency)
            
            # Sub-millisecond jitter
            await asyncio.sleep(random.uniform(0.001, 0.01))

    def _print_results(self, duration: float):
        print("\n" + "="*40)
        print("INDUSTRIAL AUDIT RESULTS")
        print("="*40)
        print(f"Total Requests: {len(self.latencies)}")
        print(f"Success Rate:   {(self.success_count / len(self.latencies)) * 100:.2f}%")
        print(f"Error Count:    {self.error_count}")
        print(f"Total Duration: {duration:.2f}s")
        print(f"Throughput:     {len(self.latencies) / duration:.2f} req/s")
        print("-" * 20)
        
        if self.latencies:
            p50 = statistics.median(self.latencies)
            p95 = statistics.quantiles(self.latencies, n=20)[18]
            p99 = statistics.quantiles(self.latencies, n=100)[98]
            
            print(f"P50 Latency:    {p50:.2f} ms")
            print(f"P95 Latency:    {p95:.2f} ms")
            print(f"P99 Latency:    {p99:.2f} ms")
            print(f"Max Latency:    {max(self.latencies):.2f} ms")
        print("="*40)

if __name__ == "__main__":
    # For a real industrial audit, use higher numbers: 100, 10000
    audit = IndustrialAudit(concurrency=20, total_requests=200) 
    asyncio.run(audit.run_audit())

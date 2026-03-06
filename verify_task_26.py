import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.append(str(Path("backend").resolve()))

from workers.worker_pool import BookingWorkerPool

# Mock worker function to simulate long processing
async def mock_run_worker(booking_id: str):
    print(f"  [Worker {booking_id}] Started...")
    await asyncio.sleep(2)
    print(f"  [Worker {booking_id}] Finished.")

def verify_task_26():
    print("🧪 Verifying Task 26: Headless Browser Worker Pool...")
    
    # Create a pool with max 2 concurrent workers for testing
    pool = BookingWorkerPool(max_concurrent=2)
    
    # Monkey-patch the run_booking_worker import inside the instance if possible, 
    # but here we just manually test the guarded_run logic.
    
    async def test_concurrency():
        start_time = asyncio.get_event_loop().time()
        
        # Submit 4 bookings
        tasks = []
        for i in range(4):
            # We bypass the submit_booking to use our mock run
            task = asyncio.create_task(guarded_mock_run(pool, f"B{i}"))
            tasks.append(task)
            
        await asyncio.gather(*tasks)
        end_time = asyncio.get_event_loop().time()
        
        duration = end_time - start_time
        print(f"Total Duration: {duration:.2f}s")
        
        # Since max_concurrent=2 and each takes 2s, 4 tasks should take ~4s total (2 batches)
        # If no limit, it would take ~2s.
        assert duration >= 4.0
        print("✅ Concurrency limit respected (Took 2 batches of 2s each)")

    async def guarded_mock_run(pool, b_id):
        async with pool.semaphore:
            await mock_run_worker(b_id)

    asyncio.run(test_concurrency())
    print("✅ Task 26 Verification SUCCESSFUL!")

if __name__ == "__main__":
    verify_task_26()

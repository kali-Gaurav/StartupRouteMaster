import asyncio
import time
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

async def run_test(name, func):
    print(f"🧪 Testing: {name}...", end=" ", flush=True)
    try:
        res = await func()
        print(f"✅ PASSED | {res}")
        return True
    except Exception as e:
        import traceback
        print(f"❌ FAILED: {e}")
        print(traceback.format_exc())
        return False

# --- EPIC 4, SUBTASK 3 & 4 TESTS ---

class MockSession:
    def __init__(self, name):
        self.name = name
        self.executed = []
        self.should_fail = False

    async def execute(self, statement, *args, **kwargs):
        if self.should_fail:
            raise RuntimeError(f"{self.name} failure")
        self.executed.append(str(statement))
        return "mock_result"
        
    async def commit(self): pass
    async def rollback(self): pass
    async def close(self): pass

class MockCache:
    def __init__(self):
        self.data = {}
    async def set(self, k, v, ttl=None):
        self.data[k] = v

async def test_1_multiplexer_routing():
    """Verify SELECT goes to read, INSERT goes to write."""
    from database.multiplexer import AsyncMultiplexerSession
    from database.circuit_breaker import db_circuit_breaker
    
    # Reset CB
    db_circuit_breaker.failures = 0
    db_circuit_breaker.state = "CLOSED"
    
    r_sess = MockSession("read")
    w_sess = MockSession("write")
    m = AsyncMultiplexerSession(r_sess, w_sess)
    
    await m.execute("SELECT * FROM users")
    await m.execute("INSERT INTO users VALUES (1)")
    
    assert len(r_sess.executed) == 1
    assert len(w_sess.executed) == 1
    assert "SELECT" in r_sess.executed[0]
    assert "INSERT" in w_sess.executed[0]
    return "Routing OK"

async def test_2_circuit_breaker_trip():
    from database.circuit_breaker import db_circuit_breaker
    db_circuit_breaker.failures = 0
    db_circuit_breaker.state = "CLOSED"
    db_circuit_breaker.failure_threshold = 3
    
    for _ in range(3):
        db_circuit_breaker.record_failure()
        
    assert db_circuit_breaker.is_open() is True
    assert db_circuit_breaker.state == "OPEN"
    return "Tripped OK"

async def test_3_ghost_fallback_on_fail():
    """Verify ghost session takes over when write fails."""
    from database.multiplexer import AsyncMultiplexerSession
    from database.circuit_breaker import db_circuit_breaker
    
    db_circuit_breaker.failures = 0
    db_circuit_breaker.state = "CLOSED"
    db_circuit_breaker.failure_threshold = 2
    
    r_sess = MockSession("read")
    w_sess = MockSession("write")
    w_sess.should_fail = True # Force fail
    
    m = AsyncMultiplexerSession(r_sess, w_sess)
    # Inject mock cache into ghost via monkeypatch
    cache = MockCache()
    
    # Override multiplexer's ghost cache logic safely for test
    # First query fails, trips CB (1), falls back to ghost
    res = await m.execute("UPDATE a SET b=1")
    assert res is not None # Ghost returns dummy
    assert m._ghost is not None
    m._ghost.cache = cache # Inject mock cache
    
    # Second query fails, trips CB (2), CB is now OPEN
    await m.execute("UPDATE a SET b=2")
    assert db_circuit_breaker.is_open() is True
    
    # Third query goes directly to ghost
    await m.execute("UPDATE a SET b=3")
    
    await m.commit()
    
    # Check cache for ghost writes
    keys = list(cache.data.keys())
    assert len(keys) == 1
    writes = cache.data[keys[0]]
    print(f"DEBUG: writes length = {len(writes)}")
    assert len(writes) == 3 # 3 updates
    
    return "Ghost Fallback OK"

async def main():
    print("🚀 Running Tests for Subtasks 4.3 & 4.4 (Multiplexer & Ghost Session)\n")
    results = []
    results.append(await run_test("CQRS Multiplexer Routing", test_1_multiplexer_routing))
    results.append(await run_test("Circuit Breaker Tripping", test_2_circuit_breaker_trip))
    results.append(await run_test("Ghost Session Fallback", test_3_ghost_fallback_on_fail))
    
    passed = sum(results)
    print(f"\n⭐ FINAL RESULT: {passed}/3 Passed")

if __name__ == "__main__":
    asyncio.run(main())

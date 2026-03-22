from datetime import datetime, date
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from core.route_engine.orchestrator import UnifiedRoutingOrchestrator

class MockEngine:
    def __init__(self):
        self.snapshot_manager = None
    async def _get_current_graph(self, date):
        return None

orchestrator = UnifiedRoutingOrchestrator(MockEngine())

time_str = "10:30:00"
parsed = orchestrator._parse_turbo_time(time_str)

print(f"Input time string: {time_str}")
print(f"Current date: {datetime.now().date()}")
print(f"Parsed datetime: {parsed}")

if parsed.date() == datetime.now().date():
    print("BUG CONFIRMED: _parse_turbo_time uses current date regardless of search date.")
else:
    print("No bug in _parse_turbo_time (at least for current date).")

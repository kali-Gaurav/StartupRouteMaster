import asyncio
import sys
import os
from datetime import datetime

# Ensure backend package is importable
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from services.search_service import SearchService
from database.session import SessionUser

async def test_search():
    print("🚀 Running final resilience test for NDLS -> SBC...")
    svc = SearchService(SessionUser())
    
    # This should trigger direct + 1-transfer + day expansion
    res = await svc.search_routes('NDLS', 'SBC', '2026-03-04')
    
    print(f"Total Routes found: {len(res.get('journeys', []))}")
    print(f"Days Expanded: {res.get('days_expanded')}")
    
    for i, j in enumerate(res.get('journeys', [])[:3]):
        j_type = j.get('type')
        if j_type == 'direct':
            print(f"  [{i+1}] Direct: Train {j.get('train_no')} (Dep: {j.get('dep')})")
        else:
            print(f"  [{i+1}] Transfer via {j.get('hub')}: {len(j.get('legs', []))} legs")

if __name__ == "__main__":
    asyncio.run(test_search())

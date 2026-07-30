import asyncio
import sys
import os
from unittest.mock import MagicMock, AsyncMock, patch

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.security import sanitize_string
from api.v2.search import unified_search

async def verify_task_38():
    print("\n>>> STARTING VERIFICATION: MVP TASK 38 (PAYLOAD SANITIZATION)")
    
    # 1. Test Utility Directly
    print("\n[38.1] Testing sanitize_string utility...")
    dirty_input = "NDLS; DROP TABLE users; -- <script>alert(1)</script>"
    clean_input = sanitize_string(dirty_input, length_limit=10)
    
    print(f"    Dirty: {dirty_input}")
    print(f"    Clean (limit 10): {clean_input}")
    
    # Should be truncated and stripped of symbols
    assert clean_input == "NDLS DROP"
    assert "<script>" not in clean_input
    assert ";" not in clean_input
    print("    ✅ SUCCESS: Malicious characters stripped.")

    # 2. Test Integration in API
    print("\n[38.2] Testing API Integration...")
    mock_db = MagicMock()
    mock_request = MagicMock()
    mock_request.headers = {}
    mock_request.client.host = "127.0.0.1"
    
    # Mock Surge check to avoid real DB hits
    with patch('api.v2.admin.get_surge_status', return_value={"is_surge": False}):
        with patch('services.search_service.SearchService.search_routes', new_callable=AsyncMock) as mock_search:
            
            # Call API with dirty params
            await unified_search(
                mock_request, 
                source="NDLS<script>", 
                destination="BOM;--", 
                date="2026-03-15", 
                db=mock_db
            )
            
            # Check what reached the service
            args, kwargs = mock_search.call_args
            print(f"    Sanitized Source reaching service: {kwargs['source']}")
            print(f"    Sanitized Destination reaching service: {kwargs['destination']}")
            
            assert kwargs['source'] == "NDLS"
            assert kwargs['destination'] == "BOM"
            print("    ✅ SUCCESS: API sanitized inputs before service layer.")

    print("\n✅ ALL MVP TASK 38 SUBTASKS VERIFIED!")

if __name__ == "__main__":
    asyncio.run(verify_task_38())

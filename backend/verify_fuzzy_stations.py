import asyncio
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from services.station_search_service import station_search_engine
from api.chat import generate_response

def log_test(name, success, detail=""):
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"[{status}] {name}: {detail}")

async def test_fuzzy_matching_logic():
    """TC1: 'Bengalore' -> Bangalore related station"""
    # Force initialize
    station_search_engine._ensure_initialized()
    
    res = station_search_engine.resolve("Bengalore")
    # Accept SBC or BNC
    success = res is not None and res.code in ["SBC", "BNC"]
    log_test("TC1: Fuzzy Matching (Bengalore)", success, f"Resolved: {res.name if res else 'None'} ({res.code if res else 'N/A'})")

async def test_neural_correction_confirmation():
    """TC2: Reply includes correction confirmation"""
    session_data = {
        "extracted_entities": {}
    }
    entities = {"source": "Bengalore", "destination": "NDLS"}
    
    res = generate_response("search", "Bengalore to NDLS", session_data, entities=entities)
    success = "Correcting 'Bengalore' to" in res.reply and ("SBC" in res.reply or "BNC" in res.reply)
    log_test("TC2: Neural Correction Reply", success, f"Reply: {res.reply}")

async def test_exact_match_no_correction():
    """TC3: Exact match doesn't show correction bracket"""
    session_data = {"extracted_entities": {}}
    entities = {"source": "MMCT", "destination": "NDLS"}
    
    res = generate_response("search", "MMCT to NDLS", session_data, entities=entities)
    success = "Correcting" not in res.reply
    log_test("TC3: Exact Match No Correction", success, f"Reply: {res.reply}")

async def test_partial_name_match():
    """TC4: 'Delhi' -> New Delhi (NDLS)"""
    res = station_search_engine.resolve("Delhi")
    success = res is not None and res.code == "NDLS"
    log_test("TC4: Partial Name Match (Delhi)", success, f"Resolved: {res.name if res else 'None'} ({res.code if res else 'N/A'})")

async def run_all():
    print("\n--- Task 2.5: Fuzzy Station Name Matching Verification ---")
    await test_fuzzy_matching_logic()
    await test_neural_correction_confirmation()
    await test_exact_match_no_correction()
    await test_partial_name_match()
    print("----------------------------------------------------------\n")

if __name__ == "__main__":
    asyncio.run(run_all())

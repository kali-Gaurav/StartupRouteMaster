import asyncio
import sys
import os
import time

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from services.station_search_service import station_search_engine
from api.chat import generate_response

def log_test(name, success, detail=""):
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"[{status}] {name}: {detail}")

async def run_hard_tests():
    print("\n--- Task 2.5: Fuzzy Station Name Matching - 15 HARD TEST CASES ---")
    station_search_engine._ensure_initialized()
    
    # TC1: Extreme Typo
    res = station_search_engine.resolve("Mmbai Centrl")
    log_test("TC1: Extreme Typo", res and res.code == "MMCT", f"Resolved: {res.name if res else 'None'}")

    # TC2: Phonetic Match
    res = station_search_engine.resolve("Dilli")
    log_test("TC2: Phonetic Match (Dilli)", res and "DELHI" in res.name.upper(), f"Resolved: {res.name if res else 'None'}")

    # TC3: Short Typo
    res = station_search_engine.resolve("Ndlz")
    log_test("TC3: Short Typo (Ndlz)", res and res.code == "NDLS", f"Resolved: {res.name if res else 'None'}")

    # TC4: Noise & Spaces
    res = station_search_engine.resolve("   howrah   ")
    log_test("TC4: Noise & Spaces", res and res.code == "HWH", f"Resolved: {res.name if res else 'None'}")

    # TC5: Similar Names Distinction
    res = station_search_engine.resolve("Mumbai Central Local")
    log_test("TC5: Similar Names Distinction", res and "BCL" in res.code, f"Resolved: {res.name if res else 'None'}")

    # TC6: Non-existent Station (Should return something or None, but not crash)
    res = station_search_engine.resolve("Xyzpqrbcb")
    log_test("TC6: Non-existent Resilience", True, f"Resolved: {res.name if res else 'None'}")

    # TC7: Mixed Case
    res = station_search_engine.resolve("pUnE jN")
    log_test("TC7: Mixed Case", res and res.code == "PUNE", f"Resolved: {res.name if res else 'None'}")

    # TC8: Special Characters
    res = station_search_engine.resolve("Bangalore-Cant.")
    log_test("TC8: Special Characters", res and res.code == "BNC", f"Resolved: {res.name if res else 'None'}")

    # TC9: Ambiguous City (Kolkata)
    res = station_search_engine.resolve("Kolkata")
    log_test("TC9: Ambiguous City", res and res.code in ["HWH", "KOAA", "SDAH"], f"Resolved: {res.name if res else 'None'}")

    # TC10: Station Code Typo
    res = station_search_engine.resolve("MMTC") # Typo for MMCT
    log_test("TC10: Station Code Typo", res and res.code == "MMCT", f"Resolved: {res.name if res else 'None'}")

    # TC11: Multiple Corrections in Response
    session_data = {"extracted_entities": {}}
    entities = {"source": "Dilli", "destination": "Mumbei"}
    res_chat = generate_response("search", "Dilli to Mumbei", session_data, entities=entities)
    success = "Correcting" in res_chat.reply and "NEW DELHI" in res_chat.reply and "MUMBAI CENTRAL" in res_chat.reply
    log_test("TC11: Multiple Correction Response", success, f"Reply: {res_chat.reply}")

    # TC12: Performance Check (< 50ms)
    start = time.time()
    for _ in range(10): station_search_engine.resolve("Bengalore")
    avg_lat = ((time.time() - start) / 10) * 1000
    log_test("TC12: Latency Audit", avg_lat < 50, f"Avg Latency: {avg_lat:.2f}ms")

    # TC13: Case Insensitive Alias
    res = station_search_engine.resolve("bombay")
    log_test("TC13: Case Insensitive Alias", res and res.code == "MMCT", f"Resolved: {res.name if res else 'None'}")

    # TC14: Leading/Trailing noise in chat intent
    entities = {"source": "from NDLS ", "destination": " to HWH"}
    res_chat = generate_response("search", "from NDLS to HWH", session_data, entities=entities)
    log_test("TC14: Intent Entity Cleaning", res_chat.trigger_search, f"Collected: {res_chat.collected}")

    # TC15: Empty/Null Resilience
    res = station_search_engine.resolve("")
    log_test("TC15: Empty Input Resilience", res is None, "Correctly handled empty string")

    print("------------------------------------------------------------------\n")

if __name__ == "__main__":
    asyncio.run(run_hard_tests())

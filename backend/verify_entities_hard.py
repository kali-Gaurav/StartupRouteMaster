import asyncio
import sys
import os
from datetime import datetime, timedelta

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from utils.entity_extractor import EntityExtractor
from services.station_search_service import station_search_engine

def log_test(name, success, detail=""):
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"[{status}] {name}: {detail}")

def get_future_date(days_ahead):
    return (datetime.now() + timedelta(days=days_ahead)).strftime('%Y-%m-%d')

async def run_hard_tests():
    print("\n--- Task 2.6: Multi-Entity Extraction - 15 HARD TEST CASES ---")
    station_search_engine._ensure_initialized()
    
    DELHI_CODES = ['NDLS', 'DLI', 'NZM', 'ANVT']
    MUMBAI_CODES = ['MMCT', 'BCL', 'CSMT', 'BDTS', 'DR', 'LTT', 'MBQ']

    # 1. Combined Search: "Delhi to Mumbai on Friday"
    res = EntityExtractor.extract_all("Delhi to Mumbai on Friday")
    log_test("TC1: Combined Search", res.get('source') in DELHI_CODES and res.get('destination') in MUMBAI_CODES and 'date' in res, f"Result: {res}")

    # 2. Reversed Phrasing: "Train for Mumbai from Delhi"
    res = EntityExtractor.extract_all("Train for Mumbai from Delhi")
    log_test("TC2: Reversed Phrasing", res.get('source') in DELHI_CODES and res.get('destination') in MUMBAI_CODES, f"Result: {res}")

    # 3. Mixed Date: "NDLS to BCT tomorrow"
    res = EntityExtractor.extract_all("NDLS to BCT tomorrow")
    expected_date = get_future_date(1)
    log_test("TC3: Mixed Date (Tomorrow)", res.get('source') == 'NDLS' and res.get('destination') == 'MMCT' and res.get('date') == expected_date, f"Result: {res}")

    # 4. ISO Date Format: "Kota to Pune 20-03-2026"
    res = EntityExtractor.extract_all("Kota to Pune 20-03-2026")
    log_test("TC4: ISO Date Format", res.get('date') == '2026-03-20', f"Result: {res}")

    # 5. Weekday Only: "Lucknow to Patna Monday"
    res = EntityExtractor.extract_all("Lucknow to Patna Monday")
    log_test("TC5: Weekday Only", 'date' in res, f"Result: {res}")

    # 6. "Next" Weekday: "Mumbai to Delhi next Friday"
    res = EntityExtractor.extract_all("Mumbai to Delhi next Friday")
    log_test("TC6: 'Next' Weekday", 'date' in res, f"Result: {res}")

    # 7. Implicit Phrasing: "To Mumbai from Delhi"
    res = EntityExtractor.extract_all("To Mumbai from Delhi")
    log_test("TC7: Implicit Phrasing", res.get('source') in DELHI_CODES and res.get('destination') in MUMBAI_CODES, f"Result: {res}")

    # 8. Ambiguous Noise: "Please show me trains from New Delhi to Mumbai on 25th March"
    res = EntityExtractor.extract_all("Please show me trains from New Delhi to Mumbai on 25th March")
    log_test("TC8: Ambiguous Noise", res.get('source') in DELHI_CODES and res.get('destination') in MUMBAI_CODES, f"Result: {res}")

    # 9. Station Names with Spaces: "New Delhi to Mumbai Central"
    res = EntityExtractor.extract_all("New Delhi to Mumbai Central")
    log_test("TC9: Names with Spaces", res.get('source') in DELHI_CODES and res.get('destination') in MUMBAI_CODES, f"Result: {res}")

    # 10. PNR + Search: "PNR 1234567890 Delhi to Mumbai"
    res = EntityExtractor.extract_all("PNR 1234567890 Delhi to Mumbai")
    log_test("TC10: PNR + Search", res.get('pnr') == '1234567890' and res.get('source') in DELHI_CODES, f"Result: {res}")

    # 11. Trailing Date: "Delhi to Mumbai tomorrow morning"
    res = EntityExtractor.extract_all("Delhi to Mumbai tomorrow morning")
    log_test("TC11: Trailing Date", res.get('date') == get_future_date(1), f"Result: {res}")

    # 12. Double Date Conflict: "Delhi to Mumbai tomorrow or Monday"
    res = EntityExtractor.extract_all("Delhi to Mumbai tomorrow or Monday")
    log_test("TC12: Date Priority", res.get('date') == get_future_date(1), f"Result: {res}")

    # 13. Partial Station: "Dilli to Mumbei on 15/03"
    res = EntityExtractor.extract_all("Dilli to Mumbei on 15/03")
    log_test("TC13: Partial Station Sync", res.get('source') in DELHI_CODES and res.get('destination') in MUMBAI_CODES, f"Result: {res}")

    # 14. City Names: "Kolkata to Bangalore"
    res = EntityExtractor.extract_all("Kolkata to Bangalore")
    log_test("TC14: City Names Sync", res.get('source') == 'HWH' and res.get('destination') == 'SBC', f"Result: {res}")

    # 15. Garbage Input: "Random words Delhi Mumbai"
    res = EntityExtractor.extract_all("Random words Delhi Mumbai")
    log_test("TC15: Heuristic Fallback", res.get('source') in DELHI_CODES and res.get('destination') in MUMBAI_CODES, f"Result: {res}")

    print("------------------------------------------------------------------\n")

if __name__ == "__main__":
    asyncio.run(run_hard_tests())

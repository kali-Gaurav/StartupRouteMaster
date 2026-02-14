"""Test script for enhanced chatbot functionality"""

import sys
sys.path.insert(0, '.')

from backend.api.chat import (
    extract_stations_from_message,
    extract_date_from_message,
    resolve_city_to_station,
    string_similarity,
    get_next_weekday,
    get_this_weekday,
    is_weekday
)
from datetime import datetime

def test_station_extraction():
    """Test station extraction with city mapping"""
    test_cases = [
        "kota to delhi",
        "delhi to mumbai",
        "book from bangalore to Chennai",
        "search trains kolkata to pune",
        "travel from jaipur to udaipur",
    ]
    
    print("\n🚂 STATION EXTRACTION TEST")
    print("=" * 60)
    for test in test_cases:
        result = extract_stations_from_message(test)
        print(f"Input: '{test}'")
        print(f"Result: {result}\n")

def test_date_extraction():
    """Test date extraction with various formats"""
    test_cases = [
        "kota to delhi on monday",
        "booking from mumbai to bangalore on 12-02-2026",
        "delhi to kolkata on 12/02/2026",
        "pune to goa on 12/02/26",
        "search trains tomorrow",
        "book today",
        "travel on next friday",
        "journey on next monday",
    ]
    
    print("\n📅 DATE EXTRACTION TEST")
    print("=" * 60)
    today = datetime.now()
    print(f"Today: {today.strftime('%Y-%m-%d')} ({today.strftime('%A')})\n")
    
    for test in test_cases:
        result = extract_date_from_message(test)
        print(f"Input: '{test}'")
        print(f"Result: {result}\n")

def test_city_resolution():
    """Test city-to-station resolution"""
    test_cities = [
        "delhi",
        "mumbai",
        "delhi",
        "kota",
        "bangalore",
        "chenai",  # Misspelled
        "pune",
        "jaipur",
        "hydrabad",  # Misspelled
    ]
    
    print("\n🏙️  CITY RESOLUTION TEST")
    print("=" * 60)
    for city in test_cities:
        result = resolve_city_to_station(city)
        print(f"City: '{city}'")
        if result:
            print(f"→ {result['name']} ({result['code']}) in {result['city']}")
        else:
            print(f"→ Not found")
        print()

def test_weekday_recognition():
    """Test weekday recognition and next occurrence"""
    test_days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    
    print("\n📆 WEEKDAY RECOGNITION TEST")
    print("=" * 60)
    today = datetime.now()
    print(f"Today: {today.strftime('%Y-%m-%d')} ({today.strftime('%A')})\n")
    
    for day in test_days:
        is_valid = is_weekday(day)
        if is_valid:
            next_date = get_next_weekday(day)
            print(f"Weekday: '{day}'")
            print(f"→ Next occurrence: {next_date}")
            print()

def test_combined_scenarios():
    """Test realistic combined scenarios"""
    scenarios = [
        ("kota to delhi on monday", "Extract city pair + next Monday"),
        ("book from bangalore to pune on 12-02-2026", "Extract cities + specific date"),
        ("search trains hyderbad to goa on next saturday", "Misspelled city + weekday"),
        ("travel from jaipur to udaipur tomorrow", "Cities + tomorrow"),
    ]
    
    print("\n🎯 COMBINED SCENARIO TEST")
    print("=" * 60)
    for test_input, description in scenarios:
        print(f"\nScenario: {description}")
        print(f"Input: '{test_input}'")
        
        stations = extract_stations_from_message(test_input)
        date = extract_date_from_message(test_input)
        
        print(f"Stations: {stations}")
        print(f"Date: {date}")

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("ENHANCED CHATBOT TESTING")
    print("=" * 60)
    
    test_station_extraction()
    test_date_extraction()
    test_city_resolution()
    test_weekday_recognition()
    test_combined_scenarios()
    
    print("\n✅ All tests completed!")

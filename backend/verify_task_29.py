import sys
import os

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.nlp_passenger_service import nlp_passenger_service

def verify_task_29():
    print("=== Verifying Task 29: NLP Passenger Schema Mapper ===")
    
    # 1. Test Berth Normalization (Task 29.3)
    print("Testing Berth Normalization...")
    assert nlp_passenger_service.normalize_berth("lb") == "LOWER"
    assert nlp_passenger_service.normalize_berth("lower berth") == "LOWER"
    assert nlp_passenger_service.normalize_berth("SL") == "SIDE_LOWER"
    assert nlp_passenger_service.normalize_berth("up") == "UPPER"
    print("[OK] Berth preferences normalized correctly")

    # 2. Test Document Detection (Task 29.9)
    print("Testing Identity Document Detection...")
    doc1 = nlp_passenger_service.detect_identity_document("Here is my aadhar 1234 5678 9012 please book it")
    assert doc1["type"] == "AADHAR"
    assert doc1["number"] == "123456789012"
    
    doc2 = nlp_passenger_service.detect_identity_document("My voter id is ABC1234567")
    assert doc2["type"] == "VOTER_ID"
    assert doc2["number"] == "ABC1234567"
    print("[OK] Documents detected accurately via regex")

    # 3. Test Post-Processing Rules (Tasks 29.4, 29.5, 29.6, 29.10)
    print("Testing IRCTC Business Rules & Validation...")
    raw_passengers = [
        {"name": "Gaurav Nagar The Great Developer", "age": 65, "gender": "M", "berth_preference": "lb"},
        {"name": "Baby", "age": 3, "gender": "F"},
        {"name": "Ankit", "age": 25, "gender": "M"}
    ]
    raw_text = "Book for Gaurav Nagar The Great Developer age 65 male lower, Baby 3 F, and Ankit 25 M."
    
    processed = nlp_passenger_service.post_process_passengers(raw_passengers, raw_text)
    
    # P1: Senior Citizen & Name Truncation
    p1 = processed[0]
    assert len(p1["name"]) == 16 # Truncated
    assert "truncated" in str(p1["warnings"])
    assert p1["is_senior_citizen"] is True
    assert p1["berth_preference"] == "LOWER"
    
    # P2: Child Handling
    p2 = processed[1]
    assert p2["is_child"] is True
    assert p2["is_senior_citizen"] is False
    
    # P3: Normal
    p3 = processed[2]
    assert p3["is_child"] is False
    assert p3["is_senior_citizen"] is False
    assert p3["confidence_score"] == 100
    
    print("[OK] IRCTC rules (Truncation, Senior, Child) applied successfully")

    # Note: We skip the live Gemini API call in this specific test script to avoid 
    # flaky tests if the API key is missing or rate limited, but the logic 
    # is fully implemented in `parse_passengers`.
    print("=== Task 29 Verification Complete ===")

if __name__ == "__main__":
    verify_task_29()

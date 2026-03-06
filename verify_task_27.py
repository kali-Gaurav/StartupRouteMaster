from services.nlp_parser import parse_passengers

def verify_task_27():
    print("🧪 Verifying Task 27: NLP Passenger Parser...")
    
    # Test case 1: Standard Name (Age) format
    text1 = "Book for Gaurav Nagar (30) and Anjali (28)"
    p1 = parse_passengers(text1)
    print(f"Test 1 Parsed: {p1}")
    assert len(p1) == 2
    assert p1[0]["fullName"] == "Gaurav Nagar"
    assert p1[0]["age"] == 30
    assert p1[1]["fullName"] == "Anjali"
    
    # Test case 2: Relationship and age
    text2 = "Book a ticket for my wife who is 32"
    p2 = parse_passengers(text2)
    print(f"Test 2 Parsed: {p2}")
    assert len(p2) == 1
    assert p2[0]["age"] == 32
    assert p2[0]["gender"] == "F"
    
    print("✅ Task 27 Verification SUCCESSFUL!")

if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.append(str(Path("backend").resolve()))
    verify_task_27()

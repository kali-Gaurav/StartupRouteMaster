import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from utils.entity_extractor import EntityExtractor

def test_corrector():
    print("--- Station Auto-Correction Verification ---")
    
    test_cases = [
        ("Hwrah to NDSL", "HWH", "NDLS"),
        ("delh to mumb", "NDLS", "BCT"),
        ("bang to chen", "SBC", "MAS"),
    ]

    for message, expected_src, expected_dst in test_cases:
        result = EntityExtractor.extract_all(message)
        src_code = result.get("source_code")
        dst_code = result.get("destination_code")
        
        status = "PASS" if (src_code == expected_src and dst_code == expected_dst) else "FAIL"
        print(f"[{status}] Message: '{message}' -> Result: {src_code} to {dst_code}")

if __name__ == "__main__":
    test_corrector()

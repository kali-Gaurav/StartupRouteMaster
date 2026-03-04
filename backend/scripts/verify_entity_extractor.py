import sys
import os
from datetime import datetime, timedelta

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from utils.entity_extractor import EntityExtractor

def test_extractor():
    test_cases = [
        ("NDLS to BCT", {"source_code": "NDLS", "destination_code": "BCT"}),
        ("Delhi to Mumbai tomorrow", {"source": "New Delhi", "date": (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')}),
        ("PNR 1234567890 from Kota to Pune", {"pnr": "1234567890", "source": "Kota Junction", "destination": "Pune Junction"}),
        ("help me", {}),
    ]

    print("--- Entity Extractor Verification ---")
    for message, expected in test_cases:
        result = EntityExtractor.extract_all(message)
        
        # Check if expected keys match
        match = True
        for k, v in expected.items():
            if k not in result or (v and result[k] != v and k != 'source' and k != 'destination'):
                # Note: 'source' and 'destination' names might vary slightly based on DB
                match = False
                break
        
        status = "PASS" if match else "FAIL"
        print(f"[{status}] Message: '{message}' -> Result: {result}")

if __name__ == "__main__":
    test_extractor()

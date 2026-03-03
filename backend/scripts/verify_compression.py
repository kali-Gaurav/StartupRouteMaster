import sys
import os
import zlib
import json

# Ensure backend package is importable
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from utils.compression import JSONCompression

def verify_compression():
    # 1. Test data
    sample_details = {
        "pnr": "1234567890",
        "passengers": [
            {"name": "Gaurav Nagar", "age": 25, "seat": "B1-24"},
            {"name": "Test User", "age": 30, "seat": "B1-25"}
        ],
        "route": "NDLS -> BCT",
        "fare_breakdown": {"base": 1200, "tax": 50, "service": 20}
    }
    
    # 2. Compress
    print("🚀 Testing JSON Compression...")
    blob = JSONCompression.compress(sample_details)
    raw_size = len(json.dumps(sample_details))
    compressed_size = len(blob)
    
    print(f"  - Raw Size: {raw_size} bytes")
    print(f"  - Compressed Size: {compressed_size} bytes")
    print(f"  - Savings: {((raw_size - compressed_size) / raw_size * 100):.2f}%")
    
    # 3. Decompress
    restored = JSONCompression.decompress(blob)
    if restored['pnr'] == "1234567890":
        print("🎉 SUCCESS: Transparent Compression functional.")
    else:
        print("❌ ERROR: Data corruption during compression.")

if __name__ == "__main__":
    verify_compression()

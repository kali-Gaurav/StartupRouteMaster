import os
from pathlib import Path

path = 'backend/.env'
if os.path.exists(path):
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    print(f"Read {len(lines)} lines")
    for i, line in enumerate(lines):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        
        if '=' in line:
            parts = line.split('=', 1)
            k = parts[0].strip()
            v = parts[1].strip()
            # print(f"Line {i+1}: '{k}' = '{v}'")
            try:
                # Test setting it in a dummy dict
                dummy = {}
                dummy[k] = v
                # Test setting it in os.environ (but don't actually do it for all if we suspect crash)
                # Just check for suspicious characters
                if any(ord(c) < 32 or ord(c) > 126 for c in k):
                    print(f"❌ Suspicious key at line {i+1}: {k!r}")
            except Exception as e:
                print(f"❌ Error parsing line {i+1}: {e}")
        else:
            print(f"⚠️ No '=' in line {i+1}: {line!r}")
else:
    print(".env not found")

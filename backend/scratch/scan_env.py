
import os
from pathlib import Path

env_path = Path('.env')
with open(env_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    line = line.strip()
    if not line or line.startswith('#'):
        continue
    
    if '=' not in line:
        print(f"Line {i+1}: No '=' found: {repr(line)}")
        continue
        
    key, value = line.split('=', 1)
    
    # Check for spaces in key
    if ' ' in key:
        print(f"Line {i+1}: Space in key: {repr(key)}")
    
    # Check for weird characters in key
    if not key.isidentifier() and not all(c.isalnum() or c == '_' for c in key):
        print(f"Line {i+1}: Non-standard characters in key: {repr(key)}")

print("Scan complete.")

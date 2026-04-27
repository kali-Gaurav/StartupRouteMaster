
import os
from pathlib import Path

env_path = Path('.env')
try:
    # Try reading as UTF-16 first just in case
    with open(env_path, 'rb') as f:
        content = f.read()
    
    # Remove null bytes
    clean_content = content.replace(b'\x00', b'')
    
    # Also handle possible UTF-16 BOM
    if clean_content.startswith(b'\xff\xfe') or clean_content.startswith(b'\xfe\xff'):
        clean_content = clean_content[2:]
        
    with open(env_path, 'wb') as f:
        f.write(clean_content)
        
    print("Successfully cleaned null bytes from .env")
except Exception as e:
    print(f"Error cleaning .env: {e}")

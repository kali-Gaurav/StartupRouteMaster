import os

path = '.env'
if os.path.exists(path):
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    for i, line in enumerate(lines):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        
        if '=' in line:
            parts = line.split('=', 1)
            k = parts[0].strip()
            v = parts[1].strip()
            try:
                os.environ[k] = v
            except OSError as e:
                print(f"❌ OSError at line {i+1}: key='{k}', value='{v}', error={e}")
            except Exception as e:
                print(f"❌ Error at line {i+1}: {e}")
    print("Test complete")
else:
    print(".env not found")

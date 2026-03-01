import os

files = [
    'backend/services/route_engine.py',
    'backend/services/journey_reconstruction.py',
    'backend/services/multi_modal_route_engine.py'
]

for fname in files:
    size = os.path.getsize(fname)
    with open(fname, 'rb') as f:
        data = f.read()
    null_count = data.count(b'\x00')
    print(f'{fname}: size={size}, null_bytes={null_count}')
    if null_count > 0:
        # Try to remove all null bytes and see if we get valid Python
        try:
            cleaned = data.replace(b'\x00', b'')
            decoded = cleaned.decode('utf-8')
            # Check if it starts with valid Python
            if decoded.strip().startswith(('import ', 'from ', 'class ', 'def ', '#')):
                print(f'  -> Can recover by removing nulls')
                with open(fname, 'wb') as fw:
                    fw.write(cleaned)
                print(f'  -> FIXED')
        except Exception as e:
            print(f'  -> Cannot fix: {e}')

import os

files = [
    'backend/services/route_engine.py',
    'backend/services/journey_reconstruction.py',
    'backend/services/multi_modal_route_engine.py'
]

for fname in files:
    with open(fname, 'rb') as f:
        data = f.read()
    
    # Try UTF-16 decoding
    try:
        decoded = data.decode('utf-16')
        print(f'{fname}: Successfully decoded as UTF-16')
        print(f'  First 100 chars: {repr(decoded[:100])}')
        
        # Write back as UTF-8
        with open(fname, 'w', encoding='utf-8') as fw:
            fw.write(decoded)
        print(f'  -> FIXED (converted to UTF-8)')
    except Exception as e:
        print(f'{fname}: ERROR - {e}')

print("\nDone!")

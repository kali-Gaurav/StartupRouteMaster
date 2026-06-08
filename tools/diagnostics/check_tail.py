import os
path = 'backend/.env'
size = os.path.getsize(path)
with open(path, 'rb') as f:
    f.seek(max(0, size - 200))
    tail = f.read()
    print(tail.hex(' '))
    try:
        print(tail.decode('utf-8'))
    except:
        print("Tail decode failed")

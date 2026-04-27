path = 'backend/.env'
with open(path, 'rb') as f:
    head = f.read(100)
    print(head.hex(' '))

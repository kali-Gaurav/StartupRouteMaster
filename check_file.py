with open('backend/services/telegram_dispatcher.py', 'rb') as f:
    content = f.read()
lines = content.split(b'\n')
for i in range(165, 175):
    if i < len(lines):
        try:
            print(f'{i+1}: {lines[i].decode("utf-8", errors="ignore")}')
        except:
            print(f'{i+1}: <binary>')
import os

path = 'backend/.env'
if os.path.exists(path):
    with open(path, 'rb') as f:
        content = f.read()
    
    print("Content length:", len(content))
    # Replace common Windows line ending issues or bad characters
    # Especially if echo added something weird
    lines = content.splitlines()
    clean_lines = []
    for line in lines:
        try:
            l = line.decode('utf-8').strip()
            if l:
                clean_lines.append(l)
        except:
            print("Bad line skipped")
    
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(clean_lines) + '\n')
    print("Cleaned .env")
else:
    print(".env not found")

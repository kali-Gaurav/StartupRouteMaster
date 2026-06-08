import os

path = '.env'
if os.path.exists(path):
    with open(path, 'rb') as f:
        content = f.read()
    
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
    print("Cleaned root .env")
else:
    print("root .env not found")

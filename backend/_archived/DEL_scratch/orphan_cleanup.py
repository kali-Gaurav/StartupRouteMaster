import re
import os

def cleanup_orphans(filepath):
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    new_lines = []
    for line in lines:
        stripped = line.strip()
        # Remove lines that are just closing brackets/parentheses and indented
        if stripped in [')', ']', '}', '),', '],', '},']:
            if line.startswith('    '):
                # Check if it follows a legitimate block? 
                # Actually, in models, these are almost always orphans now.
                continue
        
        # Remove empty __table_args__ broken lines
        if stripped == '__table_args__ =':
            continue
            
        new_lines.append(line)
    
    with open(filepath, 'w') as f:
        f.writelines(new_lines)

for f in ['database/models/core.py', 'database/models/sathi.py', 'database/models/algorithm.py', 'database/models/telegram.py']:
    if os.path.exists(f):
        print(f"Cleaning orphans in {f}...")
        cleanup_orphans(f)

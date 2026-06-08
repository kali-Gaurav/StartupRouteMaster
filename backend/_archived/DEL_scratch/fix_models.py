import os
import re

def fix_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()
    
    # 1. First, find all classes with __table_args__ as a tuple or dict
    # and add extend_existing=True to them.
    
    # Handle dict __table_args__
    content = re.sub(
        r'__table_args__\s*=\s*\{([^}]*)\}',
        lambda m: f'__table_args__ = {{"extend_existing": True, {m.group(1)}}}' if 'extend_existing' not in m.group(1) else m.group(0),
        content
    )
    
    # Handle tuple __table_args__
    # __table_args__ = (...,)
    # Becomes: __table_args__ = (..., {"extend_existing": True})
    content = re.sub(
        r'__table_args__\s*=\s*\(([\s\S]*?)\)',
        lambda m: f'__table_args__ = ({m.group(1).strip()}, {{"extend_existing": True}})' if 'extend_existing' not in m.group(1) else m.group(0),
        content
    )
    
    # 2. For classes that HAVE __tablename__ but NO __table_args__, add it.
    # This is tricky because we don't want to add it if it was already added by step 1
    # or if it's already there.
    
    lines = content.splitlines()
    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        new_lines.append(line)
        if '__tablename__ =' in line:
            # Check next few lines for __table_args__
            has_args = False
            for j in range(1, 5):
                if i + j < len(lines) and '__table_args__' in lines[i+j]:
                    has_args = True
                    break
            if not has_args:
                new_lines.append('    __table_args__ = {"extend_existing": True}')
        i += 1
    
    new_content = '\n'.join(new_lines)
    
    # Clean up double commas or empty dicts if any
    new_content = new_content.replace(', ,', ',')
    new_content = new_content.replace('{, ', '{')
    
    with open(filepath, 'w') as f:
        f.write(new_content)

files_to_fix = [
    'database/models/core.py',
    'database/models/sathi.py',
    'database/models/algorithm.py',
    'database/models/telegram.py'
]

for f in files_to_fix:
    if os.path.exists(f):
        print(f"Fixing {f}...")
        fix_file(f)

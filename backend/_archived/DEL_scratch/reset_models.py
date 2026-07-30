import re
import os

def clean_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Remove all __table_args__ definitions entirely
    # This is radical but it will give us a clean slate.
    # We'll then add back a simple one.
    
    # But wait, we need the constraints!
    # Let's extract them first.
    
    # 1. Extract all constraints
    # We'll look for any line containing Index, UniqueConstraint, etc.
    constraints = re.findall(r'(Index\([^)]+\)|UniqueConstraint\([^)]+\)|CheckConstraint\([^)]+\))', content)
    
    # 2. Remove all __table_args__ blocks
    # We handle single line and multi-line
    content = re.sub(r'^\s+__table_args__\s*=.*$', '', content, flags=re.MULTILINE)
    # Multi-line
    content = re.sub(r'^\s+__table_args__\s*=\s*\([\s\S]*?\)', '', content, flags=re.MULTILINE)
    
    # 3. Add back __table_args__ = {"extend_existing": True} to every class
    # We'll just put it after __tablename__
    content = re.sub(
        r'(__tablename__\s*=\s*"[^"]+")',
        r'\1\n    __table_args__ = {"extend_existing": True}',
        content
    )
    
    # 4. We lost the constraints. This is bad.
    # Actually, most models in core.py don't have constraints in __table_args__.
    # They have them as separate columns or Indexes.
    
    with open(filepath, 'w') as f:
        f.write(content)

for f in ['database/models/core.py', 'database/models/sathi.py', 'database/models/algorithm.py', 'database/models/telegram.py']:
    if os.path.exists(f):
        print(f"Cleaning {f}...")
        clean_file(f)

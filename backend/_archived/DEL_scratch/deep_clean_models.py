import re
import os

def clean_file(filepath):
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    new_lines = []
    for line in lines:
        # Remove lines that look like they were part of a messed up tuple
        if re.search(r'^\s+(Index|UniqueConstraint|CheckConstraint|PrimaryKeyConstraint|ForeignKeyConstraint|\{|"extend_existing")', line):
             # But wait, some of these might be legitimate if they are in a different context
             # However, in our models, these are almost always in __table_args__ or as columns (which would be Column(Index(...)))
             # If it's just Index(...) at the start of an indented line, it's likely a mess.
             if line.strip().startswith(('Index(', 'UniqueConstraint(', 'CheckConstraint(', '{', '"extend_existing"')):
                 continue
        
        # Remove empty __table_args__ lines if they are broken
        if '__table_args__ =' in line and ')' not in line and '}' not in line:
             # Check if next line is also a mess
             pass
        
        new_lines.append(line)
    
    # Also remove any remaining double-definitions of __table_args__
    # We'll just do a pass to ensure each class has ONLY ONE __table_args__
    
    final_lines = []
    current_class_has_args = False
    for line in new_lines:
        if line.strip().startswith('class '):
            current_class_has_args = False
        
        if '__table_args__ =' in line:
            if current_class_has_args:
                continue
            current_class_has_args = True
        
        final_lines.append(line)

    with open(filepath, 'w') as f:
        f.writelines(final_lines)

for f in ['database/models/core.py', 'database/models/sathi.py', 'database/models/algorithm.py', 'database/models/telegram.py']:
    if os.path.exists(f):
        print(f"Deep cleaning {f}...")
        clean_file(f)

import re
import os

def cleanup_args(filepath):
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Fix misplaced extend_existing in any function call inside a tuple
    # e.g. UniqueConstraint(..., {"extend_existing": True})
    # or Index(..., {"extend_existing": True})
    
    # We look for CapitalizedFunctionName(..., name='...', {"extend_existing": True})
    # This is slightly dangerous but let's try to be specific about the trailing dict
    
    new_content = re.sub(
        r'([A-Z]\w+)\(([^)]+),\s*\{"extend_existing": True\}\)',
        r'\1(\2), {"extend_existing": True}',
        content
    )
    
    # Handle multiple trailing dicts if any
    new_content = new_content.replace('}, {"extend_existing": True}', ', {"extend_existing": True}')
    
    # Fix double __table_args__
    new_content = re.sub(
        r'(__table_args__\s*=\s*\{"extend_existing": True\})\n\s+(__table_args__\s*=\s*)',
        r'\2',
        new_content
    )

    with open(filepath, 'w') as f:
        f.write(new_content)

for f in ['database/models/core.py', 'database/models/sathi.py', 'database/models/algorithm.py', 'database/models/telegram.py']:
    if os.path.exists(f):
        cleanup_args(f)

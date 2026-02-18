#!/usr/bin/env python3
"""Bulk update import statements in backend"""
import os
import re

replacements = [
    (r'from backend\.models import', 'from backend.database.models import'),
    (r'from backend\.config import', 'from backend.database.config import'),
]

dirs_to_process = ['api', 'services']

for root_dir in dirs_to_process:
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            if file.endswith('.py'):
                path = os.path.join(root, file)
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                original_content = content
                for pattern, replacement in replacements:
                    content = re.sub(pattern, replacement, content)
                if content != original_content:
                    with open(path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    print(f"✓ Updated: {path}")

print("\nAll imports updated successfully!")

import os
from pathlib import Path

def clean_env(env_path):
    if not os.path.exists(env_path):
        return
    with open(env_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    seen = set()
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            new_lines.append(line)
            continue
        
        if '=' in stripped:
            key = stripped.split('=')[0].strip()
            if key in seen:
                continue
            seen.add(key)
            # Remove trailing comments or spaces from the value if needed
            new_lines.append(line.rstrip() + '\n')
        else:
            new_lines.append(line)

    with open(env_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

def add_requirement(req_path, package):
    if not os.path.exists(req_path):
        return
    with open(req_path, 'r', encoding='utf-8') as f:
        content = f.read()
    if package not in content:
        with open(req_path, 'a', encoding='utf-8') as f:
            f.write(f"\n{package}\n")

# Clean env files
envs = [
    ".env",
    "backend/.env",
    "production.backend.env",
    "frontend/production.frontend.env"
]
for env in envs:
    clean_env(env)

# Add boto3
add_requirement("backend/requirements.txt", "boto3")
add_requirement("backend/requirements.txt", "botocore")

print("Cleanup and dependency update complete.")

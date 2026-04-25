import sys

with open('requirements.txt', 'r') as f:
    lines = f.read().splitlines()

deps = []
for line in lines:
    line = line.split('#')[0].strip()
    if line:
        deps.append(f'    "{line}",')

deps_str = '\n'.join(deps)

new_pyproject = f'''[project]
name = "backend"
version = "0.1.0"
description = "Add your description here"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
{deps_str}
]

[project.optional-dependencies]
dev = [
    "pytest==8.0.2",
    "pytest-asyncio==0.23.5",
    "pytest-cov==4.1.0",
    "pre-commit==3.6.2"
]

[tool.pyright]
include = ["."]
extraPaths = ["."]
venvPath = "."
venv = ".venv"
typeCheckingMode = "basic"
'''

with open('pyproject.toml', 'w') as f:
    f.write(new_pyproject)

print('Updated pyproject.toml')

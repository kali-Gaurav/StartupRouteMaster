import sys
import os

# Use the virtual environment's python
venv_python = os.path.join("backend", ".venv", "Scripts", "python.exe")

print(f"--- Running Test with {venv_python} ---")
os.system(f"{venv_python} -m pytest backend/tests/test_search.py")

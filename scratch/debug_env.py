import os
from dotenv import dotenv_values

def check_file(filepath):
    print(f"Checking {filepath}")
    if not os.path.exists(filepath):
        print("  File not found")
        return
    config = dotenv_values(filepath)
    for k, v in config.items():
        if k is None:
            print("  Found None key")
            continue
        try:
            os.environ[k] = str(v)
            print(f"  OK: {k}")
        except Exception as e:
            print(f"  FAIL: {k} = {v!r}")
            print(f"  Error: {e}")
            break

check_file(".env")
check_file("backend/.env")

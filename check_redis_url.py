import os
from dotenv import load_dotenv

load_dotenv('backend/.env')
url = os.getenv('REDIS_URL', '')
print(f"REDIS_URL is set: {bool(url)}")
if url:
    parts = url.split("://")
    if len(parts) > 1:
        print(f"Protocol: {parts[0]}")
        # redacted the middle part for safety
        if "@" in parts[1]:
            host_parts = parts[1].split("@")[1].split(":")
            print(f"Host: {host_parts[0]}")
            if len(host_parts) > 1:
                print(f"Port: {host_parts[1].split('/')[0]}")
        else:
            print("No @ found in URL")
else:
    print("REDIS_URL not found in .env")

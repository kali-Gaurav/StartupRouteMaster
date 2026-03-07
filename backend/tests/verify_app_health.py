import httpx
import time
import sys

def check_health(url="http://localhost:8000/health", retries=10, delay=2):
    print(f"Checking health at {url}...")
    for i in range(retries):
        try:
            with httpx.Client() as client:
                response = client.get(url, timeout=5.0)
                if response.status_code == 200:
                    print(f"✅ Server is UP! Response: {response.json()}")
                    return True
                else:
                    print(f"⚠️ Server returned status {response.status_code}")
        except Exception as e:
            print(f"⏳ Attempt {i+1}/{retries}: Server not ready yet... ({e})")
        
        time.sleep(delay)
    
    print("❌ Server failed to start within the timeout period.")
    return False

if __name__ == "__main__":
    if not check_health():
        sys.exit(1)

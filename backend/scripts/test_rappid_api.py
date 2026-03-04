import requests
import json

def test_rappid():
    train_no = "12628" # Karnataka Express
    url = f"https://rappid.in/apis/train.php?train_no={train_no}"
    
    print(f"📡 Fetching live status for train {train_no} from {url}...")
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        print(json.dumps(data, indent=2))
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_rappid()

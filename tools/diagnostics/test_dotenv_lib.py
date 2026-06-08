import dotenv
import os

def test_dotenv(path):
    print(f"Testing {path}...")
    try:
        vals = dotenv.dotenv_values(path)
        print(f"Parsed {len(vals)} values")
        for k, v in vals.items():
            if k is None:
                print("❌ Found None key")
                continue
            try:
                os.environ[k] = v
            except Exception as e:
                print(f"❌ Error setting {k}: {e}")
    except Exception as e:
        print(f"❌ Error parsing {path}: {e}")

test_dotenv('backend/.env')
test_dotenv('.env')

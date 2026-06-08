import dotenv
import os

def test_dotenv(path):
    print(f"Testing {path}...")
    vals = dotenv.dotenv_values(path)
    for k, v in vals.items():
        if k == "" or k is None:
            print(f"❌ Empty key found in {path}! Value: {v}")
        else:
            try:
                os.environ[k] = v
            except OSError as e:
                print(f"❌ OSError in {path}: key='{k}', value='{v}', error={e}")

test_dotenv('backend/.env')
test_dotenv('.env')

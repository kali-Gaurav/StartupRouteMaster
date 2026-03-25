import http.client
import json

def make_request(endpoint):
    conn = http.client.HTTPSConnection("irctc1.p.rapidapi.com")
    headers = {
        'x-rapidapi-key': "e0adaea886msh3fb9b9456cad9ccp17a317jsna7fe7b2fe0b6",
        'x-rapidapi-host': "irctc1.p.rapidapi.com",
        'Content-Type': "application/json"
    }
    print(f"--- Requesting {endpoint} ---")
    try:
        conn.request("GET", endpoint, headers=headers)
        res = conn.getresponse()
        data = res.read()
        print(json.dumps(json.loads(data.decode("utf-8")), indent=2))
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()
        print("--- Done ---")

if __name__ == "__main__":
    make_request("/api/v1/searchTrain?query=12936")

import requests
import json
from datetime import datetime, timedelta

# Define the API endpoint
url = "http://127.0.0.1:8000/api/v2/search/unified"

# Define the search query
# Using a common route: New Delhi (NDLS) to Mumbai Central (BCT)
# Searching for a date 3 days from now to ensure it's in the future
search_date = datetime.now().strftime("%Y-%m-%d")

payload = {
    "source": "NDLS",
    "destination": "BCT",
    "date": search_date
}

# Set headers
headers = {
    "Content-Type": "application/json",
    "Accept": "application/json"
}

def run_search_test():
    """
    Sends a search request to the API and prints the response.
    """
    print(f"Sending search request to {url} with payload:")
    print(json.dumps(payload, indent=2))

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=60)
        response.raise_for_status()  # Raise an exception for bad status codes

        print("\nAPI Response:")
        response_data = response.json()
        print(json.dumps(response_data, indent=2))

        if isinstance(response_data, list):
            print(f"\nSuccessfully found {len(response_data)} journeys.")
            for journey in response_data:
                print(f"  - Journey ID: {journey.get('journey_id')}, Fare: {journey.get('total_price')}")
        else:
            print("\nUnexpected response format.")


    except requests.exceptions.RequestException as e:
        print(f"\nAn error occurred: {e}")

if __name__ == "__main__":
    run_search_test()

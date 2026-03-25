import requests
import json

url = "https://irctc1.p.rapidapi.com/api/v2/trainBetweenStations"

querystring = {"fromStationCode":"CSMT","toStationCode":"HWH"}

headers = {
	"x-rapidapi-key": "e0adaea886msh3fb9b9456cad9ccp17a317jsna7fe7b2fe0b6",
	"x-rapidapi-host": "irctc1.p.rapidapi.com",
	"Content-Type": "application/json"
}

try:
    response = requests.get(url, headers=headers, params=querystring)
    response.raise_for_status()  # Raise an exception for bad status codes
    print(json.dumps(response.json(), indent=2))
except requests.exceptions.HTTPError as errh:
    print(f"Http Error: {errh}")
except requests.exceptions.ConnectionError as errc:
    print(f"Error Connecting: {errc}")
except requests.exceptions.Timeout as errt:
    print(f"Timeout Error: {errt}")
except requests.exceptions.RequestException as err:
    print(f"OOps: Something Else: {err}")

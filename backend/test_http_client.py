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
    make_request("/api/v1/getFare?trainNo=19038&fromStationCode=bvi&toStationCode=st")
    make_request("/api/v2/trainBetweenStations?fromStationCode=bju&toStationCode=bdts")
    make_request("/api/v3/getPNRStatusDetail")
    make_request("/api/v1/searchStation?query=BJU")
    make_request("/api/v1/searchTrain?query=190")
    make_request("/api/v3/trainBetweenStations?fromStationCode=BVI&toStationCode=NDLS")
    make_request("/api/v1/liveTrainStatus?trainNo=19038&startDay=1")
    make_request("/api/v1/getTrainSchedule?trainNo=12936")
    make_request("/api/v3/getPNRStatus")
    make_request("/api/v1/checkSeatAvailability?classType=2A&fromStationCode=ST&quota=GN&toStationCode=BVI&trainNo=19038")
    make_request("/api/v2/checkSeatAvailability?classType=2A&fromStationCode=ST&quota=GN&toStationCode=BVI&trainNo=19038")
    make_request("/api/v1/getTrainClasses?trainNo=19038")
    make_request("/api/v2/getFare?trainNo=19038&fromStationCode=ST&toStationCode=BVI")
    make_request("/api/v3/getTrainsByStation")
    make_request("/api/v3/getLiveStation?hours=1")

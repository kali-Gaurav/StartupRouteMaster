from fastapi.testclient import TestClient
from backend.app import app
from backend.tests.test_integration_audit import login_passenger, auth_headers

client = TestClient(app)

# login
token, refresh = login_passenger()
print('token:', token[:10]+'...')
# monkeypatch not available; but search endpoint is independent
# call availability
search_resp = client.post('/api/search/', json={'source':'PGT','destination':'KOTA','date':'2026-03-01'}, headers=auth_headers(token))
print('search status', search_resp.status_code, search_resp.text[:200])
routes = search_resp.json().get('routes', {}).get('direct', [])
print('routes:', routes)
avail_payload = {'trip_id': routes[0].get('TripId') or routes[0].get('trip_id') or 1,'from_stop_id':1,'to_stop_id':4,'travel_date':'2026-03-01','quota_type':'GENERAL','passengers':1}
avail = client.post('/api/v1/booking/availability', json=avail_payload, headers=auth_headers(token))
print('avail status', avail.status_code, avail.text[:300])
# booking
booking_payload = {"route_id": routes[0].get('RouteId') or routes[0].get('route_id') or str(avail_payload['trip_id']),"travel_date":"2026-03-01","booking_details":{},"amount_paid":0,"passenger_details":[{"full_name":"Test User","age":30,"gender":"M"}]}
book_resp = client.post('/api/v1/booking/', json=booking_payload, headers=auth_headers(token))
print('book status', book_resp.status_code)
print('book body', book_resp.text)

from fastapi.testclient import TestClient
from backend.app import app
from backend.tests.test_integration_audit import login_passenger, auth_headers

client = TestClient(app)

token2,_ = login_passenger("+919876543210")
print('attempting ws connect with token2')
with client.websocket_connect(f"/api/ws/sos?token={token2}") as ws:
    print('connected')
    # now trigger sos
    resp = client.post("/api/sos/", json={"lat":12.34,"lng":56.78,"name":"Tester"}, headers=auth_headers(token2))
    print('sos resp', resp.status_code)
    msg = ws.receive_json()
    print('received', msg)

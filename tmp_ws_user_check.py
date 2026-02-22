import asyncio
from backend.tests.test_integration_audit import login_passenger
from backend.api.websockets import get_ws_user

# login as second user
token2,_ = login_passenger("+919876543210")
print('token2', token2)

user = asyncio.get_event_loop().run_until_complete(get_ws_user(token2))
print('ws user', user)

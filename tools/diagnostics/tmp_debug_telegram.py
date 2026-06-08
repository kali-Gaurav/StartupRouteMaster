import sys
sys.path.insert(0, r'c:/Users/Gaurav Nagar/OneDrive/Desktop/startupV2/backend')
from fastapi import FastAPI
from fastapi.testclient import TestClient
import api.telegram_bot as telegram_module
from api.telegram_bot import router
from unittest.mock import MagicMock

app = FastAPI()
app.include_router(router)
mock_get_db = MagicMock()
mock_get_current_user = MagicMock()
app.dependency_overrides[telegram_module.get_db] = mock_get_db
app.dependency_overrides[telegram_module.get_current_user] = mock_get_current_user
client = TestClient(app)
resp = client.get('/telegram/link-token')
print('status', resp.status_code)
print(resp.text)
print('route count', len(app.routes))
print('override keys', list(app.dependency_overrides.keys()))
print('get_db key module', telegram_module.get_db.__module__)
print('current_user key module', telegram_module.get_current_user.__module__)

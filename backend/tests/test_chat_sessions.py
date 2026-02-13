from fastapi.testclient import TestClient
import json

import app as _app
import api.chat as chat_module


class FakeRedis:
    def __init__(self):
        self.store = {}
        self.sets = {}

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value, ex=None):
        self.store[key] = value

    def delete(self, key):
        self.store.pop(key, None)

    def ping(self):
        return True

    def scan_iter(self, match=None, count=100):
        prefix = match.rstrip('*') if match else ''
        for k in list(self.store.keys()):
            if k.startswith(prefix):
                yield k


client = TestClient(_app.app)


def test_chat_session_persists_in_redis_monkeypatched():
    fake = FakeRedis()
    # monkeypatch module-level redis in chat module
    chat_module._redis = fake

    # 1) start a session (no session_id provided)
    resp = client.post("/chat", json={"message": "Delhi to Mumbai"})
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("session_id")
    assert data.get("trigger_search") is True
    sid = data["session_id"]

    # verify session stored in fake redis
    stored = fake.get(f"chat:session:{sid}")
    assert stored is not None
    session_obj = json.loads(stored)
    # user + assistant messages
    assert any(m["role"] == "user" and "Delhi" in m["content"] for m in session_obj["messages"]) 

    # 2) send another message using same session_id
    resp2 = client.post("/chat", json={"message": "What can you do?", "session_id": sid})
    assert resp2.status_code == 200
    d2 = resp2.json()
    assert d2["session_id"] == sid

    stored2 = json.loads(fake.get(f"chat:session:{sid}"))
    # should contain at least two user messages now
    user_msgs = [m for m in stored2["messages"] if m["role"] == "user"]
    assert len(user_msgs) >= 2

    # 3) health endpoint reports redis_ok and sessions_active
    health = client.get("/chat/health").json()
    assert health["redis_ok"] is True
    assert health["sessions_active"] >= 1

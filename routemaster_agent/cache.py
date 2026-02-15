import time

class TTLCache:
    def __init__(self, ttl_seconds=21600):  # default 6 hours
        self.ttl = ttl_seconds
        self._store = {}

    def get(self, key):
        row = self._store.get(key)
        if not row:
            return None
        value, ts = row
        if time.time() - ts > self.ttl:
            del self._store[key]
            return None
        return value

    def set(self, key, value):
        self._store[key] = (value, time.time())

    def clear(self):
        self._store.clear()

# single global cache instance usable by API
cache = TTLCache()
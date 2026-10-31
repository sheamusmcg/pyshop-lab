"""A small in-process TTL cache with an injectable clock.

The clock is a callable returning seconds. Tests set it so that expiry is
deterministic. The platform's Forecast service caches per fund; the cache must
be invalidated when a fund's forecast is updated through the supported path.
"""
import time


class TTLCache:
    def __init__(self, ttl_seconds=300, clock=None):
        self.ttl = ttl_seconds
        self.clock = clock or time.monotonic
        self._store = {}          # key -> (expires_at, value)
        self.hits = 0
        self.misses = 0

    def get(self, key):
        item = self._store.get(key)
        if item is None or item[0] <= self.clock():
            self.misses += 1
            if item is not None:
                del self._store[key]
            return None
        self.hits += 1
        return item[1]

    def set(self, key, value):
        self._store[key] = (self.clock() + self.ttl, value)

    def invalidate(self, key):
        self._store.pop(key, None)

    def clear(self):
        self._store.clear()

    def stats(self):
        return {"hits": self.hits, "misses": self.misses, "entries": len(self._store)}

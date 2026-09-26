"""In-memory sliding-window rate limits for the public demo.

Protects the AI API budget on an unauthenticated URL: a per-client limit (stops one visitor
hammering the service) and a global daily cap (bounds worst-case spend). State lives in process
memory, so limits apply per replica and reset on restart; production would use a shared store
(e.g. Redis) or the API gateway (Azure API Management / Front Door) instead.
"""

import time
from collections import deque
from collections.abc import Callable


class RateLimiter:
    def __init__(self, per_client_per_minute: int, global_per_day: int,
                 clock: Callable[[], float] = time.monotonic):
        self.per_client = per_client_per_minute
        self.global_per_day = global_per_day
        self.clock = clock
        self._clients: dict[str, deque[float]] = {}
        self._global: deque[float] = deque()

    @staticmethod
    def _prune(hits: deque[float], cutoff: float) -> None:
        while hits and hits[0] <= cutoff:
            hits.popleft()

    def check(self, client: str) -> tuple[str, int] | None:
        """Record a request. Returns None if allowed, else (reason, retry_after_seconds)."""
        now = self.clock()
        self._prune(self._global, now - 86400)
        if len(self._global) >= self.global_per_day:
            return "daily", int(self._global[0] + 86400 - now) + 1

        hits = self._clients.setdefault(client, deque())
        self._prune(hits, now - 60)
        if len(hits) >= self.per_client:
            return "client", int(hits[0] + 60 - now) + 1

        hits.append(now)
        self._global.append(now)
        if len(self._clients) > 10_000:  # drop idle clients so memory stays bounded
            self._clients = {k: v for k, v in self._clients.items() if v and v[-1] > now - 60}
        return None

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request


class RateLimiter:
    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window_seconds: int) -> None:
        now = time.monotonic()
        with self._lock:
            events = self._events[key]
            while events and events[0] <= now - window_seconds:
                events.popleft()
            if len(events) >= limit:
                raise HTTPException(status_code=429, detail="Too many attempts. Please wait and try again.")
            events.append(now)

    def reset(self) -> None:
        with self._lock:
            self._events.clear()


auth_limiter = RateLimiter()


def rate_limit_auth(request: Request) -> None:
    client = request.client.host if request.client else "unknown"
    auth_limiter.check(f"auth:{client}", 10, 60)

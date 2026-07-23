from __future__ import annotations

import asyncio
import hashlib
import time
from collections import deque

from fastapi import Request


class FixedWindowRateLimiter:
    """Small in-process guard for the single-process MVP API deployment."""

    def __init__(self, default_limit: int, sensitive_limit: int, window_seconds: int = 60) -> None:
        self.default_limit = default_limit
        self.sensitive_limit = sensitive_limit
        self.window_seconds = window_seconds
        self._requests: dict[str, deque[float]] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def _identity(request: Request) -> str:
        credential = (
            request.headers.get("authorization")
            or request.headers.get("x-extension-pairing")
            or request.headers.get("x-development-user")
        )
        if credential:
            return hashlib.sha256(credential.encode()).hexdigest()
        return request.client.host if request.client is not None else "unknown"

    @staticmethod
    def _sensitive(path: str) -> bool:
        return "/extension/connections" in path or any(
            marker in path
            for marker in (
                "/imports/",
                "/extension/pairings",
                "/images",
                "/jobs/claim",
                "/workers/register",
            )
        )

    async def check(self, request: Request) -> tuple[bool, int, int]:
        limit = self.sensitive_limit if self._sensitive(request.url.path) else self.default_limit
        now = time.monotonic()
        key = f"{self._identity(request)}:{'sensitive' if self._sensitive(request.url.path) else 'default'}"
        async with self._lock:
            entries = self._requests.setdefault(key, deque())
            threshold = now - self.window_seconds
            while entries and entries[0] <= threshold:
                entries.popleft()
            if len(entries) >= limit:
                retry_after = max(1, int(self.window_seconds - (now - entries[0])) + 1)
                return False, 0, retry_after
            entries.append(now)
            remaining = max(0, limit - len(entries))
            if len(self._requests) > 10_000:
                for stored_key in [
                    stored_key for stored_key, value in self._requests.items() if not value or value[-1] <= threshold
                ]:
                    self._requests.pop(stored_key, None)
                while len(self._requests) > 10_000:
                    self._requests.pop(next(iter(self._requests)))
            return True, remaining, self.window_seconds

"""Tiny async TTL cache so we don't hammer public APIs."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class _Entry:
    value: Any
    expires_at: float


class TTLCache:
    """Minimal async TTL cache. One in-flight request per key (single-flight)."""

    def __init__(self) -> None:
        self._store: dict[str, _Entry] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def get_or_fetch(
        self,
        key: str,
        ttl_seconds: float,
        fetch: Callable[[], Awaitable[Any]],
    ) -> Any:
        now = time.monotonic()
        entry = self._store.get(key)
        if entry and entry.expires_at > now:
            return entry.value

        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            # re-check under lock
            entry = self._store.get(key)
            now = time.monotonic()
            if entry and entry.expires_at > now:
                return entry.value
            value = await fetch()
            self._store[key] = _Entry(value=value, expires_at=now + ttl_seconds)
            return value

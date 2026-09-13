"""Simple process-local TTL cache for odds payloads."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass
class _Entry(Generic[T]):
    value: T
    expires_at: float


class TtlCache(Generic[T]):
    """Single-key TTL cache suitable for one uvicorn process."""

    def __init__(self, ttl_seconds: float = 1800.0) -> None:
        self._ttl_seconds = ttl_seconds
        self._entry: _Entry[T] | None = None

    def get(self) -> T | None:
        if self._entry is None:
            return None
        if time.monotonic() >= self._entry.expires_at:
            self._entry = None
            return None
        return self._entry.value

    def set(self, value: T) -> None:
        self._entry = _Entry(value=value, expires_at=time.monotonic() + self._ttl_seconds)

    def clear(self) -> None:
        self._entry = None

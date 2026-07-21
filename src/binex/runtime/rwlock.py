"""A small async readers-writer lock for workspace serialization (#75).

Writers are mutually exclusive; readers share. This makes two nodes that write
the same workspace serialize (per-node commits can't interleave) while read-only
nodes still run in parallel — "restrictive but correct" for v1.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator


class AsyncRWLock:
    """Writer-exclusive, reader-shared async lock (writer-preferring on contention
    is not guaranteed; fairness is best-effort via asyncio scheduling).
    """

    def __init__(self) -> None:
        self._cond = asyncio.Condition()
        self._readers = 0
        self._writer = False

    @contextlib.asynccontextmanager
    async def read(self) -> AsyncIterator[None]:
        async with self._cond:
            while self._writer:
                await self._cond.wait()
            self._readers += 1
        try:
            yield
        finally:
            async with self._cond:
                self._readers -= 1
                if self._readers == 0:
                    self._cond.notify_all()

    @contextlib.asynccontextmanager
    async def write(self) -> AsyncIterator[None]:
        async with self._cond:
            while self._writer or self._readers > 0:
                await self._cond.wait()
            self._writer = True
        try:
            yield
        finally:
            async with self._cond:
                self._writer = False
                self._cond.notify_all()


__all__ = ["AsyncRWLock"]

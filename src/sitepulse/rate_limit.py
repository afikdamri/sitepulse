"""Shared rate limiting, so crawling and link checking together respect robots.txt Crawl-delay."""

import asyncio
import time

MAX_CRAWL_DELAY_S = 5.0  # honour Crawl-delay, but never stall the audit for hours


class RateLimiter:
    """Guarantee at least `interval_s` seconds between request starts, across all workers."""

    def __init__(self, interval_s: float) -> None:
        self.interval_s = interval_s
        self._lock = asyncio.Lock()
        self._next_allowed = 0.0

    async def wait(self) -> None:
        async with self._lock:  # one worker at a time reserves the next slot
            now = time.monotonic()
            delay = self._next_allowed - now
            if delay > 0:
                await asyncio.sleep(delay)
            self._next_allowed = max(now, self._next_allowed) + self.interval_s

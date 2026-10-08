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
            # perf_counter has microsecond resolution; time.monotonic ticks every ~15.6 ms on
            # Windows, and asyncio.sleep may wake slightly early - so re-check after sleeping.
            # ASYNC110 is about polling state others change; here we just sleep off the rest.
            while (delay := self._next_allowed - time.perf_counter()) > 0:  # noqa: ASYNC110
                await asyncio.sleep(delay)
            self._next_allowed = time.perf_counter() + self.interval_s

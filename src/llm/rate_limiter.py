import asyncio
import time
from collections import defaultdict


class RateLimiter:
    def __init__(self, rpm: int = 100):
        self.rpm = rpm
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._counts: dict[str, list[float]] = defaultdict(list)

    async def acquire(self, provider: str = "openai") -> None:
        lock = self._locks[provider]
        async with lock:
            now = time.monotonic()
            window = now - 60.0
            self._counts[provider] = [
                t for t in self._counts[provider] if t > window
            ]
            if len(self._counts[provider]) >= self.rpm:
                sleep_until = self._counts[provider][0] + 60.0
                sleep_for = sleep_until - now
                if sleep_for > 0:
                    await asyncio.sleep(sleep_for)
            self._counts[provider].append(now)

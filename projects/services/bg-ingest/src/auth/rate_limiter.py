import asyncio
import time
import logging

class AsyncRateLimiter:
    """
    Async token bucket rate limiter with a background refill task.
    Usage:
        async with rate_limiter:
            ... # make API call
    Call close() or use in a context that ensures cleanup.
    """
    def __init__(self, max_calls: int, period: float, refill_interval: float = 0.1):
        self.max_calls = max_calls
        self.period = period
        self._tokens = max_calls
        self._lock = asyncio.Lock()
        self._waiters = []
        self._refill_rate = max_calls / period  # tokens per second
        self._refill_interval = refill_interval
        self._closed = False
        self._last_refill = time.monotonic()
        self._refill_task = asyncio.create_task(self._refill_loop())
        self.logger = logging.getLogger("src.auth.rate_limiter")

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass  # nothing to clean up

    async def acquire(self):
        while True:
            async with self._lock:
                if self._tokens >= 1:
                    self._tokens -= 1
                    return
                waiter = asyncio.get_event_loop().create_future()
                self._waiters.append(waiter)
                # Log when a request is queued due to rate limiting
                self.logger.warning(
                    "Rate limiter: request queued due to no available tokens",
                    extra={
                        "log_type": "rate_limit_queue",
                        "tokens": self._tokens,
                        "queue_length": len(self._waiters),
                        "max_calls": self.max_calls,
                        "period": self.period
                    }
                )
            try:
                await waiter
            except Exception:
                async with self._lock:
                    if waiter in self._waiters:
                        self._waiters.remove(waiter)
                raise

    async def _refill_loop(self):
        try:
            while not self._closed:
                await asyncio.sleep(self._refill_interval)
                async with self._lock:
                    now = time.monotonic()
                    elapsed = now - self._last_refill
                    refill = elapsed * self._refill_rate
                    if refill >= 1:
                        new_tokens = min(self.max_calls, self._tokens + int(refill))
                        added = new_tokens - self._tokens
                        self._tokens = new_tokens
                        self._last_refill = now
                        # Wake up waiters if tokens were added
                        for _ in range(min(added, len(self._waiters))):
                            waiter = self._waiters.pop(0)
                            if not waiter.done():
                                waiter.set_result(None)
        except asyncio.CancelledError:
            pass

    def close(self):
        self._closed = True
        if self._refill_task and not self._refill_task.done():
            try:
                self._refill_task.cancel()
            except RuntimeError:
                # Event loop might be closed, just ignore
                pass

    def __del__(self):
        try:
            self.close()
        except Exception:
            # Never raise exceptions from __del__
            pass

import asyncio
import time
import logging

class CircuitBreakerOpenError(Exception):
    """Raised when the circuit breaker is open and requests are blocked."""
    pass

class CircuitBreaker:
    STATE_CLOSED = "closed"
    STATE_OPEN = "open"
    STATE_HALF_OPEN = "half-open"

    def __init__(
        self,
        failure_threshold=5,
        recovery_timeout=30,
        half_open_success_threshold=2,
        half_open_max_attempts=2,
        logger=None
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_success_threshold = half_open_success_threshold
        self.half_open_max_attempts = half_open_max_attempts
        self._state = self.STATE_CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_attempts = 0
        self._opened_since = None
        self._lock = asyncio.Lock()
        self.logger = logger or logging.getLogger(__name__)

    @property
    def state(self):
        return self._state

    async def before_request(self):
        async with self._lock:
            now = time.monotonic()
            if self._state == self.STATE_OPEN:
                if self._opened_since is not None and (now - self._opened_since) >= self.recovery_timeout:
                    self._state = self.STATE_HALF_OPEN
                    self._success_count = 0
                    self._half_open_attempts = 0
                    self.logger.info("Circuit breaker transitioning to HALF-OPEN.")
                else:
                    self.logger.warning("Circuit breaker is OPEN. Blocking request.")
                    raise CircuitBreakerOpenError("Circuit breaker is open. Requests are temporarily blocked.")
            if self._state == self.STATE_HALF_OPEN:
                if self._half_open_attempts >= self.half_open_max_attempts:
                    self._state = self.STATE_OPEN
                    self._opened_since = now
                    self.logger.warning("Circuit breaker reverting to OPEN from HALF-OPEN (too many attempts).")
                    raise CircuitBreakerOpenError("Circuit breaker is open. Requests are temporarily blocked.")
                self._half_open_attempts += 1

    async def record_success(self):
        async with self._lock:
            if self._state == self.STATE_HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.half_open_success_threshold:
                    self._state = self.STATE_CLOSED
                    self._failure_count = 0
                    self._success_count = 0
                    self._half_open_attempts = 0
                    self._opened_since = None
                    self.logger.info("Circuit breaker transitioning to CLOSED after successful half-open attempts.")
            elif self._state == self.STATE_CLOSED:
                self._failure_count = 0

    async def record_failure(self):
        async with self._lock:
            now = time.monotonic()
            if self._state == self.STATE_CLOSED:
                self._failure_count += 1
                if self._failure_count >= self.failure_threshold:
                    self._state = self.STATE_OPEN
                    self._opened_since = now
                    self.logger.warning("Circuit breaker transitioning to OPEN after failures.")
            elif self._state == self.STATE_HALF_OPEN:
                self._state = self.STATE_OPEN
                self._opened_since = now
                self.logger.warning("Circuit breaker reverting to OPEN from HALF-OPEN after failure.")
                self._success_count = 0
                self._half_open_attempts = 0 
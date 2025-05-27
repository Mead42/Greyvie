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
        self.state = self.STATE_CLOSED
        self._failure_count = 0
        self._opened_since = None
        self._half_open_successes = 0
        self._half_open_attempts = 0
        self._lock = asyncio.Lock()
        self.logger = logger or logging.getLogger(__name__)

    async def before_request(self, correlation_id=None, endpoint=None):
        async with self._lock:
            if self.state == self.STATE_OPEN:
                now = time.monotonic()
                # Ensure _opened_since is set when in OPEN state
                if self._opened_since is None:
                    self._opened_since = now
                
                if (now - self._opened_since) >= self.recovery_timeout:
                    # Move to half-open
                    self.state = self.STATE_HALF_OPEN
                    self._half_open_successes = 0
                    self._half_open_attempts = 0
                    self.logger.info("Circuit breaker transitioning to HALF-OPEN.")
                else:
                    self.logger.warning(
                        "Circuit breaker is OPEN. Blocking request.",
                        extra={
                            "log_type": "circuit_breaker_blocked",
                            "correlation_id": correlation_id,
                            "endpoint": endpoint
                        }
                    )
                    raise CircuitBreakerOpenError("Circuit breaker is open. Requests are temporarily blocked.")
            # If half-open, allow limited attempts
            if self.state == self.STATE_HALF_OPEN:
                if self._half_open_attempts >= self.half_open_max_attempts:
                    self.state = self.STATE_OPEN
                    self._opened_since = time.monotonic()
                    self.logger.warning("Circuit breaker reverting to OPEN from HALF-OPEN (too many attempts).")
                    raise CircuitBreakerOpenError("Circuit breaker is open. Requests are temporarily blocked.")
                self._half_open_attempts += 1
            # If closed, proceed

    async def record_success(self):
        async with self._lock:
            if self.state == self.STATE_HALF_OPEN:
                self._half_open_successes += 1
                if self._half_open_successes >= self.half_open_success_threshold:
                    self.state = self.STATE_CLOSED
                    self._failure_count = 0
                    self._half_open_successes = 0
                    self._half_open_attempts = 0
                    self._opened_since = None
                    self.logger.info("Circuit breaker transitioning to CLOSED after successful half-open attempts.")
            elif self.state == self.STATE_CLOSED:
                self._failure_count = 0

    async def record_failure(self):
        async with self._lock:
            if self.state == self.STATE_CLOSED:
                self._failure_count += 1
                if self._failure_count >= self.failure_threshold:
                    self.state = self.STATE_OPEN
                    self._opened_since = time.monotonic()
                    self.logger.warning("Circuit breaker transitioning to OPEN after failures.")
            elif self.state == self.STATE_HALF_OPEN:
                self.state = self.STATE_OPEN
                self._opened_since = time.monotonic()
                self.logger.warning("Circuit breaker reverting to OPEN from HALF-OPEN after failure.")
                self._half_open_successes = 0
                self._half_open_attempts = 0

import pytest
import asyncio
import time
from src.auth.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError

@pytest.mark.asyncio
async def test_circuit_breaker_closed_to_open():
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=10)
    # Should start closed
    assert cb.state == cb.STATE_CLOSED
    # Record failures
    await cb.record_failure()
    assert cb.state == cb.STATE_CLOSED
    await cb.record_failure()
    assert cb.state == cb.STATE_CLOSED
    await cb.record_failure()
    assert cb.state == cb.STATE_OPEN

@pytest.mark.asyncio
async def test_circuit_breaker_blocks_when_open():
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=5)
    await cb.record_failure()  # Should open
    assert cb.state == cb.STATE_OPEN
    with pytest.raises(CircuitBreakerOpenError):
        await cb.before_request()

@pytest.mark.asyncio
async def test_circuit_breaker_opens_then_half_open_after_timeout(monkeypatch):
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=1)
    await cb.record_failure()  # Open
    assert cb.state == cb.STATE_OPEN
    # Fast-forward time
    monkeypatch.setattr(time, "monotonic", lambda: cb._opened_since + 2)
    # Next before_request should transition to half-open
    await cb.before_request()
    assert cb.state == cb.STATE_HALF_OPEN

@pytest.mark.asyncio
async def test_circuit_breaker_half_open_to_closed_on_success():
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=1, half_open_success_threshold=2, half_open_max_attempts=2)
    await cb.record_failure()  # Open
    # Simulate timeout
    cb.state = cb.STATE_HALF_OPEN
    cb._half_open_successes = 0
    cb._half_open_attempts = 0
    await cb.before_request()  # 1st attempt
    await cb.record_success()
    await cb.before_request()  # 2nd attempt
    await cb.record_success()
    assert cb.state == cb.STATE_CLOSED

@pytest.mark.asyncio
async def test_circuit_breaker_half_open_to_open_on_failure():
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=1, half_open_success_threshold=2, half_open_max_attempts=2)
    await cb.record_failure()  # Open
    # Simulate timeout
    cb.state = cb.STATE_HALF_OPEN
    cb._half_open_successes = 0
    cb._half_open_attempts = 0
    await cb.before_request()  # 1st attempt
    await cb.record_failure()  # Should go back to open
    assert cb.state == cb.STATE_OPEN

@pytest.mark.asyncio
async def test_circuit_breaker_half_open_max_attempts(monkeypatch):
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=1, half_open_success_threshold=2, half_open_max_attempts=1)
    await cb.record_failure()  # Open
    # Simulate timeout
    cb.state = cb.STATE_HALF_OPEN
    cb._half_open_successes = 0
    cb._half_open_attempts = 1
    # Should revert to open after max attempts
    with pytest.raises(CircuitBreakerOpenError):
        await cb.before_request()
    assert cb.state == cb.STATE_OPEN 

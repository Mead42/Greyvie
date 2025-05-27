import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, Mock, patch
from src.auth.dexcom_client import DexcomApiClient
import httpx
from datetime import datetime, timedelta
from src.auth.models import GlucoseReading
import asyncio
import time
from src.auth.rate_limiter import AsyncRateLimiter
import random
from typing import Optional, Type, TypeVar, List
import logging
from src.auth.circuit_breaker import CircuitBreakerOpenError
import json
import uuid
import io

# --- Mock methods for PII redaction test (defined at module level) ---
async def mock_ensure_token_valid(self, correlation_id: str = None):
    """Mock implementation of _ensure_token_valid that accepts correlation_id"""
    pass

async def mock_cb_before_request(*args, **kwargs):
    return None

async def mock_cb_record_success(self): # Renamed to avoid conflict
    return None
# --- End mock methods ---

@pytest.mark.asyncio
async def test_get_authorization_url():
    client = DexcomApiClient(
        base_url="https://sandbox-api.dexcom.com",
        client_id="test_id",
        client_secret="test_secret",
        sandbox=True
    )
    url = client.get_authorization_url("https://myapp.com/callback", state="abc123")
    assert url.startswith("https://sandbox-api.dexcom.com/v2/oauth2/login")
    assert "client_id=test_id" in url
    assert "redirect_uri=https://myapp.com/callback" in url
    assert "state=abc123" in url
    assert "scope=offline_access" in url

@pytest.mark.asyncio
async def test_authenticate_success(monkeypatch):
    client = DexcomApiClient(
        base_url="https://sandbox-api.dexcom.com",
        client_id="test_id",
        client_secret="test_secret",
        sandbox=True
    )
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = AsyncMock(return_value={
        "access_token": "access123",
        "refresh_token": "refresh123",
        "expires_in": 3600
    })
    monkeypatch.setattr(client._client, "post", AsyncMock(return_value=mock_response))
    result = await client.authenticate("authcode", "https://myapp.com/callback")
    assert client._access_token == "access123"
    assert client._refresh_token == "refresh123"
    assert isinstance(client._token_expiry, type(client._token_expiry))
    assert result["access_token"] == "access123"

@pytest.mark.asyncio
async def test_authenticate_failure(monkeypatch):
    client = DexcomApiClient(
        base_url="https://sandbox-api.dexcom.com",
        client_id="test_id",
        client_secret="test_secret",
        sandbox=True
    )
    mock_response = AsyncMock()
    mock_response.status_code = 400
    mock_response.text = "Bad Request"
    mock_response.request = httpx.Request("POST", "https://sandbox-api.dexcom.com/v2/oauth2/token")
    monkeypatch.setattr(client._client, "post", AsyncMock(return_value=mock_response))
    with pytest.raises(httpx.HTTPStatusError):
        await client.authenticate("badcode", "https://myapp.com/callback")

@pytest.mark.asyncio
async def test_refresh_access_token_success(monkeypatch):
    client = DexcomApiClient(
        base_url="https://sandbox-api.dexcom.com",
        client_id="test_id",
        client_secret="test_secret",
        sandbox=True
    )
    client._refresh_token = "refresh123"
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = AsyncMock(return_value={
        "access_token": "access456",
        "refresh_token": "refresh456",
        "expires_in": 3600
    })
    monkeypatch.setattr(client._client, "post", AsyncMock(return_value=mock_response))
    result = await client.refresh_access_token()
    assert client._access_token == "access456"
    assert client._refresh_token == "refresh456"
    assert isinstance(client._token_expiry, type(client._token_expiry))
    assert result["access_token"] == "access456"

@pytest.mark.asyncio
async def test_refresh_access_token_failure(monkeypatch):
    client = DexcomApiClient(
        base_url="https://sandbox-api.dexcom.com",
        client_id="test_id",
        client_secret="test_secret",
        sandbox=True
    )
    client._refresh_token = "refresh123"
    mock_response = AsyncMock()
    mock_response.status_code = 400
    mock_response.text = "Bad Request"
    mock_response.request = httpx.Request("POST", "https://sandbox-api.dexcom.com/v2/oauth2/token")
    monkeypatch.setattr(client._client, "post", AsyncMock(return_value=mock_response))
    with pytest.raises(httpx.HTTPStatusError):
        await client.refresh_access_token()

@pytest.mark.asyncio
async def test_get_request():
    # TODO: Mock HTTPX and test GET request
    pass

@pytest.mark.asyncio
async def test_post_request():
    # TODO: Mock HTTPX and test POST request
    pass

@pytest.mark.asyncio
async def test_error_handling():
    # TODO: Mock HTTPX and test error handling (401, 429, etc.)
    pass

@pytest.mark.asyncio
def make_client_with_token():
    client = DexcomApiClient(
        base_url="https://sandbox-api.dexcom.com",
        client_id="test_id",
        client_secret="test_secret",
        sandbox=True
    )
    client._access_token = "access123"
    client._refresh_token = "refresh123"
    client._token_expiry = datetime.utcnow() + timedelta(hours=1)
    return client

@pytest.mark.asyncio
async def test_get_success(monkeypatch):
    client = make_client_with_token()
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.headers = {}
    mock_response.content = b"{}"
    monkeypatch.setattr(client._client, "get", AsyncMock(return_value=mock_response))
    response = await client.get("/v2/users/self/egvs", params={"foo": "bar"})
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_post_success(monkeypatch):
    client = make_client_with_token()
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.headers = {}
    mock_response.content = b"{}"
    monkeypatch.setattr(client._client, "post", AsyncMock(return_value=mock_response))
    response = await client.post("/v2/users/self/egvs", data={"foo": "bar"})
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_get_expired_token_refresh(monkeypatch):
    client = make_client_with_token()
    client._token_expiry = datetime.utcnow() - timedelta(seconds=1)  # expired
    mock_refresh = AsyncMock()
    mock_refresh.return_value = None
    monkeypatch.setattr(client, "refresh_access_token", mock_refresh)
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.headers = {}
    mock_response.content = b"{}"
    monkeypatch.setattr(client._client, "get", AsyncMock(return_value=mock_response))
    response = await client.get("/v2/users/self/egvs")
    assert response.status_code == 200
    assert mock_refresh.call_count == 1

@pytest.mark.asyncio
async def test_post_expired_token_refresh(monkeypatch):
    client = make_client_with_token()
    client._token_expiry = datetime.utcnow() - timedelta(seconds=1)  # expired
    mock_refresh = AsyncMock()
    mock_refresh.return_value = None
    monkeypatch.setattr(client, "refresh_access_token", mock_refresh)
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.headers = {}
    mock_response.content = b"{}"
    monkeypatch.setattr(client._client, "post", AsyncMock(return_value=mock_response))
    response = await client.post("/v2/users/self/egvs", data={})
    assert response.status_code == 200
    assert mock_refresh.call_count == 1

@pytest.mark.asyncio
async def test_get_401_refresh_and_retry_success(monkeypatch):
    client = make_client_with_token()
    # First call returns 401, second returns 200
    mock_get = AsyncMock(side_effect=[
        AsyncMock(status_code=401, headers={}, content=b"auth error"), 
        AsyncMock(status_code=200, headers={}, content=b"success")
    ])
    monkeypatch.setattr(client._client, "get", mock_get)
    mock_refresh = AsyncMock()
    monkeypatch.setattr(client, "refresh_access_token", mock_refresh)
    response = await client.get("/v2/users/self/egvs")
    assert response.status_code == 200
    assert mock_refresh.call_count == 1
    assert mock_get.call_count == 2

@pytest.mark.asyncio
async def test_post_401_refresh_and_retry_success(monkeypatch):
    client = make_client_with_token()
    # First call returns 401, second returns 200
    mock_post = AsyncMock(side_effect=[
        AsyncMock(status_code=401, headers={}, content=b"auth error"), 
        AsyncMock(status_code=200, headers={}, content=b"success")
    ])
    monkeypatch.setattr(client._client, "post", mock_post)
    mock_refresh = AsyncMock()
    monkeypatch.setattr(client, "refresh_access_token", mock_refresh)
    response = await client.post("/v2/users/self/egvs", data={})
    assert response.status_code == 200
    assert mock_refresh.call_count == 1
    assert mock_post.call_count == 2

@pytest.mark.asyncio
async def test_get_401_refresh_and_retry_fail(monkeypatch):
    client = make_client_with_token()
    # Both calls return 401
    mock_get = AsyncMock(side_effect=[
        AsyncMock(status_code=401, headers={}, text="auth error1", request=httpx.Request("GET", "url"), content=b"auth error1"), 
        AsyncMock(status_code=401, headers={}, text="auth error2", request=httpx.Request("GET", "url"), content=b"auth error2")
    ])
    monkeypatch.setattr(client._client, "get", mock_get)
    mock_refresh = AsyncMock()
    monkeypatch.setattr(client, "refresh_access_token", mock_refresh)
    with pytest.raises(httpx.HTTPStatusError):
        await client.get("/v2/users/self/egvs")
    assert mock_refresh.call_count == 1
    assert mock_get.call_count == 2

@pytest.mark.asyncio
async def test_post_401_refresh_and_retry_fail(monkeypatch):
    client = make_client_with_token()
    # Both calls return 401
    mock_post = AsyncMock(side_effect=[
        AsyncMock(status_code=401, headers={}, text="auth error1", request=httpx.Request("POST", "url"), content=b"auth error1"), 
        AsyncMock(status_code=401, headers={}, text="auth error2", request=httpx.Request("POST", "url"), content=b"auth error2")
    ])
    monkeypatch.setattr(client._client, "post", mock_post)
    mock_refresh = AsyncMock()
    monkeypatch.setattr(client, "refresh_access_token", mock_refresh)
    with pytest.raises(httpx.HTTPStatusError):
        await client.post("/v2/users/self/egvs", data={})
    assert mock_refresh.call_count == 1
    assert mock_post.call_count == 2

@pytest.mark.asyncio
async def test_get_http_error(monkeypatch):
    client = make_client_with_token()
    mock_response = AsyncMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    mock_response.request = httpx.Request("GET", "https://sandbox-api.dexcom.com/v2/users/self/egvs")
    monkeypatch.setattr(client._client, "get", AsyncMock(return_value=mock_response))
    with pytest.raises(httpx.HTTPStatusError):
        await client.get("/v2/users/self/egvs")

@pytest.mark.asyncio
async def test_post_http_error(monkeypatch):
    client = make_client_with_token()
    mock_response = AsyncMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    mock_response.request = httpx.Request("POST", "https://sandbox-api.dexcom.com/v2/users/self/egvs")
    monkeypatch.setattr(client._client, "post", AsyncMock(return_value=mock_response))
    with pytest.raises(httpx.HTTPStatusError):
        await client.post("/v2/users/self/egvs", data={})

@pytest.mark.asyncio
async def test_parse_response_egvs(monkeypatch):
    client = make_client_with_token()
    class DummyResponse:
        def json(self):
            return {"egvs": [
                {"value": 100, "timestamp": "2024-06-01T12:00:00Z"},
                {"value": 110, "timestamp": "2024-06-01T12:05:00Z"}
            ]}
    response = DummyResponse()
    readings = await client.parse_response(response)
    assert isinstance(readings, list)
    assert all(isinstance(r, GlucoseReading) for r in readings)
    assert readings[0].value == 100
    assert readings[1].timestamp == "2024-06-01T12:05:00Z"

@pytest.mark.asyncio
async def test_parse_response_with_model(monkeypatch):
    client = make_client_with_token()
    class DummyResponse:
        def json(self):
            return {"value": 120, "timestamp": "2024-06-01T13:00:00Z"}
    response = DummyResponse()
    reading = await client.parse_response(response, model=GlucoseReading)
    assert isinstance(reading, GlucoseReading)
    assert reading.value == 120

@pytest.mark.asyncio
async def test_parse_response_fallback(monkeypatch):
    client = make_client_with_token()
    class DummyResponse:
        def json(self):
            return {"foo": "bar"}
    response = DummyResponse()
    data = await client.parse_response(response)
    assert data == {"foo": "bar"}

@pytest.mark.asyncio
async def test_parse_response_invalid(monkeypatch):
    client = make_client_with_token()
    class DummyResponse:
        def json(self):
            raise ValueError("Invalid JSON")
    response = DummyResponse()
    with pytest.raises(ValueError):
        await client.parse_response(response)

@pytest.mark.asyncio
async def test_dexcom_client_sandbox_rate_limit():
    client = DexcomApiClient(
        base_url="https://sandbox-api.dexcom.com",
        client_id="test_id",
        client_secret="test_secret",
        sandbox=True
    )
    assert client.rate_limiter.max_calls == 100
    assert client.rate_limiter.period == 60

@pytest.mark.asyncio
async def test_dexcom_client_production_rate_limit():
    client = DexcomApiClient(
        base_url="https://api.dexcom.com",
        client_id="test_id",
        client_secret="test_secret",
        sandbox=False
    )
    assert client.rate_limiter.max_calls == 1000
    assert client.rate_limiter.period == 60

@pytest.mark.asyncio
async def test_dexcom_client_custom_rate_limit():
    client = DexcomApiClient(
        base_url="https://api.dexcom.com",
        client_id="test_id",
        client_secret="test_secret",
        sandbox=False,
        max_calls=42,
        period=10
    )
    assert client.rate_limiter.max_calls == 42
    assert client.rate_limiter.period == 10

@pytest.mark.asyncio
async def test_async_rate_limiter_burst_and_queue():
    limiter = AsyncRateLimiter(max_calls=2, period=1)
    results = []
    async def task(i):
        async with limiter:
            results.append((i, time.monotonic()))
    t0 = time.monotonic()
    await asyncio.gather(*(task(i) for i in range(4)))
    t1 = results[0][1] - t0
    t2 = results[1][1] - t0
    t3 = results[2][1] - t0
    t4 = results[3][1] - t0
    # First two should be nearly instant, next two should be delayed by at least 0.4s
    assert t1 < 0.2
    assert t2 < 0.2
    assert t3 >= 0.4
    assert t4 >= 0.4

@pytest.mark.asyncio
async def test_async_rate_limiter_refill():
    limiter = AsyncRateLimiter(max_calls=1, period=1)
    async with limiter:
        pass
    t0 = time.monotonic()
    await asyncio.sleep(1.05)
    async with limiter:
        t1 = time.monotonic()
    assert t1 - t0 >= 1.0

@pytest.mark.asyncio
def make_retry_client():
    # Use low max_retries and base_delay for fast tests
    return DexcomApiClient(
        base_url="https://sandbox-api.dexcom.com",
        client_id="test_id",
        client_secret="test_secret",
        sandbox=True,
        max_retries=2,
        base_delay=0.01
    )

@pytest.mark.asyncio
async def test_client_circuit_breaker_opens_on_failures(monkeypatch):
    client = DexcomApiClient(
        base_url="https://sandbox-api.dexcom.com",
        client_id="test_id",
        client_secret="test_secret",
        sandbox=True,
        max_retries=0,
        base_delay=0,
        circuit_breaker_config={"failure_threshold": 2, "recovery_timeout": 10, "half_open_success_threshold": 1, "half_open_max_attempts": 1}
    )
    client._access_token = "access123"
    client._token_expiry = datetime.utcnow() + timedelta(hours=1)

    # Always return 500
    mock_response = AsyncMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Error"
    mock_response.request = httpx.Request("GET", "url")
    monkeypatch.setattr(client._client, "get", AsyncMock(return_value=mock_response))

    # First call: should fail and increment failure count
    with pytest.raises(httpx.HTTPStatusError):
        await client.get("/v2/users/self/egvs")
    # Second call: should open the circuit
    with pytest.raises(httpx.HTTPStatusError):
        await client.get("/v2/users/self/egvs")
    # Third call: should be blocked by circuit breaker
    with pytest.raises(CircuitBreakerOpenError):
        await client.get("/v2/users/self/egvs")

@pytest.mark.asyncio
async def test_client_circuit_breaker_recovers_after_timeout(monkeypatch):
    client = DexcomApiClient(
        base_url="https://sandbox-api.dexcom.com",
        client_id="test_id",
        client_secret="test_secret",
        sandbox=True,
        max_retries=0,
        base_delay=0,
        circuit_breaker_config={"failure_threshold": 1, "recovery_timeout": 1, "half_open_success_threshold": 1, "half_open_max_attempts": 1}
    )
    client._access_token = "access123"
    client._token_expiry = datetime.utcnow() + timedelta(hours=1)

    # Always return 500 first, then 200
    mock_get = AsyncMock(side_effect=[
        AsyncMock(status_code=500, text="fail", request=httpx.Request("GET", "url"), headers={}, content=b"fail content"),
        AsyncMock(status_code=200, request=httpx.Request("GET", "url"), headers={}, content=b"success content")
    ])
    monkeypatch.setattr(client._client, "get", mock_get)

    # First call: fail and open circuit
    with pytest.raises(httpx.HTTPStatusError):
        await client.get("/v2/users/self/egvs")
    # Circuit is now open; next call should be blocked
    with pytest.raises(CircuitBreakerOpenError):
        await client.get("/v2/users/self/egvs")
    
    # Ensure the circuit breaker is in the open state
    assert client.circuit_breaker.state == client.circuit_breaker.STATE_OPEN
    
    # Manually set _opened_since if it's None (which shouldn't happen, but let's be safe)
    if client.circuit_breaker._opened_since is None:
        client.circuit_breaker._opened_since = time.monotonic() - 0.5  # Set to a recent time
    
    # Fast-forward time to allow recovery
    current_time = client.circuit_breaker._opened_since + 2
    monkeypatch.setattr(time, "monotonic", lambda: current_time)
    
    # Next call: should be allowed (half-open), and succeed, closing the circuit
    response = await client.get("/v2/users/self/egvs")
    assert response.status_code == 200
    # Circuit should be closed again
    assert client.circuit_breaker.state == client.circuit_breaker.STATE_CLOSED

@pytest.mark.asyncio
async def test_request_response_logging_and_pii_redaction(monkeypatch):
    """
    Test that DexcomApiClient logs requests and responses with PII redacted and correlation_id present.
    """
    from src.auth.dexcom_client import DexcomApiClient, logger, PII_FIELDS
    from src.auth.circuit_breaker import CircuitBreaker
    from src.utils.config import JSONFormatter
    
    # Patch methods on the CircuitBreaker class
    monkeypatch.setattr(CircuitBreaker, "before_request", mock_cb_before_request)
    monkeypatch.setattr(CircuitBreaker, "record_success", mock_cb_record_success)
    
    # Prepare a fake response
    class DummyResponse:
        status_code = 200
        headers = {"X-Test": "value"}
        content = b'{"access_token": "secret", "refresh_token": "refresh_secret", "foo": "bar"}'
        async def json(self):
            return {
                "access_token": "secret",
                "refresh_token": "refresh_secret",
                "foo": "bar"
            }
    
    # Patch the _client.get and _client.post to return DummyResponse
    async def fake_get(*args, **kwargs):
        return DummyResponse()
    async def fake_post(*args, **kwargs):
        return DummyResponse()
    
    # Patch _ensure_token_valid on the DexcomApiClient class for this test
    monkeypatch.setattr(DexcomApiClient, "_ensure_token_valid", mock_ensure_token_valid)

    # Set up log capture
    string_io = io.StringIO()
    handler = logging.StreamHandler(string_io)
    handler.setFormatter(JSONFormatter())
    original_handlers = logger.handlers.copy()
    original_propagate = logger.propagate
    logger.handlers = [handler]
    logger.propagate = False
    
    try:
        client = DexcomApiClient(
            base_url="https://sandbox-api.dexcom.com",
            client_id="test_id",
            client_secret="test_secret",
            sandbox=True
        )
        monkeypatch.setattr(client._client, "get", fake_get)
        monkeypatch.setattr(client._client, "post", fake_post)
        
        # Use a fixed correlation_id for test
        correlation_id = str(uuid.uuid4())
        # Call GET
        await client.get("/v2/users/self/egvs", params={"user_id": "should_redact", "foo": "bar"}, correlation_id=correlation_id)
        # Call POST
        await client.post("/v2/users/self/egvs", data={"access_token": "should_redact", "foo": "bar"}, correlation_id=correlation_id)
        
        # Get all log lines
        log_lines = [line for line in string_io.getvalue().splitlines() if line.strip()]
        # There should be 4 logs: request/response for GET and POST
        assert len(log_lines) == 4
        for log_line in log_lines:
            log_json = json.loads(log_line)
            # Correlation ID should be present and match
            assert log_json["correlation_id"] == correlation_id
            # PII fields should be redacted in params/body/headers
            for pii in PII_FIELDS:
                if "params" in log_json and log_json["params"]:
                    assert log_json["params"].get(pii) != "should_redact"
                    if pii in log_json["params"]:
                        assert log_json["params"][pii] == "***REDACTED***"
                if "body" in log_json and log_json["body"]:
                    assert log_json["body"].get(pii) != "should_redact"
                    if pii in log_json["body"]:
                        assert log_json["body"][pii] == "***REDACTED***"
                if "headers" in log_json and log_json["headers"]:
                    assert log_json["headers"].get(pii) != "should_redact"
                    if pii in log_json["headers"]:
                        assert log_json["headers"][pii] == "***REDACTED***"
    finally:
        logger.handlers = original_handlers
        logger.propagate = original_propagate

def test_logging_json_format_and_fields(caplog):
    """
    Test that DexcomApiClient logs are output in structured JSON format and contain required fields.
    """
    from src.auth.dexcom_client import logger
    from src.utils.config import JSONFormatter
    import logging
    import sys
    import io
    
    # Use a StringIO object to capture the log output directly
    string_io = io.StringIO()
    handler = logging.StreamHandler(string_io)
    handler.setFormatter(JSONFormatter())
    
    # Save original handlers and propagate settings
    original_handlers = logger.handlers.copy()
    original_propagate = logger.propagate
    
    # Configure our test handler
    logger.handlers = [handler]
    logger.propagate = False
    
    try:
        # Log a test message
        logger.info("Test log message", extra={"foo": "bar"})
        
        # Get the logged content
        log_content = string_io.getvalue().strip()
        
        # Verify it's valid JSON and contains expected fields
        log_json = json.loads(log_content)
        assert log_json["level"] == "INFO"
        assert log_json["message"] == "Test log message"
        assert log_json["foo"] == "bar"
        assert "timestamp" in log_json
        assert "module" in log_json
        assert "function" in log_json
        assert "line" in log_json
    finally:
        # Restore logger to original state
        logger.handlers = original_handlers
        logger.propagate = original_propagate

def test_logging_level_filtering(caplog):
    """
    Test that log level filtering works as expected for DexcomApiClient logs.
    """
    from src.auth.dexcom_client import logger
    from src.utils.config import JSONFormatter
    import logging
    import io
    
    # Create two StringIO objects to capture different log levels
    info_io = io.StringIO()
    warning_io = io.StringIO()
    
    # Save original handlers and propagate settings
    original_handlers = logger.handlers.copy()
    original_propagate = logger.propagate
    original_level = logger.level
    
    try:
        # Set up INFO handler
        info_handler = logging.StreamHandler(info_io)
        info_handler.setFormatter(JSONFormatter())
        info_handler.setLevel(logging.INFO)
        
        # Set up WARNING handler
        warning_handler = logging.StreamHandler(warning_io)
        warning_handler.setFormatter(JSONFormatter())
        warning_handler.setLevel(logging.WARNING)
        
        # Configure our test handlers
        logger.handlers = [info_handler, warning_handler]
        logger.setLevel(logging.INFO)  # Enable INFO level logging
        logger.propagate = False
        
        # Log test messages
        logger.info("This should not appear in WARNING")
        logger.warning("This should appear", extra={"test": True})
        
        # Check that INFO captures both messages
        info_content = info_io.getvalue()
        assert "This should not appear in WARNING" in info_content
        assert "This should appear" in info_content
        
        # Check that WARNING only captures warning message
        warning_content = warning_io.getvalue()
        assert "This should not appear in WARNING" not in warning_content
        assert "This should appear" in warning_content
        
        # Verify JSON format of warning message
        warning_log = warning_content.strip().split('\n')[-1]  # Get last line
        log_json = json.loads(warning_log)
        assert log_json["level"] == "WARNING"
        assert log_json["message"] == "This should appear"
        assert log_json["test"] is True
    finally:
        # Restore logger to original state
        logger.handlers = original_handlers
        logger.propagate = original_propagate
        logger.setLevel(original_level)

@pytest.mark.asyncio
async def test_correlation_id_propagation(monkeypatch):
    """
    Test that correlation IDs are properly propagated through all operations.
    """
    from src.auth.dexcom_client import DexcomApiClient, logger
    from src.auth.circuit_breaker import CircuitBreaker
    from src.utils.config import JSONFormatter
    
    # Patch methods on the CircuitBreaker class
    monkeypatch.setattr(CircuitBreaker, "before_request", mock_cb_before_request)
    monkeypatch.setattr(CircuitBreaker, "record_success", mock_cb_record_success)
    
    # Prepare a fake response
    class DummyResponse:
        status_code = 200
        headers = {"X-Test": "value"}
        content = b'{"access_token": "secret", "refresh_token": "refresh_secret", "expires_in": 3600, "foo": "bar"}'
        async def json(self):
            return {
                "access_token": "secret",
                "refresh_token": "refresh_secret",
                "expires_in": 3600,
                "foo": "bar"
            }
    
    # Patch the _client.get and _client.post to return DummyResponse
    async def fake_get(*args, **kwargs):
        return DummyResponse()
    async def fake_post(*args, **kwargs):
        return DummyResponse()
    
    # Set up log capture
    string_io = io.StringIO()
    handler = logging.StreamHandler(string_io)
    handler.setFormatter(JSONFormatter())
    original_handlers = logger.handlers.copy()
    original_propagate = logger.propagate
    logger.handlers = [handler]
    logger.propagate = False
    
    try:
        client = DexcomApiClient(
            base_url="https://sandbox-api.dexcom.com",
            client_id="test_id",
            client_secret="test_secret",
            sandbox=True
        )
        monkeypatch.setattr(client._client, "get", fake_get)
        monkeypatch.setattr(client._client, "post", fake_post)
        
        # Use a fixed correlation_id for test
        correlation_id = str(uuid.uuid4())
        
        # Test GET request
        await client.get("/v2/users/self/egvs", correlation_id=correlation_id)
        
        # Test token refresh
        await client.refresh_access_token(correlation_id=correlation_id)
        
        # Get all log lines
        log_lines = [line for line in string_io.getvalue().splitlines() if line.strip()]
        
        # Verify correlation IDs in all logs
        for log_line in log_lines:
            log_json = json.loads(log_line)
            assert "correlation_id" in log_json, f"Missing correlation_id in log: {log_json}"
            assert log_json["correlation_id"] == correlation_id, f"Correlation ID mismatch in log: {log_json}"
            
            # Verify log types
            assert "log_type" in log_json, f"Missing log_type in log: {log_json}"
            assert log_json["log_type"] in {
                "request", "response", "error", "retry", 
                "token_refresh", "token_refresh_error", "token_refresh_success"
            }, f"Invalid log_type in log: {log_json}"
            
    finally:
        logger.handlers = original_handlers
        logger.propagate = original_propagate

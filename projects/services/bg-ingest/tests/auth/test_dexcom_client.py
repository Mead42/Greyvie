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
    monkeypatch.setattr(client._client, "get", AsyncMock(return_value=mock_response))
    response = await client.get("/v2/users/self/egvs", params={"foo": "bar"})
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_post_success(monkeypatch):
    client = make_client_with_token()
    mock_response = AsyncMock()
    mock_response.status_code = 200
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
    monkeypatch.setattr(client._client, "post", AsyncMock(return_value=mock_response))
    response = await client.post("/v2/users/self/egvs", data={})
    assert response.status_code == 200
    assert mock_refresh.call_count == 1

@pytest.mark.asyncio
async def test_get_401_refresh_and_retry_success(monkeypatch):
    client = make_client_with_token()
    # First call returns 401, second returns 200
    mock_get = AsyncMock(side_effect=[AsyncMock(status_code=401), AsyncMock(status_code=200)])
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
    mock_post = AsyncMock(side_effect=[AsyncMock(status_code=401), AsyncMock(status_code=200)])
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
    mock_get = AsyncMock(side_effect=[AsyncMock(status_code=401), AsyncMock(status_code=401)])
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
    mock_post = AsyncMock(side_effect=[AsyncMock(status_code=401), AsyncMock(status_code=401)])
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

# @pytest.mark.asyncio
# async def test_get_retries_on_5xx(monkeypatch):
#     """Test GET retries on 5xx errors up to max_retries, then raises."""
#     client = make_retry_client()
#     client._access_token = "access123"
#     client._token_expiry = datetime.utcnow() + timedelta(hours=1)
    
#     # Create a mock request to use in the HTTPStatusError
#     mock_request = httpx.Request("GET", "https://sandbox-api.dexcom.com/v2/users/self/egvs")
    
#     # Create a function that returns a fresh mock response each time
#     # This ensures each call gets a new mock with the exception properly set up
#     def create_error_response():
#         mock_response = AsyncMock()
#         mock_response.status_code = 500
#         mock_response.text = "Internal Server Error"
#         mock_response.request = mock_request
#         mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
#             "500 Internal Server Error", request=mock_request, response=mock_response
#         )
#         return mock_response
    
#     # Create a mock get method that returns a new error response each time
#     mock_get = AsyncMock(side_effect=[create_error_response() for _ in range(client.max_retries + 1)])
#     monkeypatch.setattr(client._client, "get", mock_get)
    
#     # Mock sleep to avoid real delay
#     monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    
#     # The test should raise the HTTPStatusError after max_retries + 1 attempts
#     with pytest.raises(httpx.HTTPStatusError):
#         await client.get("/v2/users/self/egvs")
    
#     # Verify the get method was called the expected number of times
#     assert mock_get.call_count == client.max_retries + 1

# @pytest.mark.asyncio
# async def test_post_retries_on_429(monkeypatch):
#     """Test POST retries on 429 errors up to max_retries, then raises."""
#     client = make_retry_client()
#     client._access_token = "access123"
#     client._token_expiry = datetime.utcnow() + timedelta(hours=1)
    
#     # Create a mock request to use in the HTTPStatusError
#     mock_request = httpx.Request("POST", "https://sandbox-api.dexcom.com/v2/users/self/egvs")
    
#     # Create a function that returns a fresh mock response each time
#     def create_error_response():
#         mock_response = AsyncMock()
#         mock_response.status_code = 429
#         mock_response.text = "Rate limit"
#         mock_response.request = mock_request
#         mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
#             "429 Too Many Requests", request=mock_request, response=mock_response
#         )
#         return mock_response
    
#     # Create a mock post method that returns a new error response each time
#     mock_post = AsyncMock(side_effect=[create_error_response() for _ in range(client.max_retries + 1)])
#     monkeypatch.setattr(client._client, "post", mock_post)
    
#     # Mock sleep to avoid real delay
#     monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    
#     with pytest.raises(httpx.HTTPStatusError):
#         await client.post("/v2/users/self/egvs", data={})
        
#     # Verify the post method was called the expected number of times
#     assert mock_post.call_count == client.max_retries + 1

@pytest.mark.asyncio
async def test_get_retries_on_network_error(monkeypatch):
    """Test GET retries on network errors (TransportError) up to max_retries, then raises."""
    client = make_retry_client()
    client._access_token = "access123"
    client._token_expiry = datetime.utcnow() + timedelta(hours=1)
    # Always raise TransportError
    async def raise_transport(*a, **kw):
        raise httpx.TransportError("network fail")
    monkeypatch.setattr(client._client, "get", raise_transport)
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    with pytest.raises(httpx.TransportError):
        await client.get("/v2/users/self/egvs")

@pytest.mark.asyncio
async def test_post_does_not_retry_on_400(monkeypatch):
    """Test POST does not retry on 400 error (non-retryable)."""
    client = make_retry_client()
    client._access_token = "access123"
    client._token_expiry = datetime.utcnow() + timedelta(hours=1)
    mock_response = AsyncMock()
    mock_response.status_code = 400
    mock_response.text = "Bad Request"
    mock_response.request = httpx.Request("POST", "url")
    monkeypatch.setattr(client._client, "post", AsyncMock(return_value=mock_response))
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    with pytest.raises(httpx.HTTPStatusError):
        await client.post("/v2/users/self/egvs", data={})
    # Should only call once (no retry)
    assert client._client.post.call_count == 1

@pytest.mark.asyncio
async def test_get_logs_warning_and_respects_retry_after_on_429(monkeypatch, caplog):
    """Test GET logs a warning and respects Retry-After header on 429, then retries."""
    client = make_retry_client() # max_retries=2, base_delay=0.01
    client.max_retries = 1 # Override for this test to simplify call count checks
    client._access_token = "access123"
    client._token_expiry = datetime.utcnow() + timedelta(hours=1)

    retry_after_seconds = 5
    mock_response_429 = AsyncMock()
    mock_response_429.status_code = 429
    mock_response_429.text = "Rate limit hit"
    mock_response_429.request = httpx.Request("GET", "https://sandbox-api.dexcom.com/test_endpoint")
    mock_response_429.headers = {"Retry-After": str(retry_after_seconds)}

    mock_response_ok = AsyncMock()
    mock_response_ok.status_code = 200
    mock_response_ok.json = AsyncMock(return_value={"status": "ok"})

    # First call: 429, Second call: 200
    monkeypatch.setattr(client._client, "get", AsyncMock(side_effect=[mock_response_429, mock_response_ok]))
    
    mock_sleep = AsyncMock()
    monkeypatch.setattr(asyncio, "sleep", mock_sleep)

    caplog.set_level(logging.WARNING)

    await client.get("/test_endpoint")

    assert client._client.get.call_count == 2 # Initial call + 1 retry

    # Check log records
    assert len(caplog.records) == 1
    log_record = caplog.records[0]
    assert log_record.levelname == "WARNING"
    assert "Rate limit hit (429)" in log_record.message
    assert f"Attempt 1/{client.max_retries + 1}" in log_record.message # First attempt gets 429
    assert f"Retrying after {retry_after_seconds}s" in log_record.message
    assert "URL: https://sandbox-api.dexcom.com/test_endpoint" in log_record.message

    # Check that sleep was called with Retry-After (plus potential jitter)
    # The actual_delay includes jitter, so we check it's close to retry_after_seconds
    # delay = retry_after_seconds, jitter = random.uniform(0, delay / 2)
    # actual_delay = delay + jitter
    # So, retry_after_seconds <= actual_delay < retry_after_seconds + retry_after_seconds / 2
    assert mock_sleep.call_count == 1
    slept_duration = mock_sleep.call_args[0][0]
    assert retry_after_seconds <= slept_duration < retry_after_seconds * 1.5

@pytest.mark.asyncio
async def test_get_logs_warning_and_uses_exponential_backoff_if_no_retry_after(monkeypatch, caplog):
    """Test GET logs a warning and uses exponential backoff if Retry-After is missing."""
    client = make_retry_client() # max_retries=2, base_delay=0.01
    client.max_retries = 1
    client._access_token = "access123"
    client._token_expiry = datetime.utcnow() + timedelta(hours=1)

    mock_response_429 = AsyncMock()
    mock_response_429.status_code = 429
    mock_response_429.text = "Rate limit hit - no Retry-After"
    mock_response_429.request = httpx.Request("GET", "https://sandbox-api.dexcom.com/test_no_header")
    mock_response_429.headers = {} # No Retry-After header

    mock_response_ok = AsyncMock()
    mock_response_ok.status_code = 200
    mock_response_ok.json = AsyncMock(return_value={"status": "ok"})

    monkeypatch.setattr(client._client, "get", AsyncMock(side_effect=[mock_response_429, mock_response_ok]))
    
    mock_sleep = AsyncMock()
    monkeypatch.setattr(asyncio, "sleep", mock_sleep)

    caplog.set_level(logging.WARNING)
    await client.get("/test_no_header")

    assert client._client.get.call_count == 2
    assert len(caplog.records) == 1
    log_record = caplog.records[0]
    assert "Rate limit hit (429)" in log_record.message
    # Check it mentions the default backoff calculation, e.g., base_delay * (2**0) for first attempt
    expected_retry_mention = client.base_delay * (2**0) # attempt is 0-indexed in calculation before sleep
    assert f"Retrying after {expected_retry_mention}s" in log_record.message
    
    assert mock_sleep.call_count == 1
    slept_duration = mock_sleep.call_args[0][0]
    # base_delay = 0.01. delay = 0.01 * (2**0) = 0.01. jitter = random.uniform(0, 0.01/2)
    # 0.01 <= slept_duration < 0.01 + 0.005 = 0.015
    assert client.base_delay <= slept_duration < client.base_delay * 1.5 

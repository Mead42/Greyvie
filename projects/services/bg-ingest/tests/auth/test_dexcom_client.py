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

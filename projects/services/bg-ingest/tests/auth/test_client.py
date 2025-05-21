"""Tests for the OAuth2 API client implementation."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from pydantic import SecretStr

from src.auth.client import DexcomClient, DexcomAPIError, DexcomAuthError
from src.auth.oauth import TokenResponse
from src.models.tokens import TokenProvider, UserToken
from src.utils.config import get_settings

settings = get_settings()

# Test data
TEST_USER_ID = "test_user"
TEST_CODE = "test_code"
TEST_CODE_VERIFIER = "test_verifier"
TEST_CODE_CHALLENGE = "test_challenge"
TEST_STATE = "test_state"
TEST_ACCESS_TOKEN = "test_access_token"
TEST_REFRESH_TOKEN = "test_refresh_token"
TEST_EXPIRES_IN = 3600

@pytest.fixture
def mock_token():
    """Create a mock UserToken."""
    return UserToken(
        user_id=TEST_USER_ID,
        provider=TokenProvider.DEXCOM,
        access_token=SecretStr(TEST_ACCESS_TOKEN),
        refresh_token=SecretStr(TEST_REFRESH_TOKEN),
        expires_at=datetime.utcnow() + timedelta(seconds=TEST_EXPIRES_IN),
        scope="mock_scope",
    )

@pytest.fixture
def mock_expired_token():
    """Create a mock expired UserToken."""
    # Create a token with future expiration to pass validation
    token = UserToken(
        user_id=TEST_USER_ID,
        provider=TokenProvider.DEXCOM,
        access_token=SecretStr(TEST_ACCESS_TOKEN),
        refresh_token=SecretStr(TEST_REFRESH_TOKEN),
        expires_at=datetime.utcnow() + timedelta(minutes=5),  # Set to future to pass validation
        scope="mock_scope",
    )
    return token

@pytest.fixture
async def client():
    """Create a DexcomClient instance."""
    async with DexcomClient(TEST_USER_ID) as client:
        yield client

@pytest.mark.asyncio
async def test_initiate_authorization(client):
    """Test initiating the OAuth2 authorization flow."""
    with patch("src.auth.client.generate_pkce_pair", return_value=(TEST_CODE_VERIFIER, TEST_CODE_CHALLENGE)):
        result = await client.initiate_authorization(TEST_STATE)
        
        assert "authorization_url" in result
        assert result["code_verifier"] == TEST_CODE_VERIFIER
        assert result["state"] == TEST_STATE
        
        # Verify URL contains required parameters
        auth_url = result["authorization_url"]
        assert client.client_id in auth_url
        assert TEST_CODE_CHALLENGE in auth_url
        assert TEST_STATE in auth_url

@pytest.mark.asyncio
async def test_handle_callback_success(client, mock_token):
    """Test successful OAuth2 callback handling."""
    with patch("src.auth.client.exchange_code_and_store", return_value=mock_token) as mock_exchange:
        result = await client.handle_callback(TEST_CODE, TEST_CODE_VERIFIER)
        
        mock_exchange.assert_called_once_with(
            user_id=TEST_USER_ID,
            code=TEST_CODE,
            code_verifier=TEST_CODE_VERIFIER,
            provider=TokenProvider.DEXCOM,
        )
        
        assert isinstance(result, UserToken)
        assert result.user_id == TEST_USER_ID
        assert result.access_token.get_secret_value() == TEST_ACCESS_TOKEN

@pytest.mark.asyncio
async def test_handle_callback_failure(client):
    """Test OAuth2 callback handling with token exchange failure."""
    with patch("src.auth.client.exchange_code_and_store", side_effect=DexcomAuthError("Failed to exchange code for tokens")):
        with pytest.raises(DexcomAuthError, match="Failed to exchange code for tokens"):
            await client.handle_callback(TEST_CODE, TEST_CODE_VERIFIER)

@pytest.mark.asyncio
async def test_get_auth_header_success(client, mock_token):
    """Test getting authorization header with valid token."""
    with patch("src.auth.client.get_token", return_value=mock_token):
        headers = await client._get_auth_header()
        assert headers["Authorization"] == f"Bearer {TEST_ACCESS_TOKEN}"

@pytest.mark.asyncio
async def test_get_auth_header_no_token(client):
    """Test getting authorization header with no token available."""
    with patch("src.auth.client.get_token", return_value=None):
        with pytest.raises(DexcomAuthError, match="No valid token available"):
            await client._get_auth_header()

@pytest.mark.asyncio
async def test_get_auth_header_expired_token(client, mock_expired_token):
    """Test getting authorization header with expired token that can't be refreshed."""
    # Use a separate patch for the is_expired method
    with patch("src.auth.client.get_token", return_value=mock_expired_token), \
         patch.object(UserToken, "is_expired", return_value=True):
        with pytest.raises(DexcomAuthError, match="Token is expired"):
            await client._get_auth_header()

@pytest.mark.asyncio
async def test_make_request_success(client, mock_token):
    """Test successful API request."""
    mock_response = httpx.Response(200, json={"data": "test"})
    
    with patch("src.auth.client.get_token", return_value=mock_token), \
         patch.object(client.http_client, "request", return_value=mock_response):
        response = await client._make_request("GET", "/test")
        assert response.status_code == 200
        assert response.json() == {"data": "test"}

@pytest.mark.asyncio
async def test_make_request_auth_failure(client, mock_token):
    """Test API request with authentication failure."""
    mock_response = httpx.Response(401, text="Unauthorized")
    
    with patch("src.auth.client.get_token", return_value=mock_token), \
         patch.object(client.http_client, "request", return_value=mock_response):
        with pytest.raises(DexcomAuthError, match="Authentication failed"):
            await client._make_request("GET", "/test")

@pytest.mark.asyncio
async def test_make_request_api_error(client, mock_token):
    """Test API request with non-auth error."""
    mock_response = httpx.Response(500, text="Server Error")
    
    with patch("src.auth.client.get_token", return_value=mock_token), \
         patch.object(client.http_client, "request", return_value=mock_response):
        with pytest.raises(DexcomAPIError, match="API request failed"):
            await client._make_request("GET", "/test")

@pytest.mark.asyncio
async def test_make_request_network_error(client, mock_token):
    """Test API request with network error."""
    with patch("src.auth.client.get_token", return_value=mock_token), \
         patch.object(client.http_client, "request", side_effect=httpx.RequestError("Network error")):
        with pytest.raises(DexcomAPIError, match="Request failed"):
            await client._make_request("GET", "/test")

@pytest.mark.asyncio
async def test_convenience_methods(client, mock_token):
    """Test the convenience HTTP methods."""
    mock_response = httpx.Response(200, json={"data": "test"})
    
    with patch("src.auth.client.get_token", return_value=mock_token), \
         patch.object(client.http_client, "request", return_value=mock_response):
        # Test GET
        response = await client.get("/test")
        assert response.status_code == 200
        
        # Test POST
        response = await client.post("/test", json={"key": "value"})
        assert response.status_code == 200
        
        # Test PUT
        response = await client.put("/test", json={"key": "value"})
        assert response.status_code == 200
        
        # Test DELETE
        response = await client.delete("/test")
        assert response.status_code == 200

@pytest.mark.asyncio
async def test_context_manager(mock_token):
    """Test the client as a context manager."""
    with patch("src.auth.client.get_token", return_value=mock_token):
        async with DexcomClient(TEST_USER_ID) as client:
            assert isinstance(client, DexcomClient)
            assert not client.http_client.is_closed
        
        # Verify client is closed after context
        assert client.http_client.is_closed 

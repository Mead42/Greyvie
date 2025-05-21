"""Tests for the OAuth2 implementation."""
import json
import urllib.parse
from datetime import datetime, timedelta
from unittest import mock

import pytest
import httpx
from httpx import Response

from src.auth.oauth import (
    TokenError,
    TokenResponse,
    build_dexcom_auth_url,
    exchange_code_for_tokens,
    refresh_access_token,
    validate_redirect_uri,
)


class TestOauthUrl:
    """Tests for the OAuth2 URL building functionality."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing."""
        with mock.patch("src.auth.oauth.get_settings") as mock_get_settings:
            settings = mock.MagicMock()
            settings.dexcom_api_base_url = "https://sandbox-api.dexcom.com"
            settings.dexcom_redirect_uri = "https://myapp.com/callback"
            settings.service_env = "development"
            settings.request_timeout_seconds = 30
            mock_get_settings.return_value = settings
            yield settings

    def test_build_dexcom_auth_url(self, mock_settings):
        """Test building the Dexcom authorization URL."""
        # Test parameters
        client_id = "test_client_id"
        redirect_uri = "https://myapp.com/callback"
        state = "random_state_value"
        code_challenge = "code_challenge_value"
        
        # Get the URL
        url = build_dexcom_auth_url(
            client_id=client_id,
            redirect_uri=redirect_uri,
            state=state,
            code_challenge=code_challenge,
        )
        
        # Parse the URL
        parsed_url = urllib.parse.urlparse(url)
        query_params = dict(urllib.parse.parse_qsl(parsed_url.query))
        
        # Check the base URL
        assert parsed_url.scheme == "https"
        assert parsed_url.netloc == "sandbox-api.dexcom.com"
        assert parsed_url.path == "/v2/oauth2/login"
        
        # Check required parameters
        assert query_params["client_id"] == client_id
        assert query_params["redirect_uri"] == redirect_uri
        assert query_params["response_type"] == "code"
        assert query_params["state"] == state
        assert query_params["code_challenge"] == code_challenge
        assert query_params["code_challenge_method"] == "S256"
        assert query_params["scope"] == "offline_access"

    def test_build_dexcom_auth_url_with_custom_scope(self, mock_settings):
        """Test building the authorization URL with custom scope."""
        # Test with a string scope
        url_with_string_scope = build_dexcom_auth_url(
            client_id="test_client_id",
            redirect_uri="https://myapp.com/callback",
            state="random_state_value",
            code_challenge="code_challenge_value",
            scope="offline_access egv",
        )
        
        parsed_url = urllib.parse.urlparse(url_with_string_scope)
        query_params = dict(urllib.parse.parse_qsl(parsed_url.query))
        assert query_params["scope"] == "offline_access egv"
        
        # Test with a list scope
        url_with_list_scope = build_dexcom_auth_url(
            client_id="test_client_id",
            redirect_uri="https://myapp.com/callback",
            state="random_state_value",
            code_challenge="code_challenge_value",
            scope=["offline_access", "egv", "calibrations"],
        )
        
        parsed_url = urllib.parse.urlparse(url_with_list_scope)
        query_params = dict(urllib.parse.parse_qsl(parsed_url.query))
        assert query_params["scope"] == "offline_access egv calibrations"

    def test_validate_redirect_uri(self, mock_settings):
        """Test redirect URI validation."""
        # Valid URI from settings
        assert validate_redirect_uri("https://myapp.com/callback") is True
        
        # Development URIs in development mode
        assert validate_redirect_uri("http://localhost:5001/api/oauth/callback") is True
        assert validate_redirect_uri("http://localhost:3000/callback") is True
        
        # Invalid URI
        assert validate_redirect_uri("https://malicious-site.com/callback") is False
        
        # Test in non-development mode
        mock_settings.service_env = "production"
        assert validate_redirect_uri("http://localhost:5001/api/oauth/callback") is False


class TestTokenResponse:
    """Tests for the TokenResponse model."""
    
    def test_token_response_properties(self):
        """Test token response properties."""
        now = datetime.utcnow()
        
        # Create a token response with 1 hour expiration
        token = TokenResponse(
            access_token="test_access_token",
            token_type="Bearer",
            expires_in=3600,  # 1 hour
            refresh_token="test_refresh_token",
            scope="offline_access",
            issued_at=now,
        )
        
        # Check expiration calculation
        expected_expiry = now + timedelta(seconds=3600)
        assert token.expires_at.timestamp() == pytest.approx(expected_expiry.timestamp(), abs=1)
        
        # Not expired
        assert token.is_expired is False
        
        # Almost expired (within the 60-second buffer)
        token.issued_at = now - timedelta(seconds=3550)
        assert token.is_expired is True
        
        # Fully expired
        token.issued_at = now - timedelta(seconds=3700)
        assert token.is_expired is True


class TestTokenExchange:
    """Tests for token exchange functionality."""
    
    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing."""
        with mock.patch("src.auth.oauth.get_settings") as mock_get_settings:
            settings = mock.MagicMock()
            settings.dexcom_api_base_url = "https://sandbox-api.dexcom.com"
            settings.request_timeout_seconds = 30
            mock_get_settings.return_value = settings
            yield settings
            
    @pytest.fixture
    def mock_httpx_client(self):
        """Mock httpx AsyncClient."""
        with mock.patch("httpx.AsyncClient") as mock_client:
            mock_instance = mock.AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            yield mock_instance
    
    @pytest.mark.asyncio
    async def test_exchange_code_for_tokens_success(self, mock_settings, mock_httpx_client):
        """Test successful code exchange."""
        # Mock response
        mock_response = Response(
            status_code=200,
            content=json.dumps({
                "access_token": "test_access_token",
                "token_type": "Bearer",
                "expires_in": 3600,
                "refresh_token": "test_refresh_token",
                "scope": "offline_access",
            }).encode(),
        )
        mock_httpx_client.post.return_value = mock_response
        
        # Call the function
        result = await exchange_code_for_tokens(
            code="test_auth_code",
            code_verifier="test_code_verifier",
            client_id="test_client_id",
            redirect_uri="https://myapp.com/callback",
        )
        
        # Check the result
        assert isinstance(result, TokenResponse)
        assert result.access_token == "test_access_token"
        assert result.token_type == "Bearer"
        assert result.expires_in == 3600
        assert result.refresh_token == "test_refresh_token"
        assert result.scope == "offline_access"
        
        # Check that request was sent correctly
        mock_httpx_client.post.assert_called_once()
        args, kwargs = mock_httpx_client.post.call_args
        assert args[0] == "https://sandbox-api.dexcom.com/v2/oauth2/token"
        assert kwargs["data"]["grant_type"] == "authorization_code"
        assert kwargs["data"]["code"] == "test_auth_code"
        assert kwargs["data"]["code_verifier"] == "test_code_verifier"
        assert kwargs["data"]["client_id"] == "test_client_id"
        assert kwargs["data"]["redirect_uri"] == "https://myapp.com/callback"
        assert "Content-Type" in kwargs["headers"]
        assert kwargs["headers"]["Content-Type"] == "application/x-www-form-urlencoded"
    
    @pytest.mark.asyncio
    async def test_exchange_code_for_tokens_with_client_secret(self, mock_settings, mock_httpx_client):
        """Test code exchange with client secret."""
        # Mock response
        mock_response = Response(
            status_code=200,
            content=json.dumps({
                "access_token": "test_access_token",
                "token_type": "Bearer",
                "expires_in": 3600,
                "refresh_token": "test_refresh_token",
                "scope": "offline_access",
            }).encode(),
        )
        mock_httpx_client.post.return_value = mock_response
        
        # Call the function with client_secret
        await exchange_code_for_tokens(
            code="test_auth_code",
            code_verifier="test_code_verifier",
            client_id="test_client_id",
            redirect_uri="https://myapp.com/callback",
            client_secret="test_client_secret",
        )
        
        # Check client_secret was included
        args, kwargs = mock_httpx_client.post.call_args
        assert kwargs["data"]["client_secret"] == "test_client_secret"
    
    @pytest.mark.asyncio
    async def test_exchange_code_for_tokens_error_response(self, mock_settings, mock_httpx_client):
        """Test error response from token endpoint."""
        # Mock error response
        mock_response = Response(
            status_code=400,
            content=json.dumps({
                "error": "invalid_grant",
                "error_description": "The authorization code is invalid.",
            }).encode(),
        )
        mock_httpx_client.post.return_value = mock_response
        
        # Call the function and expect exception
        with pytest.raises(TokenError) as exc_info:
            await exchange_code_for_tokens(
                code="invalid_code",
                code_verifier="test_code_verifier",
                client_id="test_client_id",
                redirect_uri="https://myapp.com/callback",
            )
        
        # Check exception content
        assert exc_info.value.error == "invalid_grant"
        assert exc_info.value.error_description == "The authorization code is invalid."
        assert exc_info.value.status_code == 400
    
    @pytest.mark.asyncio
    async def test_exchange_code_for_tokens_network_error(self, mock_settings, mock_httpx_client):
        """Test network error during token exchange."""
        # Mock network error
        mock_httpx_client.post.side_effect = httpx.RequestError("Connection error")
        
        # Call the function and expect exception
        with pytest.raises(TokenError) as exc_info:
            await exchange_code_for_tokens(
                code="test_auth_code",
                code_verifier="test_code_verifier",
                client_id="test_client_id",
                redirect_uri="https://myapp.com/callback",
            )
        
        # Check exception content
        assert exc_info.value.error == "network_error"
        assert "Connection error" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_refresh_access_token_success(self, mock_settings, mock_httpx_client):
        """Test successful token refresh."""
        # Mock response
        mock_response = Response(
            status_code=200,
            content=json.dumps({
                "access_token": "new_access_token",
                "token_type": "Bearer",
                "expires_in": 3600,
                "refresh_token": "new_refresh_token",
                "scope": "offline_access",
            }).encode(),
        )
        mock_httpx_client.post.return_value = mock_response
        
        # Call the function
        result = await refresh_access_token(
            refresh_token="old_refresh_token",
            client_id="test_client_id",
        )
        
        # Check the result
        assert isinstance(result, TokenResponse)
        assert result.access_token == "new_access_token"
        assert result.refresh_token == "new_refresh_token"
        
        # Check that request was sent correctly
        mock_httpx_client.post.assert_called_once()
        args, kwargs = mock_httpx_client.post.call_args
        assert args[0] == "https://sandbox-api.dexcom.com/v2/oauth2/token"
        assert kwargs["data"]["grant_type"] == "refresh_token"
        assert kwargs["data"]["refresh_token"] == "old_refresh_token"
        assert kwargs["data"]["client_id"] == "test_client_id"
    
    @pytest.mark.asyncio
    async def test_refresh_access_token_error(self, mock_settings, mock_httpx_client):
        """Test error during token refresh."""
        # Mock error response
        mock_response = Response(
            status_code=400,
            content=json.dumps({
                "error": "invalid_grant",
                "error_description": "The refresh token is invalid or expired.",
            }).encode(),
        )
        mock_httpx_client.post.return_value = mock_response
        
        # Call the function and expect exception
        with pytest.raises(TokenError) as exc_info:
            await refresh_access_token(
                refresh_token="expired_refresh_token",
                client_id="test_client_id",
            )
        
        # Check exception content
        assert exc_info.value.error == "invalid_grant"
        assert "The refresh token is invalid or expired" in exc_info.value.error_description 
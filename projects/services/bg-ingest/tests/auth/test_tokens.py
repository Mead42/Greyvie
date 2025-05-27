"""Tests for the OAuth2 token service."""
import json
from datetime import datetime, timedelta
from unittest import mock

import pytest
from pydantic import SecretStr

from src.auth.oauth import TokenResponse, TokenError
from src.auth.tokens import (
    store_token,
    get_token,
    refresh_token,
    delete_token,
    get_tokens_needing_refresh,
    exchange_code_and_store,
)
from src.models.tokens import UserToken, TokenProvider, TokenType


@pytest.fixture
def mock_token_repository():
    """Mock the token repository for testing."""
    with mock.patch("src.auth.tokens.get_token_repository") as mock_get_repo:
        mock_repo = mock.MagicMock()
        mock_get_repo.return_value = mock_repo
        yield mock_repo


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    with mock.patch("src.auth.tokens.settings", autospec=True) as mock_settings:
        mock_settings.dexcom_client_id = "test_client_id"
        mock_settings.dexcom_client_secret = mock.MagicMock()
        mock_settings.dexcom_client_secret.get_secret_value.return_value = "test_client_secret"
        mock_settings.dexcom_redirect_uri = "https://myapp.com/callback"
        yield mock_settings


@pytest.fixture
def mock_exchange_code():
    """Mock the exchange_code_for_tokens function."""
    with mock.patch("src.auth.tokens.exchange_code_for_tokens") as mock_exchange:
        # Create a token response for successful exchange
        token_response = TokenResponse(
            access_token="test_access_token",
            token_type="Bearer",
            expires_in=3600,
            refresh_token="test_refresh_token",
            scope="offline_access",
            issued_at=datetime.utcnow(),
        )
        mock_exchange.return_value = token_response
        yield mock_exchange


@pytest.fixture
def mock_refresh_access_token():
    """Mock the refresh_access_token function."""
    with mock.patch("src.auth.tokens.refresh_access_token") as mock_refresh:
        # Create a token response for successful refresh
        token_response = TokenResponse(
            access_token="new_access_token",
            token_type="Bearer",
            expires_in=3600,
            refresh_token="new_refresh_token",
            scope="offline_access",
            issued_at=datetime.utcnow(),
        )
        mock_refresh.return_value = token_response
        yield mock_refresh


def create_mock_token(user_id, provider_value, access_token_value, refresh_token_value=None, expired=False):
    """Helper to create a UserToken instance for testing."""
    # For expired tokens, we need to use mocks since Pydantic validation won't allow expired dates
    if expired:
        mock_token = mock.MagicMock()
        mock_token.user_id = user_id
        mock_token.provider = TokenProvider.DEXCOM if provider_value == "dexcom" else TokenProvider.INTERNAL
        
        # Create nested mocks for the SecretStr attributes
        mock_access_token = mock.MagicMock(spec=SecretStr)
        mock_access_token.get_secret_value.return_value = access_token_value
        mock_token.access_token = mock_access_token
        
        if refresh_token_value:
            mock_refresh_token = mock.MagicMock(spec=SecretStr)
            mock_refresh_token.get_secret_value.return_value = refresh_token_value
            mock_token.refresh_token = mock_refresh_token
        else:
            mock_token.refresh_token = None
        
        # Set expiration in the past
        mock_token.expires_at = datetime.utcnow() - timedelta(minutes=5)
        mock_token.is_expired = mock.MagicMock(return_value=True)
        
        mock_token.scope = "offline_access"
        mock_token.created_at = datetime.utcnow() - timedelta(days=1)
        mock_token.updated_at = datetime.utcnow()
        mock_token.token_type = TokenType.OAUTH
        
        return mock_token
    else:
        # For non-expired tokens, create an actual UserToken instance
        expires_at = datetime.utcnow() + timedelta(hours=1)
        
        # Create a real UserToken instance with valid values
        token = UserToken(
            user_id=user_id,
            provider=TokenProvider.DEXCOM if provider_value == "dexcom" else TokenProvider.INTERNAL,
            access_token=SecretStr(access_token_value),
            refresh_token=SecretStr(refresh_token_value) if refresh_token_value else None,
            token_type=TokenType.OAUTH,  # Use enum value instead of "Bearer"
            expires_at=expires_at,
            scope="offline_access",
            created_at=datetime.utcnow() - timedelta(days=1),
            updated_at=datetime.utcnow()
        )
        
        return token


class TestTokenService:
    """Tests for the token service."""
    
    @pytest.mark.asyncio
    async def test_store_token_new(self, mock_token_repository):
        """Test storing a new token."""
        # Setup
        user_id = "test_user"
        token_response = TokenResponse(
            access_token="test_access_token",
            token_type="Bearer",
            expires_in=3600,
            refresh_token="test_refresh_token",
            scope="offline_access",
            issued_at=datetime.utcnow(),
        )
        
        # Mock repo to return None (no existing token)
        mock_token_repository.get_by_user_and_provider.return_value = None
        
        # Test store_token
        result = await store_token(user_id, token_response, TokenProvider.DEXCOM)
        
        # Verify
        assert result is not None
        mock_token_repository.create.assert_called_once()
        created_token = mock_token_repository.create.call_args[0][0]
        assert created_token.user_id == user_id
        assert created_token.provider == TokenProvider.DEXCOM
        assert created_token.access_token.get_secret_value() == "test_access_token"
        assert created_token.refresh_token.get_secret_value() == "test_refresh_token"
        assert created_token.scope == "offline_access"
    
    @pytest.mark.asyncio
    async def test_store_token_update(self, mock_token_repository):
        """Test updating an existing token."""
        # Setup
        user_id = "test_user"
        token_response = TokenResponse(
            access_token="new_access_token",
            token_type="Bearer",
            expires_in=3600,
            refresh_token="new_refresh_token",
            scope="offline_access",
            issued_at=datetime.utcnow(),
        )
        
        # Create a properly mocked existing token
        existing_token = create_mock_token(
            user_id=user_id,
            provider_value="dexcom",
            access_token_value="old_access_token",
            refresh_token_value="old_refresh_token"
        )
        
        mock_token_repository.get_by_user_and_provider.return_value = existing_token
        
        # Test store_token
        result = await store_token(user_id, token_response, TokenProvider.DEXCOM)
        
        # Verify
        assert result is not None
        mock_token_repository.update.assert_called_once()
        updated_token = mock_token_repository.update.call_args[0][0]
        assert updated_token.user_id == user_id
        assert updated_token.provider == TokenProvider.DEXCOM
        assert updated_token.access_token.get_secret_value() == "new_access_token"
        assert updated_token.refresh_token.get_secret_value() == "new_refresh_token"
        
        # Verify created_at was preserved
        assert updated_token.created_at == existing_token.created_at
    
    @pytest.mark.asyncio
    async def test_get_token_found(self, mock_token_repository):
        """Test getting a token that exists and is valid."""
        # Setup
        user_id = "test_user"
        
        # Create a properly mocked token
        existing_token = create_mock_token(
            user_id=user_id,
            provider_value="dexcom",
            access_token_value="test_access_token", 
            refresh_token_value="test_refresh_token"
        )
        
        mock_token_repository.get_by_user_and_provider.return_value = existing_token
        
        # Test get_token
        result = await get_token(user_id, TokenProvider.DEXCOM)
        
        # Verify
        assert result == existing_token
        # No auto-refresh should have happened
        
    @pytest.mark.asyncio
    async def test_get_token_expired_with_auto_refresh(self, mock_token_repository):
        """Test getting an expired token with auto refresh enabled."""
        # Setup
        user_id = "test_user"
        provider = TokenProvider.DEXCOM
        
        # Create a properly mocked expired token
        expired_token = create_mock_token(
            user_id=user_id,
            provider_value="dexcom",
            access_token_value="expired_access_token", 
            refresh_token_value="test_refresh_token",
            expired=True
        )
        
        mock_token_repository.get_by_user_and_provider.return_value = expired_token
        
        # Create a properly mocked refreshed token
        refreshed_token = create_mock_token(
            user_id=user_id,
            provider_value="dexcom",
            access_token_value="new_access_token", 
            refresh_token_value="new_refresh_token"
        )
        
        # Setup the refresh_token mock to return the refreshed token
        with mock.patch("src.auth.tokens.refresh_token") as mock_refresh_func:
            mock_refresh_func.return_value = refreshed_token
            
            # Test get_token with auto_refresh=True
            result = await get_token(user_id, provider, auto_refresh=True)
            
            # Verify
            assert result == refreshed_token
            mock_refresh_func.assert_called_once_with(user_id, provider)
    
    @pytest.mark.asyncio
    async def test_get_token_expired_without_auto_refresh(self, mock_token_repository):
        """Test getting an expired token with auto refresh disabled."""
        # Setup
        user_id = "test_user"
        
        # Create a properly mocked expired token
        expired_token = create_mock_token(
            user_id=user_id,
            provider_value="dexcom",
            access_token_value="expired_access_token", 
            refresh_token_value="test_refresh_token",
            expired=True
        )
        
        mock_token_repository.get_by_user_and_provider.return_value = expired_token
        
        # Test get_token with auto_refresh=False
        result = await get_token(user_id, TokenProvider.DEXCOM, auto_refresh=False)
        
        # Verify that we got the expired token without attempting to refresh it
        assert result == expired_token
    
    @pytest.mark.asyncio
    async def test_refresh_token_success(self, mock_token_repository, mock_settings, mock_refresh_access_token):
        """Test successfully refreshing a token."""
        # Setup
        user_id = "test_user"
        provider = TokenProvider.DEXCOM
        
        # Create a token with a refresh token
        token = create_mock_token(
            user_id=user_id,
            provider_value="dexcom",
            access_token_value="old_access_token", 
            refresh_token_value="test_refresh_token"
        )
        
        mock_token_repository.get_by_user_and_provider.return_value = token
        
        # Mock storing the refreshed token
        with mock.patch("src.auth.tokens.store_token") as mock_store:
            # Create the expected refreshed token
            refreshed_token = create_mock_token(
                user_id=user_id,
                provider_value="dexcom",
                access_token_value="new_access_token", 
                refresh_token_value="new_refresh_token"
            )
            
            mock_store.return_value = refreshed_token
            
            # Test refresh_token
            result = await refresh_token(user_id, provider)
            
            # Verify
            assert result == refreshed_token
            
            # Check that refresh_access_token was called with the right parameters
            mock_refresh_access_token.assert_called_once()
            call_args = mock_refresh_access_token.call_args[1]
            assert call_args["refresh_token"] == "test_refresh_token"
            
            # Verify that store_token was called
            mock_store.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_refresh_token_no_token(self, mock_token_repository):
        """Test refreshing when no token exists."""
        # Setup
        user_id = "test_user"
        provider = TokenProvider.DEXCOM
        
        # Mock no token found
        mock_token_repository.get_by_user_and_provider.return_value = None
        
        # Test refresh_token
        result = await refresh_token(user_id, provider)
        
        # Verify
        assert result is None
    
    @pytest.mark.asyncio
    async def test_refresh_token_no_refresh_token(self, mock_token_repository):
        """Test refreshing a token that has no refresh token."""
        # Setup
        user_id = "test_user"
        provider = TokenProvider.DEXCOM
        
        # Create a properly mocked token without a refresh token
        token = create_mock_token(
            user_id=user_id,
            provider_value="dexcom",
            access_token_value="access_token", 
            refresh_token_value=None
        )
        
        mock_token_repository.get_by_user_and_provider.return_value = token
        
        # Test refresh_token
        result = await refresh_token(user_id, provider)
        
        # Verify
        assert result is None
    
    @pytest.mark.asyncio
    async def test_refresh_token_error(self, mock_token_repository, mock_refresh_access_token):
        """Test handling errors during token refresh."""
        # Setup
        user_id = "test_user"
        provider = TokenProvider.DEXCOM
        
        # Create a properly mocked token with a refresh token
        token = create_mock_token(
            user_id=user_id,
            provider_value="dexcom",
            access_token_value="old_access_token", 
            refresh_token_value="test_refresh_token"
        )
        
        mock_token_repository.get_by_user_and_provider.return_value = token
        
        # Mock refresh_access_token to raise an error
        mock_refresh_access_token.side_effect = TokenError("invalid_grant", "The refresh token is invalid")
        
        # Test refresh_token
        with pytest.raises(TokenError) as exc_info:
            await refresh_token(user_id, provider)
        
        # Verify
        assert "refresh_failed" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_delete_token(self, mock_token_repository):
        """Test deleting a token."""
        # Setup
        user_id = "test_user"
        provider = TokenProvider.DEXCOM
        
        # Mock successful deletion
        mock_token_repository.delete.return_value = True
        
        # Test delete_token
        result = await delete_token(user_id, provider)
        
        # Verify
        assert result is True
        mock_token_repository.delete.assert_called_once_with(user_id, provider)
    
    @pytest.mark.asyncio
    async def test_get_tokens_needing_refresh(self, mock_token_repository):
        """Test getting tokens that need refresh."""
        # Setup - create properly mocked tokens
        token1 = create_mock_token(
            user_id="user1",
            provider_value="dexcom",
            access_token_value="token1", 
            refresh_token_value="refresh1",
            expired=True
        )
        
        # Create a token that expires soon (5 minutes)
        token2 = create_mock_token(
            user_id="user2",
            provider_value="dexcom",
            access_token_value="token2", 
            refresh_token_value="refresh2"
        )
        # Adjust expires_at to be soon but not expired
        token2.expires_at = datetime.utcnow() + timedelta(minutes=5)
        
        # Create a token without a refresh token
        token3 = create_mock_token(
            user_id="user3",
            provider_value="dexcom",
            access_token_value="token3", 
            refresh_token_value=None
        )
        # Adjust expires_at to be soon but not expired
        token3.expires_at = datetime.utcnow() + timedelta(minutes=5)
        
        # Create a token that expires far in the future
        token4 = create_mock_token(
            user_id="user4",
            provider_value="dexcom",
            access_token_value="token4", 
            refresh_token_value="refresh4"
        )
        # Adjust expires_at to be far in the future
        token4.expires_at = datetime.utcnow() + timedelta(hours=2)
        
        # Prepare the tokens for the mock repository
        mock_token_repository.get_expired_tokens.return_value = [token1, token2, token3, token4]
        
        # Mock datetime.utcnow to return a consistent value
        with mock.patch("src.auth.tokens.datetime") as mock_datetime:
            now = datetime.utcnow()
            mock_datetime.utcnow.return_value = now
            
            # Test get_tokens_needing_refresh with 10-minute threshold
            result = await get_tokens_needing_refresh(threshold_minutes=10)
            
            # Verify based on our mocked objects
            assert "user1" in result  # Already expired
            assert "user2" in result  # Expires within 10 minutes
            assert "user3" not in result  # No refresh token
            assert "user4" not in result  # Not expiring soon (2 hours)
    
    @pytest.mark.asyncio
    async def test_exchange_code_and_store(self, mock_exchange_code, mock_settings):
        """Test exchanging code and storing tokens."""
        # Setup
        user_id = "test_user"
        code = "test_auth_code"
        code_verifier = "test_code_verifier"
        provider = TokenProvider.DEXCOM
        
        # Mock storing the token
        with mock.patch("src.auth.tokens.store_token") as mock_store:
            # Create the expected token to be stored
            expected_token = create_mock_token(
                user_id=user_id,
                provider_value="dexcom",
                access_token_value="stored_access_token", 
                refresh_token_value="stored_refresh_token"
            )
            
            mock_store.return_value = expected_token
            
            # Test exchange_code_and_store
            result = await exchange_code_and_store(user_id, code, code_verifier, provider)
            
            # Verify
            assert result == expected_token
            
            # Verify exchange_code_for_tokens was called
            mock_exchange_code.assert_called_once()
            call_args = mock_exchange_code.call_args[1]
            assert call_args["code"] == code
            assert call_args["code_verifier"] == code_verifier
            
            # Verify store_token was called
            mock_store.assert_called_once() 

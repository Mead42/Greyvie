"""
OAuth2 token management and storage service.

This module provides functionality for securely storing, retrieving,
and refreshing OAuth tokens using the token repository.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Any

from pydantic import SecretStr

from src.auth.oauth import TokenResponse, exchange_code_for_tokens, refresh_access_token, TokenError
from src.data.token_repository import get_token_repository
from src.models.tokens import UserToken, TokenProvider
from src.utils.config import get_settings


logger = logging.getLogger(__name__)
settings = get_settings()


async def store_token(
    user_id: str,
    token_response: TokenResponse,
    provider: TokenProvider = TokenProvider.DEXCOM,
) -> UserToken:
    """
    Store an OAuth token in the repository.
    
    Args:
        user_id: The user's ID
        token_response: The OAuth token response to store
        provider: The token provider (defaults to Dexcom)
        
    Returns:
        UserToken: The stored token model
    """
    # Create a UserToken object from the TokenResponse
    token = UserToken(
        user_id=user_id,
        provider=provider,
        access_token=SecretStr(token_response.access_token),
        refresh_token=SecretStr(token_response.refresh_token) if token_response.refresh_token else None,
        expires_at=token_response.expires_at,
        scope=token_response.scope,
    )
    
    # Get the repository and store the token
    repo = get_token_repository()
    
    # Check if a token already exists for this user and provider
    existing_token = repo.get_by_user_and_provider(user_id, provider)
    if existing_token:
        # Update existing token
        token.created_at = existing_token.created_at  # Preserve original creation date
        return repo.update(token)
    else:
        # Create new token
        return repo.create(token)


async def get_token(
    user_id: str,
    provider: TokenProvider = TokenProvider.DEXCOM,
    auto_refresh: bool = True,
) -> Optional[UserToken]:
    """
    Get an OAuth token from the repository, optionally refreshing it if expired.
    
    Args:
        user_id: The user's ID
        provider: The token provider (defaults to Dexcom)
        auto_refresh: Whether to automatically refresh the token if it's expired
        
    Returns:
        Optional[UserToken]: The token, or None if not found
    """
    repo = get_token_repository()
    token = repo.get_by_user_and_provider(user_id, provider)
    
    if not token:
        return None
    
    # Check if token is expired and auto_refresh is enabled
    if auto_refresh and token.is_expired() and (token.refresh_token is not None):
        try:
            # Refresh the token
            refreshed_token = await refresh_token(user_id, provider)
            # Only return the refreshed token if we actually got one back
            if refreshed_token:
                return refreshed_token
        except TokenError as e:
            logger.error(f"Failed to refresh token for user {user_id}: {str(e)}")
            # Return the expired token, let the caller handle it
    
    return token


async def refresh_token(
    user_id: str,
    provider: TokenProvider = TokenProvider.DEXCOM,
) -> Optional[UserToken]:
    """
    Refresh an OAuth token and update it in the repository.
    
    Args:
        user_id: The user's ID
        provider: The token provider (defaults to Dexcom)
        
    Returns:
        Optional[UserToken]: The refreshed token, or None if token not found or refresh failed
        
    Raises:
        TokenError: If the token refresh fails
    """
    repo = get_token_repository()
    token = repo.get_by_user_and_provider(user_id, provider)
    
    if not token:
        logger.warning(f"No token found for user {user_id} and provider {provider}")
        return None
    
    if token.refresh_token is None:
        logger.warning(f"No refresh token available for user {user_id} and provider {provider}")
        return None
    
    # Use the refresh token to get a new access token
    refresh_token_value = token.refresh_token.get_secret_value()
    
    # Get client credentials from settings
    client_id = settings.dexcom_client_id
    client_secret = settings.dexcom_client_secret.get_secret_value() if settings.dexcom_client_secret else None
    
    try:
        # Refresh the token
        token_response = await refresh_access_token(
            refresh_token=refresh_token_value,
            client_id=client_id,
            client_secret=client_secret,
        )
        
        # Store the refreshed token
        return await store_token(user_id, token_response, provider)
    except Exception as e:
        logger.error(f"Failed to refresh token for user {user_id}: {str(e)}")
        raise TokenError("refresh_failed", str(e))


async def delete_token(
    user_id: str,
    provider: TokenProvider = TokenProvider.DEXCOM,
) -> bool:
    """
    Delete a token from the repository.
    
    Args:
        user_id: The user's ID
        provider: The token provider (defaults to Dexcom)
        
    Returns:
        bool: True if the token was deleted successfully, False otherwise
    """
    repo = get_token_repository()
    try:
        result = repo.delete(user_id, provider)
        logger.info(f"Deleted token for user {user_id} and provider {provider}")
        return result
    except Exception as e:
        logger.error(f"Failed to delete token for user {user_id} and provider {provider}: {str(e)}")
        return False


async def get_tokens_needing_refresh(threshold_minutes: int = 10) -> Dict[str, Dict[str, UserToken]]:
    """
    Get tokens that need to be refreshed soon.
    
    Args:
        threshold_minutes: The number of minutes before expiration to consider a token as needing refresh
        
    Returns:
        Dict[str, Dict[str, UserToken]]: A dictionary of tokens needing refresh, keyed by user_id and then provider
    """
    repo = get_token_repository()
    
    # Get all tokens from the repository
    all_tokens = repo.get_expired_tokens()
    
    # Group tokens by user_id and provider
    result: Dict[str, Dict[str, UserToken]] = {}
    now = datetime.utcnow()
    threshold = now + timedelta(minutes=threshold_minutes)
    
    for token in all_tokens:
        # Skip tokens without refresh tokens
        if token.refresh_token is None:
            continue
        
        # Include tokens that are either already expired or will expire soon
        if token.expires_at <= threshold:
            # Initialize the user entry if it doesn't exist
            if token.user_id not in result:
                result[token.user_id] = {}
            
            # Add the token to the result
            result[token.user_id][token.provider.value] = token
    
    return result


async def exchange_code_and_store(
    user_id: str,
    code: str,
    code_verifier: str,
    provider: TokenProvider = TokenProvider.DEXCOM,
) -> UserToken:
    """
    Exchange an authorization code for tokens and store them.
    
    Args:
        user_id: The user's ID
        code: The authorization code from the OAuth callback
        code_verifier: The PKCE code verifier used in the initial authorization request
        provider: The token provider (defaults to Dexcom)
        
    Returns:
        UserToken: The stored token
        
    Raises:
        TokenError: If the token exchange fails
    """
    # Get client credentials from settings
    client_id = settings.dexcom_client_id
    client_secret = settings.dexcom_client_secret.get_secret_value() if settings.dexcom_client_secret else None
    redirect_uri = settings.dexcom_redirect_uri
    
    # Exchange the code for tokens
    token_response = await exchange_code_for_tokens(
        code=code,
        code_verifier=code_verifier,
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
    )
    
    # Store the tokens
    return await store_token(user_id, token_response, provider) 
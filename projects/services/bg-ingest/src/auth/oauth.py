"""
OAuth2 implementation for Dexcom API.

This module provides functions for building OAuth2 authorization URLs
and handling the OAuth2 flow with the Dexcom API.
"""
import logging
import urllib.parse
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

import httpx
from pydantic import BaseModel, Field

from src.utils.config import get_settings


class TokenResponse(BaseModel):
    """OAuth2 token response model."""
    
    access_token: str
    token_type: str
    expires_in: int
    refresh_token: Optional[str] = None
    scope: str
    
    # Add computed fields for expiration tracking
    issued_at: datetime = Field(default_factory=datetime.utcnow)
    
    @property
    def expires_at(self) -> datetime:
        """Calculate when the token will expire."""
        return self.issued_at + timedelta(seconds=self.expires_in)
    
    @property
    def is_expired(self) -> bool:
        """Check if the token is expired."""
        # Add a 60-second buffer to account for latency
        buffer_time = timedelta(seconds=60)
        return datetime.utcnow() >= (self.expires_at - buffer_time)


class TokenError(Exception):
    """Exception raised when token exchange fails."""
    
    def __init__(self, error: str, error_description: Optional[str] = None, status_code: Optional[int] = None):
        """Initialize the exception."""
        self.error = error
        self.error_description = error_description
        self.status_code = status_code
        message = f"Token error: {error}"
        if error_description:
            message += f" - {error_description}"
        super().__init__(message)


def build_dexcom_auth_url(
    client_id: str,
    redirect_uri: str,
    state: str,
    code_challenge: str,
    scope: Optional[Union[str, List[str]]] = None,
) -> str:
    """
    Build an OAuth2 authorization URL for Dexcom API with PKCE.
    
    Args:
        client_id: The OAuth2 client ID
        redirect_uri: The redirect URI after authorization
        state: A random state parameter for CSRF protection
        code_challenge: PKCE code challenge derived from code verifier
        scope: Optional scope(s) to request, defaults to ['offline_access']
        
    Returns:
        str: The complete authorization URL
        
    Notes:
        - The state parameter should be a random value that is verifiable by your app
        - The code_challenge is created using the S256 method 
        - Always validate that the redirect_uri matches your registered URIs
    """
    # Get settings
    settings = get_settings()
    
    # Create base URL
    base_url = f"{settings.dexcom_api_base_url}/v2/oauth2/login"
    
    # Process scope parameter
    if scope is None:
        scope = ["offline_access"]  # Default scope for refresh tokens
    elif isinstance(scope, str):
        scope = [s.strip() for s in scope.split(' ')]
    
    # Build query parameters
    params: Dict[str, str] = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(scope),
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    
    # URL encode parameters and build the full URL
    encoded_params = urllib.parse.urlencode(params)
    authorization_url = f"{base_url}?{encoded_params}"
    
    return authorization_url


async def exchange_code_for_tokens(
    code: str,
    code_verifier: str,
    client_id: str,
    redirect_uri: str,
    client_secret: Optional[str] = None,
) -> TokenResponse:
    """
    Exchange authorization code for access and refresh tokens.
    
    Args:
        code: Authorization code from the callback
        code_verifier: PKCE code verifier used to generate the challenge
        client_id: OAuth2 client ID
        redirect_uri: Redirect URI that was used for authorization
        client_secret: Optional client secret for confidential clients
        
    Returns:
        TokenResponse: Object containing the token response data
        
    Raises:
        TokenError: If the token exchange failed
        httpx.HTTPError: If there was an HTTP-level error
        
    Notes:
        - Always use HTTPS for token exchange
        - Validate and store tokens securely
        - Handle refresh tokens with special care
    """
    settings = get_settings()
    
    # Prepare the token request data
    token_url = f"{settings.dexcom_api_base_url}/v2/oauth2/token"
    
    # Build request data
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "code_verifier": code_verifier,
    }
    
    # Add client secret if provided (for confidential clients)
    if client_secret:
        data["client_secret"] = client_secret
    
    # Set headers including maximum timeout
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
    }
    
    # Set timeout
    timeout = httpx.Timeout(settings.request_timeout_seconds)
    
    try:
        # Make the token request
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(token_url, data=data, headers=headers)
            
            # Handle error responses
            if response.status_code != 200:
                try:
                    error_data = response.json()
                    error = error_data.get("error", "unknown_error")
                    error_description = error_data.get("error_description")
                    raise TokenError(error, error_description, response.status_code)
                except (ValueError, KeyError):
                    # If unable to parse error JSON
                    raise TokenError(
                        "invalid_response", 
                        f"Received status {response.status_code}", 
                        response.status_code
                    )
            
            # Parse response
            token_data = response.json()
            try:
                # Create token response object
                return TokenResponse(**token_data)
            except Exception as e:
                logging.error(f"Failed to parse token response: {str(e)}")
                raise TokenError("invalid_response", f"Failed to parse token response: {str(e)}")
                
    except httpx.RequestError as e:
        # Handle network errors
        logging.error(f"Network error during token exchange: {str(e)}")
        raise TokenError("network_error", f"Request failed: {str(e)}")


async def refresh_access_token(
    refresh_token: str,
    client_id: str,
    client_secret: Optional[str] = None,
) -> TokenResponse:
    """
    Refresh an access token using a refresh token.
    
    Args:
        refresh_token: The refresh token
        client_id: OAuth2 client ID
        client_secret: Optional client secret for confidential clients
        
    Returns:
        TokenResponse: Object containing the new token data
        
    Raises:
        TokenError: If the token refresh failed
        httpx.HTTPError: If there was an HTTP-level error
    """
    settings = get_settings()
    
    # Prepare the token request data
    token_url = f"{settings.dexcom_api_base_url}/v2/oauth2/token"
    
    # Build request data
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
    }
    
    # Add client secret if provided (for confidential clients)
    if client_secret:
        data["client_secret"] = client_secret
    
    # Set headers
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
    }
    
    # Set timeout
    timeout = httpx.Timeout(settings.request_timeout_seconds)
    
    try:
        # Make the token request
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(token_url, data=data, headers=headers)
            
            # Handle error responses
            if response.status_code != 200:
                try:
                    error_data = response.json()
                    error = error_data.get("error", "unknown_error")
                    error_description = error_data.get("error_description")
                    raise TokenError(error, error_description, response.status_code)
                except (ValueError, KeyError):
                    # If unable to parse error JSON
                    raise TokenError(
                        "invalid_response", 
                        f"Received status {response.status_code}", 
                        response.status_code
                    )
            
            # Parse response
            token_data = response.json()
            try:
                # Create token response object
                return TokenResponse(**token_data)
            except Exception as e:
                logging.error(f"Failed to parse token response: {str(e)}")
                raise TokenError("invalid_response", f"Failed to parse token response: {str(e)}")
                
    except httpx.RequestError as e:
        # Handle network errors
        logging.error(f"Network error during token refresh: {str(e)}")
        raise TokenError("network_error", f"Request failed: {str(e)}")


def validate_redirect_uri(redirect_uri: str) -> bool:
    """
    Validate that a redirect URI is allowed.
    
    Args:
        redirect_uri: The redirect URI to validate
        
    Returns:
        bool: True if the redirect URI is allowed, False otherwise
        
    Notes:
        - This helps prevent open redirector vulnerabilities
        - Always maintain a whitelist of valid redirect URIs
    """
    settings = get_settings()
    
    # Use configured redirect URI as a safeguard
    allowed_uris = [settings.dexcom_redirect_uri]
    
    # Add development URLs if in development mode
    if settings.service_env == "development":
        allowed_uris.extend([
            "http://localhost:5001/api/oauth/callback",
            "http://localhost:3000/callback",
        ])
    
    return redirect_uri in allowed_uris 
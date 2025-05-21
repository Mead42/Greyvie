"""OAuth2 API client for Dexcom (CGM) API.

This client wraps authenticated HTTPS requests to Dexcom endpoints and
handles all OAuth2 token management concerns (PKCE, exchange, refresh)
internally so callers can focus on business logic.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

import httpx
from pydantic import SecretStr

from src.auth.oauth import build_dexcom_auth_url, exchange_code_for_tokens
from src.auth.pkce import generate_pkce_pair
from src.auth.tokens import (
    get_token,
    store_token,
    TokenError,
)
from src.models.tokens import TokenProvider, UserToken
from src.utils.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

__all__ = [
    "DexcomClient",
    "DexcomAPIError",
    "DexcomAuthError",
    "exchange_code_and_store",  # re-export so tests can patch it directly
]


class DexcomAPIError(Exception):
    """Non-authentication related error returned by Dexcom API."""

    def __init__(self, message: str, status_code: int | None = None, response_body: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class DexcomAuthError(DexcomAPIError):
    """Error raised when authentication or token issues occur."""


# ---------------------------------------------------------------------------
# Helper used by tests (patched via `patch("src.auth.client.exchange_code_and_store", ...)`)
# ---------------------------------------------------------------------------
async def exchange_code_and_store(*, user_id: str, code: str, code_verifier: str, provider: TokenProvider) -> UserToken:  # noqa: D401,E501
    """Exchange *code* for tokens then persist and return a `UserToken` instance."""

    token_response = await exchange_code_for_tokens(
        code=code,
        code_verifier=code_verifier,
        client_id=settings.dexcom_client_id,
        client_secret=settings.dexcom_client_secret,
        redirect_uri=settings.dexcom_redirect_uri,
    )

    return await store_token(user_id=user_id, token_response=token_response, provider=provider)


# ---------------------------------------------------------------------------
# Primary client implementation
# ---------------------------------------------------------------------------
class DexcomClient:
    """High-level async OAuth2 client for Dexcom endpoints."""

    def __init__(
        self,
        user_id: str,
        *,
        base_url: str = "https://api.dexcom.com",
        provider: TokenProvider = TokenProvider.DEXCOM,
    ) -> None:
        self.user_id = user_id
        self.base_url = base_url.rstrip("/")
        self.provider = provider
        self.client_id = settings.dexcom_client_id
        self.redirect_uri = settings.dexcom_redirect_uri
        self.http_client = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)

    # ---------------------- async context manager helpers ------------------
    async def __aenter__(self) -> "DexcomClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        await self.close()

    async def close(self) -> None:
        """Close underlying HTTPX client."""
        await self.http_client.aclose()

    # ---------------------- OAuth2 helper operations -----------------------
    async def initiate_authorization(self, state: str | None = None) -> Dict[str, str]:
        """Generate PKCE codes and return data for the front-end redirect step."""
        code_verifier, code_challenge = generate_pkce_pair()
        auth_url = build_dexcom_auth_url(
            client_id=settings.dexcom_client_id,
            redirect_uri=settings.dexcom_redirect_uri,
            state=state,
            code_challenge=code_challenge,
        )
        return {
            "authorization_url": auth_url,
            "code_verifier": code_verifier,
            "state": state,
        }

    async def handle_callback(self, code: str, code_verifier: str) -> UserToken:  # noqa: D401
        """Exchange auth *code* for tokens and persist them."""
        try:
            return await exchange_code_and_store(
                user_id=self.user_id,
                code=code,
                code_verifier=code_verifier,
                provider=self.provider,
            )
        except TokenError as exc:  # pragma: no cover – wrapped for tests
            raise DexcomAuthError("Failed to exchange code for tokens") from exc

    # ---------------------- token utilities -------------------------------
    async def _get_auth_header(self) -> Dict[str, str]:
        token = await get_token(self.user_id, provider=self.provider, auto_refresh=True)
        if token is None:
            raise DexcomAuthError("No valid token available")
        if token.is_expired():
            raise DexcomAuthError("Token is expired")
        return {"Authorization": f"Bearer {token.access_token.get_secret_value()}"}

    # ---------------------- HTTP request helpers --------------------------
    async def _make_request(self, method: str, endpoint: str, **kwargs: Any) -> httpx.Response:  # noqa: D401
        headers = kwargs.pop("headers", {})
        headers.update(await self._get_auth_header())
        try:
            resp = await self.http_client.request(method, endpoint, headers=headers, **kwargs)
        except httpx.RequestError as exc:
            raise DexcomAPIError("Request failed") from exc

        if resp.status_code == 401:
            raise DexcomAuthError("Authentication failed", status_code=resp.status_code, response_body=resp.text)
        if not resp.is_success:
            raise DexcomAPIError("API request failed", status_code=resp.status_code, response_body=resp.text)
        return resp

    # Convenience wrappers -------------------------------------------------
    async def get(self, endpoint: str, **kwargs: Any) -> httpx.Response:  # noqa: D401
        return await self._make_request("GET", endpoint, **kwargs)

    async def post(self, endpoint: str, **kwargs: Any) -> httpx.Response:
        return await self._make_request("POST", endpoint, **kwargs)

    async def put(self, endpoint: str, **kwargs: Any) -> httpx.Response:
        return await self._make_request("PUT", endpoint, **kwargs)

    async def delete(self, endpoint: str, **kwargs: Any) -> httpx.Response:
        return await self._make_request("DELETE", endpoint, **kwargs)

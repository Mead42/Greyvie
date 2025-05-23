import random
import httpx
from typing import Optional, Type, TypeVar, List
from datetime import datetime, timedelta
from src.auth.models import GlucoseReading
from src.auth.rate_limiter import AsyncRateLimiter
import asyncio
import logging

T = TypeVar('T')

class DexcomApiClient:
    """
    Dexcom API client with OAuth2, request handling, response parsing, rate limiting, and retry logic.
    All API calls are rate-limited using a token bucket algorithm.
    - Sandbox: 100 calls per 60s (default)
    - Production: 1000 calls per 60s (default, adjust as needed)
    Limits can be overridden via constructor.
    Supports retry with exponential backoff and jitter for transient errors.
    """
    def __init__(self, base_url: str, client_id: str, client_secret: str, sandbox: bool = True, max_calls: Optional[int] = None, period: Optional[int] = None, max_retries: int = 3, base_delay: float = 0.5):
        """
        Initialize the Dexcom API client.
        :param base_url: Dexcom API base URL (sandbox or production)
        :param client_id: OAuth2 client ID
        :param client_secret: OAuth2 client secret
        :param sandbox: Use sandbox environment if True
        :param max_calls: Maximum number of calls per period
        :param period: Period in seconds
        :param max_retries: Maximum number of retry attempts
        :param base_delay: Base delay between retry attempts in seconds
        """
        self.base_url = base_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.sandbox = sandbox
        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None
        self._client = httpx.AsyncClient()
        # Set rate limits based on environment if not provided
        if max_calls is None:
            max_calls = 100 if sandbox else 1000  # Adjust production limit as needed
        if period is None:
            period = 60
        self.rate_limiter = AsyncRateLimiter(max_calls=max_calls, period=period)
        self.max_retries = max_retries
        self.base_delay = base_delay

    def get_authorization_url(self, redirect_uri: str, state: Optional[str] = None) -> str:
        """
        Generate the Dexcom OAuth2 authorization URL for user login and consent.
        :param redirect_uri: The redirect URI registered with Dexcom
        :param state: Optional state parameter for CSRF protection
        :return: The full authorization URL
        """
        base = "https://sandbox-api.dexcom.com" if self.sandbox else "https://api.dexcom.com"
        url = f"{base}/v2/oauth2/login?client_id={self.client_id}&redirect_uri={redirect_uri}&response_type=code&scope=offline_access"
        if state:
            url += f"&state={state}"
        return url

    async def authenticate(self, authorization_code: str, redirect_uri: str):
        """
        Exchange the authorization code for an access token and refresh token.
        Store tokens and expiry on success.
        Raise httpx.HTTPStatusError on failure.
        """
        token_url = f"{self.base_url}/v2/oauth2/token"
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": authorization_code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        response = await self._client.post(token_url, data=data, headers=headers)
        if response.status_code != 200:
            raise httpx.HTTPStatusError(f"Dexcom token exchange failed: {response.text}", request=response.request, response=response)
        token_data = await response.json()
        self._access_token = token_data["access_token"]
        self._refresh_token = token_data["refresh_token"]
        self._token_expiry = datetime.utcnow() + timedelta(seconds=token_data["expires_in"])
        return token_data

    async def refresh_access_token(self, refresh_token: Optional[str] = None):
        """
        Use the refresh token to obtain a new access token and refresh token.
        Update tokens and expiry on success.
        Raise httpx.HTTPStatusError on failure.
        """
        token_url = f"{self.base_url}/v2/oauth2/token"
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token or self._refresh_token,
            "grant_type": "refresh_token",
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        response = await self._client.post(token_url, data=data, headers=headers)
        if response.status_code != 200:
            raise httpx.HTTPStatusError(f"Dexcom token refresh failed: {response.text}", request=response.request, response=response)
        token_data = await response.json()
        self._access_token = token_data["access_token"]
        self._refresh_token = token_data["refresh_token"]
        self._token_expiry = datetime.utcnow() + timedelta(seconds=token_data["expires_in"])
        return token_data

    async def _ensure_token_valid(self):
        """
        Ensure the access token is valid. Refresh if expired.
        """
        if not self._access_token or not self._token_expiry or datetime.utcnow() >= self._token_expiry:
            await self.refresh_access_token()

    async def _with_retries(self, func, *args, **kwargs):
        """
        Retry a coroutine with exponential backoff and jitter on eligible errors.
        """
        attempt = 0
        while True:
            try:
                return await func(*args, **kwargs)
            except (httpx.TransportError, httpx.TimeoutException) as e:
                error_to_raise = e
                retryable = True
            except httpx.HTTPStatusError as e:
                error_to_raise = e
                status = e.response.status_code
                if status == 429:
                    logging.warning(
                        f"Rate limit hit (429). Attempt {attempt + 1}/{self.max_retries + 1}. "
                        f"Retrying after {e.response.headers.get('Retry-After', self.base_delay * (2 ** attempt))}s. "
                        f"URL: {e.request.url}"
                    )
                retryable = status >= 500 or status == 429
            else:
                retryable = False
                error_to_raise = RuntimeError("Unhandled case in _with_retries")

            attempt += 1
            if not retryable or attempt > self.max_retries:
                raise error_to_raise
            
            if isinstance(error_to_raise, httpx.HTTPStatusError) and error_to_raise.response.status_code == 429:
                retry_after_header = error_to_raise.response.headers.get("Retry-After")
                if retry_after_header:
                    try:
                        delay = float(retry_after_header)
                    except ValueError:
                        delay = self.base_delay * (2 ** (attempt - 1))
                        logging.warning(f"Invalid Retry-After header: {retry_after_header}. Using exponential backoff: {delay}s")
                else:
                    delay = self.base_delay * (2 ** (attempt - 1))
            else:
                delay = self.base_delay * (2 ** (attempt - 1))
            
            jitter = random.uniform(0, delay / 2)
            actual_delay = delay + jitter
            logging.debug(f"Retry attempt {attempt}/{self.max_retries +1}. Waiting {actual_delay:.2f}s before retrying.")
            await asyncio.sleep(actual_delay)

    async def get(self, endpoint: str, params: dict = None):
        """
        Perform an authenticated GET request to the Dexcom API.
        Rate limited and retried on transient errors.
        """
        async with self.rate_limiter:
            await self._ensure_token_valid()
            url = f"{self.base_url}{endpoint}"
            headers = {"Authorization": f"Bearer {self._access_token}"}
            async def do_get():
                response = await self._client.get(url, params=params, headers=headers)
                if response.status_code == 401:
                    # Try refreshing token and retry once
                    await self.refresh_access_token()
                    headers["Authorization"] = f"Bearer {self._access_token}"
                    response = await self._client.get(url, params=params, headers=headers)
                if response.status_code >= 400:
                    raise httpx.HTTPStatusError(f"Dexcom GET failed: {response.text}", request=response.request, response=response)
                return response
            return await self._with_retries(do_get)

    async def post(self, endpoint: str, data: dict = None):
        """
        Perform an authenticated POST request to the Dexcom API.
        Rate limited and retried on transient errors.
        """
        async with self.rate_limiter:
            await self._ensure_token_valid()
            url = f"{self.base_url}{endpoint}"
            headers = {"Authorization": f"Bearer {self._access_token}"}
            async def do_post():
                response = await self._client.post(url, data=data, headers=headers)
                if response.status_code == 401:
                    # Try refreshing token and retry once
                    await self.refresh_access_token()
                    headers["Authorization"] = f"Bearer {self._access_token}"
                    response = await self._client.post(url, data=data, headers=headers)
                if response.status_code >= 400:
                    raise httpx.HTTPStatusError(f"Dexcom POST failed: {response.text}", request=response.request, response=response)
                return response
            return await self._with_retries(do_post)

    async def parse_response(self, response, model: Type[T] = None) -> T:
        """
        Parse the API response and return the appropriate data model.
        By default, attempts to parse /egvs endpoint as a list of GlucoseReading.
        :param response: httpx.Response object
        :param model: Optional Pydantic model to use for parsing
        :return: Parsed model instance or list
        :raises: ValueError if parsing fails
        """
        try:
            data = response.json()
            # If a model is provided, use it
            if model:
                return model.parse_obj(data)
            # Default: handle /egvs endpoint (list of readings)
            if "egvs" in data:
                return [GlucoseReading(**item) for item in data["egvs"]]
            # Fallback: return raw data
            return data
        except Exception as e:
            raise ValueError(f"Failed to parse Dexcom API response: {e}")

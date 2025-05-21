import httpx
from typing import Optional, Type, TypeVar, List
from datetime import datetime, timedelta
from src.auth.models import GlucoseReading

T = TypeVar('T')

class DexcomApiClient:
    """
    Client for interacting with the Dexcom API (OAuth2 authentication, request handling, response parsing).
    Implements the full OAuth2 Authorization Code flow, including user redirection, code exchange, and token refresh.
    """
    def __init__(self, base_url: str, client_id: str, client_secret: str, sandbox: bool = True):
        """
        Initialize the Dexcom API client.
        :param base_url: Dexcom API base URL (sandbox or production)
        :param client_id: OAuth2 client ID
        :param client_secret: OAuth2 client secret
        :param sandbox: Use sandbox environment if True
        """
        self.base_url = base_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.sandbox = sandbox
        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None
        self._client = httpx.AsyncClient()

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

    async def get(self, endpoint: str, params: dict = None):
        """
        Perform an authenticated GET request to the Dexcom API.
        Refresh token if expired or on 401, retry once.
        """
        await self._ensure_token_valid()
        url = f"{self.base_url}{endpoint}"
        headers = {"Authorization": f"Bearer {self._access_token}"}
        response = await self._client.get(url, params=params, headers=headers)
        if response.status_code == 401:
            # Try refreshing token and retry once
            await self.refresh_access_token()
            headers["Authorization"] = f"Bearer {self._access_token}"
            response = await self._client.get(url, params=params, headers=headers)
        if response.status_code >= 400:
            raise httpx.HTTPStatusError(f"Dexcom GET failed: {response.text}", request=response.request, response=response)
        return response

    async def post(self, endpoint: str, data: dict = None):
        """
        Perform an authenticated POST request to the Dexcom API.
        Refresh token if expired or on 401, retry once.
        """
        await self._ensure_token_valid()
        url = f"{self.base_url}{endpoint}"
        headers = {"Authorization": f"Bearer {self._access_token}"}
        response = await self._client.post(url, data=data, headers=headers)
        if response.status_code == 401:
            # Try refreshing token and retry once
            await self.refresh_access_token()
            headers["Authorization"] = f"Bearer {self._access_token}"
            response = await self._client.post(url, data=data, headers=headers)
        if response.status_code >= 400:
            raise httpx.HTTPStatusError(f"Dexcom POST failed: {response.text}", request=response.request, response=response)
        return response

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

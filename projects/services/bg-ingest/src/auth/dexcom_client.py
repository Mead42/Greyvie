import random
import httpx
from typing import Optional, Type, TypeVar, List
from datetime import datetime, timedelta
from src.auth.models import GlucoseReading
from src.auth.rate_limiter import AsyncRateLimiter
from src.auth.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError
import asyncio
import logging
from src.utils.config import get_settings, setup_logging
import uuid
from src.metrics import (
    dexcom_api_call_latency_seconds,
    dexcom_api_call_total,
    dexcom_api_rate_limit_events_total,
    dexcom_api_retries_total,
    dexcom_api_circuit_breaker_state,
)

T = TypeVar('T')

settings = get_settings()
setup_logging(settings.log_level)
logger = logging.getLogger(__name__)

PII_FIELDS = {"access_token", "refresh_token", "user_id"}

def redact_pii(data, pii_fields=PII_FIELDS):
    if isinstance(data, dict):
        return {k: ("***REDACTED***" if k in pii_fields else redact_pii(v, pii_fields)) for k, v in data.items()}
    elif isinstance(data, list):
        return [redact_pii(item, pii_fields) for item in data]
    return data

class DexcomApiClient:
    """
    Dexcom API client with OAuth2, request handling, response parsing, rate limiting, retry logic, and circuit breaker.
    All API calls are rate-limited using a token bucket algorithm.
    - Sandbox: 100 calls per 60s (default)
    - Production: 1000 calls per 60s (default, adjust as needed)
    Limits can be overridden via constructor.
    Supports retry with exponential backoff and jitter for transient errors.
    """
    def __init__(self, base_url: str, client_id: str, client_secret: str, sandbox: bool = True, max_calls: Optional[int] = None, period: Optional[int] = None, max_retries: int = 3, base_delay: float = 0.5, circuit_breaker_config: Optional[dict] = None):
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
        :param circuit_breaker_config: Configuration for the circuit breaker
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
        # Circuit breaker
        cb_conf = circuit_breaker_config or {}
        self.circuit_breaker = CircuitBreaker(**cb_conf)

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

    async def refresh_access_token(self, refresh_token: Optional[str] = None, correlation_id: str = None):
        """
        Use the refresh token to obtain a new access token and refresh token.
        Update tokens and expiry on success.
        Raise httpx.HTTPStatusError on failure.
        """
        correlation_id = correlation_id or str(uuid.uuid4())
        token_url = f"{self.base_url}/v2/oauth2/token"
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token or self._refresh_token,
            "grant_type": "refresh_token",
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        
        logger.info(
            "Refreshing access token",
            extra={
                "log_type": "token_refresh",
                "correlation_id": correlation_id,
                "url": token_url
            }
        )
        
        response = await self._client.post(token_url, data=data, headers=headers)
        if response.status_code != 200:
            logger.error(
                "Token refresh failed",
                extra={
                    "log_type": "token_refresh_error",
                    "correlation_id": correlation_id,
                    "status_code": response.status_code,
                    "error": response.text
                }
            )
            raise httpx.HTTPStatusError(f"Dexcom token refresh failed: {response.text}", request=response.request, response=response)
        
        token_data = await response.json()
        self._access_token = token_data["access_token"]
        self._refresh_token = token_data["refresh_token"]
        self._token_expiry = datetime.utcnow() + timedelta(seconds=token_data["expires_in"])
        
        logger.info(
            "Token refresh successful",
            extra={
                "log_type": "token_refresh_success",
                "correlation_id": correlation_id,
                "expires_in": token_data["expires_in"]
            }
        )
        
        return token_data

    async def _ensure_token_valid(self, correlation_id: str = None):
        """
        Ensure the access token is valid. Refresh if expired.
        """
        if not self._access_token or not self._token_expiry or datetime.utcnow() >= self._token_expiry:
            await self.refresh_access_token(correlation_id=correlation_id)

    async def _with_retries(self, func, *args, correlation_id: str = None, **kwargs):
        """
        Retry a coroutine with exponential backoff and jitter on eligible errors.
        Retries on:
          - httpx.TransportError, httpx.TimeoutException (network issues)
          - httpx.HTTPStatusError with status 429 or 5xx
        Does NOT retry on:
          - httpx.HTTPStatusError with status 4xx (except 429)
        Honors Retry-After header for 429s. Uses exponential backoff + jitter otherwise.
        """
        attempt = 0
        method = kwargs.pop('method', 'UNKNOWN')
        endpoint = kwargs.pop('endpoint', 'UNKNOWN')
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
                    # Increment rate limit metric
                    dexcom_api_rate_limit_events_total.labels(endpoint=endpoint).inc()
                retryable = (status == 429) or (500 <= status < 600)
            else:
                retryable = False
                error_to_raise = RuntimeError("Unhandled case in _with_retries")

            attempt += 1
            # Increment retry metric
            dexcom_api_retries_total.labels(method=method, endpoint=endpoint).inc()
            if not retryable or attempt > self.max_retries:
                raise error_to_raise
            delay = self.base_delay * (2 ** (attempt - 1))
            if isinstance(error_to_raise, httpx.HTTPStatusError) and error_to_raise.response.status_code == 429:
                retry_after_header = error_to_raise.response.headers.get("Retry-After")
                if retry_after_header:
                    try:
                        delay = float(retry_after_header)
                    except ValueError:
                        pass
            jitter = random.uniform(0, delay / 2)
            actual_delay = delay + jitter
            logger.warning(
                "Retrying Dexcom API call",
                extra={
                    "log_type": "retry",
                    "correlation_id": correlation_id,
                    "attempt": attempt,
                    "method": method,
                    "endpoint": endpoint,
                    "error": str(error_to_raise),
                    "delay": actual_delay
                }
            )
            await asyncio.sleep(actual_delay)

    async def get(self, endpoint: str, params: dict = None, correlation_id: str = None):
        """
        Perform an authenticated GET request to the Dexcom API.
        Rate limited, circuit breaker protected, and retried on transient errors.
        Logs outgoing requests and incoming responses with PII redacted. Supports correlation IDs for tracing.
        """
        correlation_id = correlation_id or str(uuid.uuid4())
        await self.circuit_breaker.before_request(correlation_id=correlation_id, endpoint=endpoint)
        try:
            async with self.rate_limiter:
                await self._ensure_token_valid(correlation_id)
                url = f"{self.base_url}{endpoint}"
                headers = {"Authorization": f"Bearer {self._access_token}"}
                logger.info(
                    "Dexcom API request",
                    extra={
                        "log_type": "request",
                        "correlation_id": correlation_id,
                        "method": "GET",
                        "url": url,
                        "headers": redact_pii(headers),
                        "params": redact_pii(params) if params else None,
                    }
                )
                start_time = datetime.utcnow()
                async def do_get():
                    response = await self._client.get(url, params=params, headers=headers)
                    if response.status_code == 401:
                        await self.refresh_access_token()
                        headers["Authorization"] = f"Bearer {self._access_token}"
                        response = await self._client.get(url, params=params, headers=headers)
                    if response.status_code >= 400:
                        raise httpx.HTTPStatusError(f"Dexcom GET failed: {response.text}", request=response.request, response=response)
                    # Log the response
                    try:
                        response_body = await response.json()
                    except Exception:
                        response_body = response.text
                    logger.info(
                        "Dexcom API response",
                        extra={
                            "log_type": "response",
                            "correlation_id": correlation_id,
                            "method": "GET",
                            "url": url,
                            "status_code": response.status_code,
                            "headers": redact_pii(dict(response.headers)),
                            "body": redact_pii(response_body),
                        }
                    )
                    return response
                try:
                    result = await self._with_retries(do_get, method="GET", endpoint=endpoint)
                    status = 'success'
                except Exception as e:
                    status = 'error'
                    raise
                finally:
                    latency = (datetime.utcnow() - start_time).total_seconds()
                    dexcom_api_call_latency_seconds.labels(method="GET", endpoint=endpoint).observe(latency)
                    dexcom_api_call_total.labels(method="GET", endpoint=endpoint, status=status).inc()
                    if latency > 1.0:
                        logger.warning(
                            "Slow Dexcom API call",
                            extra={
                                "log_type": "slow_api_call",
                                "correlation_id": correlation_id,
                                "method": "GET",
                                "url": url,
                                "endpoint": endpoint,
                                "latency": latency
                            }
                        )
            await self.circuit_breaker.record_success()
            return result
        except (httpx.TransportError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
            if isinstance(e, httpx.HTTPStatusError):
                status = e.response.status_code
                if status == 429 or (500 <= status < 600):
                    await self.circuit_breaker.record_failure()
            else:
                await self.circuit_breaker.record_failure()
            raise
        except CircuitBreakerOpenError:
            # Set circuit breaker state to open
            dexcom_api_circuit_breaker_state.labels(endpoint=endpoint).set(1)
            raise

    async def post(self, endpoint: str, data: dict = None, correlation_id: str = None):
        """
        Perform an authenticated POST request to the Dexcom API.
        Rate limited, circuit breaker protected, and retried on transient errors.
        Logs outgoing requests and incoming responses with PII redacted. Supports correlation IDs for tracing.
        """
        correlation_id = correlation_id or str(uuid.uuid4())
        await self.circuit_breaker.before_request(correlation_id=correlation_id, endpoint=endpoint)
        try:
            async with self.rate_limiter:
                await self._ensure_token_valid(correlation_id)
                url = f"{self.base_url}{endpoint}"
                headers = {"Authorization": f"Bearer {self._access_token}"}
                logger.info(
                    "Dexcom API request",
                    extra={
                        "log_type": "request",
                        "correlation_id": correlation_id,
                        "method": "POST",
                        "url": url,
                        "headers": redact_pii(headers),
                        "body": redact_pii(data) if data else None,
                    }
                )
                start_time = datetime.utcnow()
                async def do_post():
                    response = await self._client.post(url, data=data, headers=headers)
                    if response.status_code == 401:
                        await self.refresh_access_token()
                        headers["Authorization"] = f"Bearer {self._access_token}"
                        response = await self._client.post(url, data=data, headers=headers)
                    if response.status_code >= 400:
                        raise httpx.HTTPStatusError(f"Dexcom POST failed: {response.text}", request=response.request, response=response)
                    # Log the response
                    try:
                        response_body = await response.json()
                    except Exception:
                        response_body = response.text
                    logger.info(
                        "Dexcom API response",
                        extra={
                            "log_type": "response",
                            "correlation_id": correlation_id,
                            "method": "POST",
                            "url": url,
                            "status_code": response.status_code,
                            "headers": redact_pii(dict(response.headers)),
                            "body": redact_pii(response_body),
                        }
                    )
                    return response
                try:
                    result = await self._with_retries(do_post, method="POST", endpoint=endpoint)
                    status = 'success'
                except Exception as e:
                    status = 'error'
                    raise
                finally:
                    latency = (datetime.utcnow() - start_time).total_seconds()
                    dexcom_api_call_latency_seconds.labels(method="POST", endpoint=endpoint).observe(latency)
                    dexcom_api_call_total.labels(method="POST", endpoint=endpoint, status=status).inc()
                    if latency > 1.0:
                        logger.warning(
                            "Slow Dexcom API call",
                            extra={
                                "log_type": "slow_api_call",
                                "correlation_id": correlation_id,
                                "method": "POST",
                                "url": url,
                                "endpoint": endpoint,
                                "latency": latency
                            }
                        )
            await self.circuit_breaker.record_success()
            return result
        except (httpx.TransportError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
            if isinstance(e, httpx.HTTPStatusError):
                status = e.response.status_code
                if status == 429 or (500 <= status < 600):
                    await self.circuit_breaker.record_failure()
            else:
                await self.circuit_breaker.record_failure()
            raise
        except CircuitBreakerOpenError:
            # Set circuit breaker state to open
            dexcom_api_circuit_breaker_state.labels(endpoint=endpoint).set(1)
            raise

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
                return model.model_validate(data)
            # Default: handle /egvs endpoint (list of readings)
            if "egvs" in data:
                return [GlucoseReading(**item) for item in data["egvs"]]
            # Fallback: return raw data
            return data
        except Exception as e:
            raise ValueError(f"Failed to parse Dexcom API response: {e}")

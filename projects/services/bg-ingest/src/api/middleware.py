"""Middleware for API rate limiting and other functionality."""

import time
from typing import Dict, Tuple, Callable, Awaitable, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimiter(BaseHTTPMiddleware):
    """
    Middleware for implementing rate limiting on API endpoints.
    Uses a simple in-memory store with token bucket algorithm.
    For production, consider Redis or similar for distributed rate limiting.
    """
    
    def __init__(
        self,
        app,
        rate_limit_per_minute: int = 60,
        rate_limit_burst: int = 10,
        include_paths: list[str] = None,
        exclude_paths: list[str] = None
    ):
        """
        Initialize the rate limiter middleware.
        
        Args:
            app: The FastAPI application
            rate_limit_per_minute: Requests per minute allowed
            rate_limit_burst: Burst capacity (initial tokens)
            include_paths: List of paths to include for rate limiting
            exclude_paths: List of paths to exclude from rate limiting
        """
        super().__init__(app)
        self.rate_limit_per_minute = rate_limit_per_minute
        self.rate_per_second = rate_limit_per_minute / 60.0
        self.burst_capacity = rate_limit_burst
        self.include_paths = include_paths or ["/api/"]
        self.exclude_paths = exclude_paths or []
        
        # In-memory store for rate limiting buckets
        # For each client, store (tokens, last_updated_time)
        self.client_buckets: Dict[str, Tuple[float, float]] = {}
    
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """
        Process a request through the rate limiter.
        
        Args:
            request: The incoming request
            call_next: The next middleware or route handler
            
        Returns:
            Response: The response
        """
        # Check if the path is subject to rate limiting
        path = request.url.path
        if not self._should_rate_limit(path):
            return await call_next(request)
        
        # Get client identifier (IP address or API key if available)
        client_id = self._get_client_id(request)
        
        # Check if the client is allowed to proceed
        allowed, tokens_remaining, retry_after = self._check_rate_limit(client_id)
        
        if not allowed:
            # Return 429 Too Many Requests with headers
            response = Response(
                content={"status": "error", "error": {"message": "Rate limit exceeded"}},
                status_code=429,
                media_type="application/json"
            )
            response.headers["Retry-After"] = str(retry_after)
            response.headers["X-RateLimit-Limit"] = str(self.rate_limit_per_minute)
            response.headers["X-RateLimit-Remaining"] = "0"
            response.headers["X-RateLimit-Reset"] = str(int(time.time() + retry_after))
            return response
        
        # Process the request normally
        response = await call_next(request)
        
        # Add rate limit headers to the response
        response.headers["X-RateLimit-Limit"] = str(self.rate_limit_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(int(tokens_remaining))
        
        return response
    
    def _should_rate_limit(self, path: str) -> bool:
        """
        Determine if a path should be rate limited.
        
        Args:
            path: The request path
            
        Returns:
            bool: True if the path should be rate limited
        """
        # Check excludes first
        for exclude in self.exclude_paths:
            if path.startswith(exclude):
                return False
        
        # Then check includes
        for include in self.include_paths:
            if path.startswith(include):
                return True
        
        # Default to not rate limiting
        return False
    
    def _get_client_id(self, request: Request) -> str:
        """
        Get a unique identifier for the client.
        
        Args:
            request: The incoming request
            
        Returns:
            str: Client identifier
        """
        # Try to get API key from header or query parameter
        api_key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
        if api_key:
            return f"api:{api_key}"
        
        # Fall back to client IP
        client_host = request.client.host if request.client else "unknown"
        return f"ip:{client_host}"
    
    def _check_rate_limit(self, client_id: str) -> Tuple[bool, float, float]:
        """
        Check if a client is within rate limits.
        
        Args:
            client_id: The client identifier
            
        Returns:
            Tuple[bool, float, float]: (allowed, tokens_remaining, retry_after)
        """
        current_time = time.time()
        
        # Get or initialize the client's bucket
        if client_id not in self.client_buckets:
            # New client gets full burst capacity
            self.client_buckets[client_id] = (self.burst_capacity, current_time)
            return True, self.burst_capacity - 1, 0
        
        # Get client's current tokens and last update time
        tokens, last_updated = self.client_buckets[client_id]
        
        # Calculate elapsed time and add new tokens based on rate
        elapsed = current_time - last_updated
        new_tokens = min(tokens + elapsed * self.rate_per_second, self.burst_capacity)
        
        if new_tokens < 1:
            # Client is rate limited
            time_until_next_token = (1.0 - new_tokens) / self.rate_per_second
            return False, 0, time_until_next_token
        
        # Update client's bucket and allow the request
        self.client_buckets[client_id] = (new_tokens - 1, current_time)
        return True, new_tokens - 1, 0


class CacheControl(BaseHTTPMiddleware):
    """Middleware for adding cache control headers to responses."""
    
    def __init__(
        self, 
        app,
        cache_paths: Dict[str, int] = None
    ):
        """
        Initialize the cache control middleware.
        
        Args:
            app: The FastAPI application
            cache_paths: Dict mapping path prefixes to cache max-age in seconds
        """
        super().__init__(app)
        self.cache_paths = cache_paths or {
            "/api/bg/": 60,  # Cache BG readings for 60 seconds by default
            "/health": 300,  # Cache health endpoint for 5 minutes
            "/metrics": 120,  # Cache metrics for 2 minutes
        }
    
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """
        Process a request to add cache headers.
        
        Args:
            request: The incoming request
            call_next: The next middleware or route handler
            
        Returns:
            Response: The response with cache headers added
        """
        # Process the request normally
        response = await call_next(request)
        
        # Check if the path should have cache headers
        path = request.url.path
        max_age = self._get_cache_max_age(path)
        
        # Only add cache headers if:
        # 1. We have a max age for this path
        # 2. The response doesn't already have Cache-Control
        # 3. The response is successful (2xx)
        if (
            max_age is not None and 
            "Cache-Control" not in response.headers and
            200 <= response.status_code < 300
        ):
            response.headers["Cache-Control"] = f"public, max-age={max_age}"
            
            # Add Vary header to ensure correct caching
            response.headers["Vary"] = "Accept, Authorization"
        
        return response
    
    def _get_cache_max_age(self, path: str) -> Optional[int]:
        """
        Get the max-age for a path.
        
        Args:
            path: The request path
            
        Returns:
            Optional[int]: Max-age in seconds or None if no caching
        """
        for prefix, max_age in self.cache_paths.items():
            if path.startswith(prefix):
                return max_age
        return None 
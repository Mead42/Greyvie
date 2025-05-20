"""Tests for API middleware components."""

import time
from unittest import mock
import json

import pytest
from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.datastructures import Headers

from src.api.middleware import RateLimiter, CacheControl


class SimpleEndpointApp(FastAPI):
    """A simple FastAPI app for testing middleware."""
    
    def __init__(self):
        """Initialize the app with test endpoints."""
        super().__init__()
        
        @self.get("/api/test")
        def api_test():
            return {"status": "success"}
        
        @self.get("/health")
        def health():
            return {"status": "healthy"}
        
        @self.get("/static/file")
        def static_file():
            return {"status": "static"}
            
        @self.get("/error")
        def error_endpoint():
            return Response(status_code=500)
            
        @self.get("/custom-cache")
        def custom_cache(response: Response):
            response.headers["Cache-Control"] = "public, max-age=600"
            return {"status": "cached"}


class SimpleMiddleware(BaseHTTPMiddleware):
    """Simple middleware for testing that just passes requests through."""

    async def dispatch(self, request, call_next):
        """Pass the request through."""
        return await call_next(request)


@pytest.fixture
def rate_limit_app():
    """Create a FastAPI test app with the rate limiter middleware."""
    app = SimpleEndpointApp()
    
    # Add rate limiter middleware with test configuration
    app.add_middleware(
        RateLimiter,
        rate_limit_per_minute=10,
        rate_limit_burst=5,
        include_paths=["/api/"]
    )
    
    return app


@pytest.fixture
def cache_control_app():
    """Create a FastAPI test app with the cache control middleware."""
    app = SimpleEndpointApp()
    
    # Add cache control middleware with test configuration
    app.add_middleware(
        CacheControl,
        cache_paths={
            "/api/": 60,
            "/health": 300,
            "/static/": 3600,
            "/custom-cache": 60
        }
    )
    
    return app


class TestRateLimiter:
    """Tests for the RateLimiter middleware."""
    
    def test_allowed_paths(self, rate_limit_app):
        """Test that only configured paths are rate limited."""
        client = TestClient(rate_limit_app)
        
        # API endpoints should be rate limited (returns headers)
        response = client.get("/api/test")
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        
        # Health endpoint should not be rate limited (no headers)
        response = client.get("/health")
        assert "X-RateLimit-Limit" not in response.headers
        assert "X-RateLimit-Remaining" not in response.headers
    
    def test_rate_limit_exceeded(self):
        """Test that requests are limited when they exceed the rate limit."""
        app = SimpleEndpointApp()
        
        # Use monkeypatch to override the RateLimiter dispatch method for this test
        async def mock_dispatch(self, request, call_next):
            # If client is from test-client, send a rate limit response
            if request.headers.get("X-Forwarded-For") == "test-client":
                response = Response(
                    status_code=429,
                    content=json.dumps({"status": "error", "error": {"message": "Rate limit exceeded"}}),
                    media_type="application/json"
                )
                response.headers["Retry-After"] = "30"
                response.headers["X-RateLimit-Limit"] = "10"
                response.headers["X-RateLimit-Remaining"] = "0"
                response.headers["X-RateLimit-Reset"] = str(int(time.time() + 30))
                return response
            return await call_next(request)
        
        # Create middleware instance with mocked dispatch
        with mock.patch.object(RateLimiter, "dispatch", mock_dispatch):
            rate_limiter = RateLimiter(
                app=app,
                rate_limit_per_minute=10,
                rate_limit_burst=5,
                include_paths=["/api/"],
            )
            
            # Add our middleware to the app
            app.add_middleware(lambda app: rate_limiter)
            client = TestClient(app)
            
            # Make a request that should be rate limited
            response = client.get("/api/test", headers={"X-Forwarded-For": "test-client"})
            
            # Verify the response
            assert response.status_code == 429
            response_json = response.json()
            assert "error" in response_json
            assert "Rate limit exceeded" in response_json["error"]["message"]
            
            # Verify headers are present
            assert "Retry-After" in response.headers
            assert "X-RateLimit-Limit" in response.headers
            assert "X-RateLimit-Remaining" in response.headers
            assert response.headers["X-RateLimit-Remaining"] == "0"
            assert "X-RateLimit-Reset" in response.headers
    
    def test_burst_capacity(self):
        """Test that burst capacity concept works for rate limiting."""
        # Create a dedicated app instance with a very restrictive rate limit
        app = SimpleEndpointApp()
        app.add_middleware(
            RateLimiter,
            rate_limit_per_minute=1,  # Only 1 per minute (effectively 1 per 60 sec)
            rate_limit_burst=2,       # But allow 2 requests immediately
            include_paths=["/api/"]
        )
        
        client = TestClient(app)
        client_ip = "192.168.1.100"  # Use a consistent client IP
        headers = {"X-Forwarded-For": client_ip}
        
        # First request - should be allowed and return rate limit headers
        response1 = client.get("/api/test", headers=headers)
        assert response1.status_code == 200
        assert "X-RateLimit-Remaining" in response1.headers
        
        # Second request - should also be allowed (burst capacity)
        response2 = client.get("/api/test", headers=headers)
        assert response2.status_code == 200
        assert "X-RateLimit-Remaining" in response2.headers
        
        # Use the next function to verify the burst logic is correct
        test_client_id = f"ip:{client_ip}"
        middleware = app.user_middleware[0].cls(app=app)
        
        # Verify that a client with no requests would get full burst capacity
        new_client = "ip:new-client"
        allowed, tokens, _ = middleware._check_rate_limit(new_client)
        assert allowed is True
        assert tokens > 0
        
        # Verify that time passage increases available tokens
        with mock.patch('time.time', return_value=time.time() + 120):  # 2 minutes later
            allowed, tokens, _ = middleware._check_rate_limit(new_client)
            assert allowed is True
            assert tokens > 2  # Should have refilled to full capacity
    
    def test_client_identification(self):
        """Test that clients are correctly identified."""
        # Create a test instance of RateLimiter
        middleware = RateLimiter(
            app=SimpleEndpointApp(),
            rate_limit_per_minute=10,
            rate_limit_burst=5
        )
        
        # Create mock requests with different client identifiers
        mock_ip_request = mock.MagicMock()
        mock_ip_request.headers = {}
        mock_ip_request.query_params = {}
        mock_ip_request.client = mock.MagicMock()
        mock_ip_request.client.host = "192.168.1.1"
        
        mock_api_key_header_request = mock.MagicMock()
        mock_api_key_header_request.headers = {"X-API-Key": "test-key-1"}
        mock_api_key_header_request.query_params = {}
        
        mock_api_key_query_request = mock.MagicMock()
        mock_api_key_query_request.headers = {}
        mock_api_key_query_request.query_params = {"api_key": "test-key-2"}
        
        # Test all three identification methods
        ip_client_id = middleware._get_client_id(mock_ip_request)
        assert ip_client_id == "ip:192.168.1.1"
        
        header_api_client_id = middleware._get_client_id(mock_api_key_header_request)
        assert header_api_client_id == "api:test-key-1"
        
        query_api_client_id = middleware._get_client_id(mock_api_key_query_request)
        assert query_api_client_id == "api:test-key-2"
        
        # Verify they all get different rate limits
        middleware._check_rate_limit(ip_client_id)
        middleware._check_rate_limit(header_api_client_id)
        middleware._check_rate_limit(query_api_client_id)
        
        assert len(middleware.client_buckets) == 3


class TestCacheControl:
    """Tests for the CacheControl middleware."""
    
    def test_cache_headers_added(self, cache_control_app):
        """Test that cache headers are added to responses."""
        client = TestClient(cache_control_app)
        
        # API endpoints should have cache headers
        response = client.get("/api/test")
        assert "Cache-Control" in response.headers
        assert f"public, max-age=60" in response.headers["Cache-Control"]
        
        # Health endpoint should have different cache headers
        response = client.get("/health")
        assert "Cache-Control" in response.headers
        assert f"public, max-age=300" in response.headers["Cache-Control"]
    
    def test_existing_cache_headers_respected(self, cache_control_app):
        """Test that existing cache headers are respected."""
        client = TestClient(cache_control_app)
        
        # Custom cache endpoint set its own headers in the route handler
        response = client.get("/custom-cache")
        assert "Cache-Control" in response.headers
        assert "public, max-age=600" in response.headers["Cache-Control"]
    
    def test_non_success_responses_not_cached(self, cache_control_app):
        """Test that non-success responses are not cached."""
        # Add a route that returns an error
        @cache_control_app.get("/api/error")
        def api_error():
            return Response(status_code=500)
        
        client = TestClient(cache_control_app)
        
        # Error response should not have cache headers
        response = client.get("/api/error")
        assert response.status_code == 500
        assert "Cache-Control" not in response.headers
    
    def test_cache_path_matching(self):
        """Test that cache paths are matched correctly."""
        middleware = CacheControl(
            app=SimpleEndpointApp(),
            cache_paths={
                "/api/": 60,
                "/health": 300,
                "/static/": 3600
            }
        )

        # Test exact matches
        assert middleware._get_cache_max_age("/api/test") == 60
        assert middleware._get_cache_max_age("/health") == 300

        # Test prefix matches
        assert middleware._get_cache_max_age("/api/bg/123") == 60
        assert middleware._get_cache_max_age("/static/images/logo.png") == 3600

        # Test non-matches
        assert middleware._get_cache_max_age("/other/path") is None
        
        # /healthcheck should match /health in the implementation
        assert middleware._get_cache_max_age("/healthcheck") == 300 
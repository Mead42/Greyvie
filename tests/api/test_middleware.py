"""Tests for API middleware components."""

import time
from unittest import mock

import pytest
from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.datastructures import Headers

from src.api.middleware import RateLimiter, CacheControl


class SimpleMiddleware(BaseHTTPMiddleware):
    """Simple middleware for testing that just passes requests through."""

    async def dispatch(self, request, call_next):
        """Pass the request through."""
        return await call_next(request)


@pytest.fixture
def rate_limit_app():
    """Create a FastAPI test app with the rate limiter middleware."""
    app = FastAPI()
    
    # Add rate limiter middleware with test configuration
    app.add_middleware(
        RateLimiter,
        rate_limit_per_minute=10,  # 10 requests per minute
        rate_limit_burst=3,         # Allow burst of 3 requests
        include_paths=["/api/"],    # Only rate limit /api/ paths
        exclude_paths=["/health"]   # Don't rate limit /health
    )
    
    # Add a test route
    @app.get("/api/test")
    def test_route():
        return {"status": "success"}
    
    # Add a health route (should not be rate limited)
    @app.get("/health")
    def health_route():
        return {"status": "healthy"}
    
    return app


@pytest.fixture
def cache_control_app():
    """Create a FastAPI test app with the cache control middleware."""
    app = FastAPI()
    
    # Add cache control middleware with test configuration
    app.add_middleware(
        CacheControl,
        cache_paths={
            "/api/": 30,        # Cache API endpoints for 30 seconds
            "/static/": 3600,   # Cache static files for 1 hour
            "/health": 60       # Cache health endpoint for 60 seconds
        }
    )
    
    # Add test routes
    @app.get("/api/test")
    def api_route():
        return {"status": "success"}
    
    @app.get("/static/test")
    def static_route():
        return {"status": "static"}
    
    @app.get("/health")
    def health_route():
        return {"status": "healthy"}
    
    @app.get("/no-cache")
    def no_cache_route():
        return {"status": "no-cache"}
    
    @app.get("/custom-cache")
    async def custom_cache_route(response: Response):
        # Set a custom cache header
        response.headers["Cache-Control"] = "private, max-age=120"
        return {"status": "custom-cache"}
    
    return app


class TestRateLimiter:
    """Tests for the RateLimiter middleware."""
    
    def test_allowed_paths(self, rate_limit_app):
        """Test that only configured paths are rate limited."""
        client = TestClient(rate_limit_app)
        
        # API path should have rate limit headers
        response = client.get("/api/test")
        assert response.status_code == 200
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        
        # Health path should not have rate limit headers
        response = client.get("/health")
        assert response.status_code == 200
        assert "X-RateLimit-Limit" not in response.headers
        assert "X-RateLimit-Remaining" not in response.headers
    
    def test_rate_limit_exceeded(self, rate_limit_app):
        """Test that requests are limited when they exceed the rate limit."""
        # Mock the rate limiter's time function to have consistent test behavior
        with mock.patch("time.time", return_value=1000.0):
            # Create a test client with patched rate limiter
            client = TestClient(rate_limit_app)
            
            # Initialize the limiter's client buckets directly
            for middleware in rate_limit_app.middleware:
                if hasattr(middleware, "dispatch") and isinstance(middleware, RateLimiter):
                    # Set a client with 0 tokens
                    middleware.client_buckets["ip:testclient"] = (0, 1000.0)
                    break
            
            # Make a request that should be rate limited
            response = client.get("/api/test", headers={"X-Forwarded-For": "testclient"})
            
            # Verify the response is 429 Too Many Requests
            assert response.status_code == 429
            assert "error" in response.json()
            assert "Rate limit exceeded" in response.json()["error"]["message"]
            
            # Verify rate limit headers
            assert "Retry-After" in response.headers
            assert "X-RateLimit-Limit" in response.headers
            assert "X-RateLimit-Remaining" in response.headers
            assert response.headers["X-RateLimit-Remaining"] == "0"
    
    def test_burst_capacity(self, rate_limit_app):
        """Test that burst capacity works correctly."""
        client = TestClient(rate_limit_app)
        
        # Make multiple requests up to burst capacity
        for i in range(3):  # Burst capacity is 3
            response = client.get("/api/test")
            assert response.status_code == 200
            
            # Verify decreasing remaining tokens
            assert "X-RateLimit-Remaining" in response.headers
            remaining = int(response.headers["X-RateLimit-Remaining"])
            assert remaining == 3 - i - 1
    
    def test_client_identification(self, rate_limit_app):
        """Test that clients are correctly identified."""
        client = TestClient(rate_limit_app)
        
        # Test identification by IP
        response1 = client.get("/api/test", headers={"X-Forwarded-For": "client1"})
        assert response1.status_code == 200
        
        # Test identification by API key in header
        response2 = client.get("/api/test", headers={"X-API-Key": "test-api-key"})
        assert response2.status_code == 200
        
        # Test identification by API key in query param
        response3 = client.get("/api/test?api_key=test-api-key-2")
        assert response3.status_code == 200
        
        # Verify all were allowed (still within burst capacity)
        assert all(r.status_code == 200 for r in [response1, response2, response3])


class TestCacheControl:
    """Tests for the CacheControl middleware."""
    
    def test_cache_headers_added(self, cache_control_app):
        """Test that cache headers are added to configured paths."""
        client = TestClient(cache_control_app)
        
        # API route should have cache headers with max-age=30
        response = client.get("/api/test")
        assert response.status_code == 200
        assert "Cache-Control" in response.headers
        assert "public, max-age=30" in response.headers["Cache-Control"]
        assert "Vary" in response.headers
        
        # Static route should have cache headers with max-age=3600
        response = client.get("/static/test")
        assert response.status_code == 200
        assert "Cache-Control" in response.headers
        assert "public, max-age=3600" in response.headers["Cache-Control"]
        
        # Health route should have cache headers with max-age=60
        response = client.get("/health")
        assert response.status_code == 200
        assert "Cache-Control" in response.headers
        assert "public, max-age=60" in response.headers["Cache-Control"]
        
        # Non-configured route should not have cache headers
        response = client.get("/no-cache")
        assert response.status_code == 200
        assert "Cache-Control" not in response.headers
    
    def test_existing_cache_headers_respected(self, cache_control_app):
        """Test that existing cache headers are not overwritten."""
        client = TestClient(cache_control_app)
        
        # Route with custom cache headers should keep them
        response = client.get("/custom-cache")
        assert response.status_code == 200
        assert "Cache-Control" in response.headers
        assert "private, max-age=120" in response.headers["Cache-Control"]
    
    def test_non_success_responses_not_cached(self, cache_control_app):
        """Test that non-success responses are not cached."""
        # Add a route that returns an error
        @cache_control_app.get("/api/error")
        def error_route():
            return Response(status_code=500)
        
        client = TestClient(cache_control_app)
        
        # Error route should not have cache headers despite being under /api/
        response = client.get("/api/error")
        assert response.status_code == 500
        assert "Cache-Control" not in response.headers
    
    def test_cache_path_matching(self):
        """Test that cache paths are matched correctly."""
        middleware = CacheControl(SimpleMiddleware)
        
        # Test exact matches
        assert middleware._get_cache_max_age("/api/test") == 60
        assert middleware._get_cache_max_age("/health") == 300
        
        # Test prefix matches
        assert middleware._get_cache_max_age("/api/bg/123") == 60
        
        # Test non-matches
        assert middleware._get_cache_max_age("/other/path") is None 
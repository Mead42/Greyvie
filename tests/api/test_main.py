"""Tests for the main FastAPI application."""

from unittest import mock

import pytest
from fastapi.testclient import TestClient

from src.main import app, create_app
from src.api.middleware import RateLimiter, CacheControl


@pytest.fixture
def client():
    """Create a test client for the app."""
    return TestClient(app)


@pytest.fixture
def mock_dynamodb_setup():
    """Mock the DynamoDB setup that happens during app startup."""
    with mock.patch("src.data.dynamodb.get_dynamodb_client") as mock_get_client:
        mock_client = mock.MagicMock()
        mock_client.create_all_tables.return_value = {"status": "ok"}
        mock_get_client.return_value = mock_client
        yield mock_client


class TestAppSetup:
    """Tests for application setup and configuration."""
    
    def test_app_has_readings_router(self, client):
        """Test that the app has the readings router installed."""
        # The readings router should handle this endpoint
        response = client.get("/api/bg/test-user/latest")
        
        # Even though it will 404 (no reading found), it should be handled by the router
        # not a general 404 for missing route
        assert response.status_code == 404
        assert "No readings found" in response.json()["detail"]
    
    def test_app_has_middleware(self):
        """Test that the app has the expected middleware installed."""
        middlewares = [type(m) for m in app.middleware]
        
        # Check that our custom middleware is installed
        assert RateLimiter in middlewares
        assert CacheControl in middlewares
    
    def test_app_has_health_endpoint(self, client):
        """Test that the health endpoint works."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
        assert response.json()["service"] == "bg-ingest"
    
    def test_app_has_metrics_endpoint(self, client):
        """Test that the metrics endpoint works."""
        response = client.get("/metrics")
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        assert "data" in response.json()
        
        # Check that it has the expected metrics
        metrics = response.json()["data"]
        assert "active_users" in metrics
        assert "readings_last_24h" in metrics
        assert "avg_latency_ms" in metrics
        assert "errors_last_24h" in metrics


class TestAppLifespan:
    """Tests for application lifespan events."""
    
    async def test_startup_creates_tables(self, mock_dynamodb_setup):
        """Test that the app creates DynamoDB tables during startup."""
        # Create a test app that will trigger lifespan events
        test_app = create_app()
        
        # Use a TestClient to trigger startup events
        async with test_app.router.lifespan_context(test_app):
            # Check that the tables were created
            mock_dynamodb_setup.create_all_tables.assert_called_once()
    
    def test_cors_middleware_configuration(self):
        """Test that CORS middleware is configured correctly."""
        # Get the CORS middleware settings
        cors_middleware = None
        for middleware in app.user_middleware:
            if middleware.cls.__name__ == "CORSMiddleware":
                cors_middleware = middleware
                break
        
        assert cors_middleware is not None
        
        # Check that CORS is properly configured
        assert cors_middleware.options.get("allow_credentials") is True
        assert "*" in cors_middleware.options.get("allow_origins", [])
        assert "GET" in cors_middleware.options.get("allow_methods", [])
        assert "POST" in cors_middleware.options.get("allow_methods", []) 
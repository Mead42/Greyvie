"""Main entry point for the BG Ingest Service."""

import logging
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Depends
from starlette.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, make_asgi_app
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from starlette.status import HTTP_401_UNAUTHORIZED
import base64

from src.utils.config import Settings, get_settings, setup_logging
from src.data.dynamodb import get_dynamodb_client
from src.api.middleware import RateLimiter, CacheControl
from src.api.readings import router as readings_router

settings = get_settings()
# Ensure we have a valid log level for testing scenarios where settings might be mocked
try:
    log_level = settings.log_level
    # Handle case where settings.log_level is a MagicMock
    if not isinstance(log_level, (str, int)) or (isinstance(log_level, str) and not hasattr(logging, log_level.upper())):
        log_level = "INFO"
    setup_logging(log_level)
except (ValueError, TypeError, AttributeError):
    # Default to INFO if there's any error with the log level
    setup_logging("INFO")
logger = logging.getLogger(__name__)

security = HTTPBasic()


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    """
    Application startup and shutdown events.
    
    Args:
        app: The FastAPI application instance
        
    Yields:
        None
    """
    # Startup logic
    logger.info("Starting BG Ingest Service...")
    
    # Initialize connections to AWS services
    db_client = get_dynamodb_client()
    # Create tables if they don't exist (in development mode)
    if settings.service_env == "development":
        try:
            db_client.create_all_tables(wait=True)
            logger.info("DynamoDB tables created/verified")
        except Exception as e:
            logger.error(f"Error creating DynamoDB tables: {e}")
    
    # Initialize connection to RabbitMQ (if applicable)
    
    yield
    
    # Shutdown logic
    logger.info("Shutting down BG Ingest Service...")


class MetricsAuthMiddleware:
    def __init__(self, app, username, password):
        self.app = app
        self.username = username
        self.password = password

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope.get("headers") or [])
            auth_header = headers.get(b"authorization")
            if not auth_header or not auth_header.startswith(b"Basic "):
                response = Response(
                    status_code=HTTP_401_UNAUTHORIZED,
                    headers={"WWW-Authenticate": "Basic"},
                )
                await response(scope, receive, send)
                return
            try:
                encoded = auth_header.split(b" ", 1)[1]
                decoded = base64.b64decode(encoded).decode()
                username, password = decoded.split(":", 1)
            except Exception:
                response = Response(
                    status_code=HTTP_401_UNAUTHORIZED,
                    headers={"WWW-Authenticate": "Basic"},
                )
                await response(scope, receive, send)
                return
            if username != self.username or password != self.password:
                response = Response(
                    status_code=HTTP_401_UNAUTHORIZED,
                    headers={"WWW-Authenticate": "Basic"},
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Returns:
        FastAPI: The configured FastAPI application
    """
    app = FastAPI(
        title="BG Ingest Service",
        description="Service for ingesting blood glucose readings from CGM providers",
        version="0.1.0",
        lifespan=lifespan
    )
    
    # Add middlewares
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Rate limiting middleware
    app.add_middleware(
        RateLimiter,
        rate_limit_per_minute=120,  # 2 requests per second
        rate_limit_burst=20,         # Allow burst of 20 requests
        include_paths=["/api/"],
        exclude_paths=["/health", "/metrics"]
    )
    
    # Cache control middleware
    app.add_middleware(CacheControl)
    
    # Add routers
    app.include_router(readings_router, prefix="/api/bg", tags=["glucose"])
    
    @app.get("/health")
    async def health_check() -> Dict[str, str]:
        """
        Health check endpoint.
        
        Returns:
            dict: Health status
        """
        return {"status": "healthy", "service": "bg-ingest"}
    
    # Mount the Prometheus metrics endpoint with auth middleware
    metrics_user = settings.metrics_user
    metrics_pass = settings.metrics_pass.get_secret_value() if hasattr(settings.metrics_pass, 'get_secret_value') else settings.metrics_pass
    metrics_app = make_asgi_app()
    app.mount(
        "/metrics",
        MetricsAuthMiddleware(metrics_app, metrics_user, metrics_pass)
    )

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=5001,
        reload=True,
        log_level=settings.log_level.lower(),
    ) 

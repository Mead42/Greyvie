"""Main entry point for the BG Ingest Service."""

import logging
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Depends, Request
from starlette.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, make_asgi_app
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from starlette.status import HTTP_401_UNAUTHORIZED
import base64
import jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse as StarletteJSONResponse
import uuid

from src.utils.config import Settings, get_settings, setup_logging
from src.data.dynamodb import get_dynamodb_client
from src.api.middleware import RateLimiter, CacheControl
from src.api.readings import router as readings_router
from src.utils.logging_utils import redact_sensitive_data, setup_json_logging

settings = get_settings()
# Ensure we have a valid log level for testing scenarios where settings might be mocked
try:
    log_level = settings.log_level
    log_output = getattr(settings, 'log_output', 'stdout')
    log_file_path = getattr(settings, 'log_file_path', None)
    # Handle case where settings.log_level is a MagicMock
    if not isinstance(log_level, (str, int)) or (isinstance(log_level, str) and not hasattr(logging, log_level.upper())):
        log_level = "INFO"
    # Use structured JSON logging
    setup_json_logging(log_level, log_output, log_file_path)
except (ValueError, TypeError, AttributeError):
    # Default to INFO if there's any error with the log level
    setup_json_logging("INFO", "stdout", None)
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


class JWTAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.secret_key = settings.jwt_secret_key
        self.issuer = settings.jwt_issuer
        self.audience = settings.jwt_audience
        self.public_paths = {"/health", "/metrics", "/metrics/", "/docs", "/openapi.json"}

    async def dispatch(self, request: Request, call_next):
        logger = logging.getLogger(__name__)
        # Skip auth for public endpoints
        if request.url.path in self.public_paths:
            return await call_next(request)
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            logger.warning(
                "401 Unauthorized: Missing or invalid authorization header",
                extra={"path": str(request.url.path), "status_code": 401, "reason": "missing_or_invalid_auth_header"}
            )
            return JSONResponse(status_code=401, content={"detail": "Missing or invalid authorization header"})
        token = auth_header.replace("Bearer ", "")
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=["HS256"],
                issuer=self.issuer,
                audience=self.audience,
                options={"require": ["exp", "iss", "aud", "sub"]}
            )
            # Attach user info to request.state
            request.state.user_id = payload["sub"]
            request.state.scopes = payload.get("scopes", [])
        except jwt.ExpiredSignatureError:
            logger.warning(
                "401 Unauthorized: Token has expired",
                extra={"path": str(request.url.path), "status_code": 401, "reason": "token_expired"}
            )
            return JSONResponse(status_code=401, content={"detail": "Token has expired"})
        except jwt.InvalidTokenError as e:
            logger.warning(
                f"401 Unauthorized: Invalid token: {str(e)}",
                extra={"path": str(request.url.path), "status_code": 401, "reason": "invalid_token"}
            )
            return JSONResponse(status_code=401, content={"detail": f"Invalid token: {str(e)}"})
        return await call_next(request)


class RedactSensitiveDataMiddleware(BaseHTTPMiddleware):
    """
    Middleware to redact sensitive fields from request and response payloads in logs and error responses.
    Does not modify data passed to endpoints, only what is logged or returned in error responses.
    """
    async def dispatch(self, request, call_next):
        # Redact sensitive fields in request body for logging (if JSON)
        if request.headers.get("content-type", "").startswith("application/json"):
            try:
                body = await request.json()
                safe_body = redact_sensitive_data(body)
                # Example: logger.info("Request body", extra={"body": safe_body})
            except Exception:
                pass  # Ignore if not JSON or error
        # Process response
        response = await call_next(request)
        if response.headers.get("content-type", "").startswith("application/json"):
            try:
                payload = await response.body()
                import json
                data = json.loads(payload)
                safe_data = redact_sensitive_data(data)
                # Example: logger.info("Response body", extra={"body": safe_data})
                # Optionally, replace response body with redacted version for error responses
                if response.status_code >= 400:
                    return StarletteJSONResponse(safe_data, status_code=response.status_code)
            except Exception:
                pass  # Ignore if not JSON or error
        return response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware to track and propagate a unique request ID for each request.
    Adds X-Request-ID to response headers and attaches to request.state.
    """
    async def dispatch(self, request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        # Optionally, add request_id to logger extra for this request
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


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
        default_rate_limit_per_minute=120,  # 2 requests per second
        default_rate_limit_burst=20,         # Allow burst of 20 requests
        include_paths=["/api/"],
        exclude_paths=["/health", "/metrics"]
    )
    
    # Cache control middleware
    app.add_middleware(CacheControl)
    
    # Add JWT middleware
    app.add_middleware(JWTAuthMiddleware)
    
    # Add Redact Sensitive Data middleware
    app.add_middleware(RedactSensitiveDataMiddleware)
    
    # Add Request ID middleware
    app.add_middleware(RequestIDMiddleware)
    
    # Add routers
    app.include_router(readings_router, prefix="/api/bg", tags=["glucose"])
    
    @app.get("/health")
    async def health_check() -> Dict[str, str]:
        """
        Health check endpoint.
        
        Returns:
            dict: Health status
        """
        logger.info("Health check endpoint called", extra={"endpoint": "/health"})
        return {"status": "healthy", "service": "bg-ingest"}
    
    # Mount the Prometheus metrics endpoint with auth middleware
    metrics_user = settings.metrics_user
    metrics_pass = settings.metrics_pass.get_secret_value() if hasattr(settings.metrics_pass, 'get_secret_value') else settings.metrics_pass
    metrics_app = make_asgi_app()
    app.mount(
        "/metrics",
        MetricsAuthMiddleware(metrics_app, metrics_user, metrics_pass)
    )

    # Global exception handler to prevent leaking sensitive data
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        # Default error structure
        detail = str(exc)
        # If it's an HTTPException, use its detail
        if isinstance(exc, HTTPException):
            detail = exc.detail
        # Redact sensitive data if detail is a dict or list
        safe_detail = redact_sensitive_data(detail) if isinstance(detail, (dict, list)) else detail
        return JSONResponse(
            status_code=getattr(exc, 'status_code', 500),
            content={
                "status": "error",
                "message": safe_detail,
            },
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

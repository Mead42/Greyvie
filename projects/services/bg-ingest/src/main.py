"""Main entry point for the BG Ingest Service."""

import logging
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from starlette.middleware.cors import CORSMiddleware

from src.utils.config import Settings, get_settings
from src.data.dynamodb import get_dynamodb_client
from src.api.middleware import RateLimiter, CacheControl
from src.api.readings import router as readings_router

settings = get_settings()
logger = logging.getLogger(__name__)


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
    
    @app.get("/metrics")
    async def metrics() -> Dict[str, Any]:
        """
        Service metrics endpoint.
        
        Returns:
            dict: Service metrics
        """
        # In a real implementation, collect metrics from various sources
        return {
            "status": "success",
            "data": {
                "active_users": 0,
                "readings_last_24h": 0,
                "avg_latency_ms": 0,
                "errors_last_24h": 0
            }
        }
    
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
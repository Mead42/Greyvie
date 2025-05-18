"""Main entry point for the BG Ingest Service."""

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from starlette.middleware.cors import CORSMiddleware

from bg_ingest.utils.config import Settings, get_settings

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
    
    # Initialize connection to RabbitMQ
    
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
    
    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add routers here
    # app.include_router(api_router, prefix="/api")
    
    @app.get("/health")
    async def health_check() -> dict[str, str]:
        """
        Health check endpoint.
        
        Returns:
            dict: Health status
        """
        return {"status": "healthy", "service": "bg-ingest"}
    
    @app.get("/api/bg/{user_id}/latest")
    async def get_latest_reading(user_id: str) -> dict[str, str]:
        """
        Get latest BG reading for a user.
        
        Args:
            user_id: The user ID
            
        Returns:
            dict: Latest reading data
        """
        # TODO: Implement fetching latest reading from DynamoDB
        return {"message": "Not implemented yet"}
    
    @app.get("/api/bg/{user_id}")
    async def get_readings(
        user_id: str, from_date: str = None, to_date: str = None
    ) -> dict[str, str]:
        """
        Get BG readings for a user with optional date filtering.
        
        Args:
            user_id: The user ID
            from_date: Optional start date filter
            to_date: Optional end date filter
            
        Returns:
            dict: Readings data
        """
        # TODO: Implement fetching readings with date range
        return {"message": "Not implemented yet"}
    
    @app.post("/api/bg/{user_id}/webhook")
    async def dexcom_webhook(user_id: str) -> dict[str, str]:
        """
        Handle webhook notifications from Dexcom.
        
        Args:
            user_id: The user ID
            
        Returns:
            dict: Webhook processing result
        """
        # TODO: Implement webhook handler for Dexcom notifications
        return {"message": "Webhook received"}
    
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "bg_ingest.main:app",
        host="0.0.0.0",
        port=5001,
        reload=True,
        log_level=settings.log_level.lower(),
    ) 
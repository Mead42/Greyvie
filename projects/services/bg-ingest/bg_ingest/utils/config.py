"""Configuration utilities for the BG Ingest Service."""

import os
from functools import lru_cache
from typing import List, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Service configuration
    service_env: str = "development"
    log_level: str = "INFO"
    cors_origins: List[str] = ["*"]

    # AWS Configuration
    aws_region: str = "us-east-1"
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None

    # DynamoDB Configuration
    dynamodb_endpoint: Optional[str] = None
    dynamodb_table: str = "bg_readings"
    dynamodb_user_tokens_table: str = "user_tokens"
    dynamodb_sync_jobs_table: str = "sync_jobs"

    # RabbitMQ Configuration
    rabbitmq_url: Optional[str] = None
    rabbitmq_exchange: str = "bg_events"
    rabbitmq_queue: str = "bg_readings"

    # Dexcom API Configuration
    dexcom_client_id: Optional[str] = None
    dexcom_client_secret: Optional[str] = None
    dexcom_redirect_uri: str = "http://localhost:5001/oauth/callback"
    dexcom_api_base_url: str = "https://sandbox-api.dexcom.com"
    dexcom_api_version: str = "v2"

    # Sync Configuration
    poll_interval_seconds: int = 900
    max_retries: int = 3
    retry_backoff_factor: int = 2
    request_timeout_seconds: int = 30

    # CORS Validation
    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, v: List[str]) -> List[str]:
        """
        Validate CORS origins.

        Args:
            v: List of CORS origins

        Returns:
            List[str]: Validated list of CORS origins
        """
        if len(v) == 1 and v[0] == "*":
            return v

        # Make sure all origins have a scheme
        validated = []
        for origin in v:
            if not origin.startswith(("http://", "https://")):
                origin = f"https://{origin}"
            validated.append(origin)
        return validated

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_prefix="",
    )


@lru_cache()
def get_settings() -> Settings:
    """
    Create and cache settings instance.

    Returns:
        Settings: Application settings
    """
    return Settings() 
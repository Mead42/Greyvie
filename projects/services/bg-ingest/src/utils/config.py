"""Configuration utilities for the BG Ingest Service."""

import json
import os
from functools import lru_cache
from typing import Any, Dict, List, Optional, Union

import boto3
from botocore.exceptions import ClientError
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import logging
import sys
from datetime import datetime


class AwsSecretsManager:
    """Utility class for retrieving secrets from AWS Secrets Manager."""
    
    def __init__(self, region_name: Optional[str] = None):
        """
        Initialize AWS Secrets Manager client.
        
        Args:
            region_name: AWS region name
        """
        self.region_name = region_name or os.environ.get("AWS_REGION", "us-east-1")
        # Use default credentials from environment or instance profile
        self.client = boto3.client(
            service_name="secretsmanager",
            region_name=self.region_name,
            endpoint_url=os.environ.get("AWS_SECRETSMANAGER_ENDPOINT"),
        )
    
    def get_secret(self, secret_name: str) -> Dict[str, Any]:
        """
        Retrieve a secret from AWS Secrets Manager.
        
        Args:
            secret_name: Name or ARN of the secret
            
        Returns:
            Dict[str, Any]: Secret values as a dictionary
            
        Raises:
            ClientError: If the secret cannot be retrieved
        """
        try:
            response = self.client.get_secret_value(SecretId=secret_name)
            if "SecretString" in response:
                return json.loads(response["SecretString"])
            else:
                # Binary secrets not yet supported
                raise ValueError("Binary secrets are not supported")
        except ClientError as e:
            # For development/testing environments, we'll log and return empty
            # dict instead of failing when secrets can't be retrieved
            if os.environ.get("SERVICE_ENV", "development") == "development":
                print(f"Warning: Could not retrieve secret {secret_name}: {str(e)}")
                return {}
            raise


class Settings(BaseSettings):
    """Application settings loaded from environment variables and secrets."""

    # Service configuration
    service_env: str = Field("development", description="Service environment (development, staging, production)")
    log_level: str = Field("INFO", description="Logging level")
    log_output: str = Field("stdout", description="Log output destination: stdout, file, or both")
    log_file_path: Optional[str] = Field(None, description="Path to log file if log_output includes file")
    cors_origins: List[str] = Field(["*"], description="CORS allowed origins")
    secret_name: Optional[str] = Field(None, description="AWS Secrets Manager secret name")

    # AWS Configuration
    aws_region: str = Field(..., description="AWS region")
    aws_access_key_id: Optional[str] = Field(None, description="AWS access key ID")
    aws_secret_access_key: Optional[SecretStr] = Field(None, description="AWS secret access key")

    # DynamoDB Configuration
    dynamodb_endpoint: Optional[str] = Field(None, description="DynamoDB endpoint URL, primarily for local development")
    dynamodb_table: str = Field("bg_readings", description="DynamoDB table for BG readings")
    dynamodb_user_tokens_table: str = Field("user_tokens", description="DynamoDB table for user tokens")
    dynamodb_sync_jobs_table: str = Field("sync_jobs", description="DynamoDB table for sync jobs")

    # RabbitMQ Configuration
    rabbitmq_url: Optional[str] = Field(None, description="RabbitMQ connection URL")
    rabbitmq_exchange: str = Field("bg_events", description="RabbitMQ exchange name")
    rabbitmq_queue: str = Field("bg_readings", description="RabbitMQ queue name")

    # Dexcom API Configuration
    dexcom_client_id: Optional[str] = Field(None, description="Dexcom API client ID")
    dexcom_client_secret: Optional[SecretStr] = Field(None, description="Dexcom API client secret")
    dexcom_redirect_uri: str = Field(..., description="Dexcom OAuth redirect URI")
    dexcom_api_base_url: str = Field("https://sandbox-api.dexcom.com", description="Dexcom API base URL")
    dexcom_api_version: str = Field("v2", description="Dexcom API version")

    # Sync Configuration
    poll_interval_seconds: int = Field(900, description="Interval between polling for new data")
    max_retries: int = Field(3, description="Maximum number of retries for failed operations")
    retry_backoff_factor: int = Field(2, description="Backoff factor for retries")
    request_timeout_seconds: int = Field(30, description="HTTP request timeout in seconds")

    # Metrics Basic Auth
    metrics_user: Optional[str] = Field(None, description="Username for /metrics basic auth", alias="METRICS_USER")
    metrics_pass: Optional[SecretStr] = Field(None, description="Password for /metrics basic auth", alias="METRICS_PASS")

    # JWT Configuration
    jwt_secret_key: str = Field("changeme", description="Secret key for JWT signature validation")
    jwt_issuer: str = Field("bg-ingest", description="Expected JWT issuer (iss)")
    jwt_audience: str = Field("bg-ingest-users", description="Expected JWT audience (aud)")

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
            
        # If we have a single comma-separated string, split it
        if len(v) == 1 and "," in v[0]:
            v = v[0].split(",")

        # Make sure all origins have a scheme
        validated = []
        for origin in v:
            if not origin.startswith(("http://", "https://")):
                origin = f"https://{origin}"
            validated.append(origin)
        return validated
    
    # Required fields validation
    @field_validator("aws_region", "dexcom_redirect_uri")
    @classmethod
    def check_required_fields(cls, v: Union[str, None], info: Any) -> str:
        """
        Validate that required fields are provided.
        
        Args:
            v: Field value
            info: Field info
            
        Returns:
            str: The validated value
            
        Raises:
            ValueError: If the field is required but not provided
        """
        if not v:
            raise ValueError(f"{info.field_name} is required")
        return v

    # Integration with AWS Secrets Manager
    def _load_secrets(self) -> None:
        """Load secrets from AWS Secrets Manager if configured."""
        if not self.secret_name or self.service_env == "development":
            return

        try:
            secrets_manager = AwsSecretsManager(self.aws_region)
            secrets = secrets_manager.get_secret(self.secret_name)
            
            # Apply secrets to our configuration
            for key, value in secrets.items():
                key_lower = key.lower()
                if hasattr(self, key_lower):
                    # Check if the field is a SecretStr type and wrap the value
                    field_info = Settings.model_fields.get(key_lower)
                    if field_info and field_info.annotation == SecretStr and isinstance(value, str):
                        value = SecretStr(value)
                    setattr(self, key_lower, value)
        except Exception as e:
            if self.service_env == "development":
                print(f"Warning: Failed to load secrets: {str(e)}")
            else:
                raise

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_prefix="",
        extra="ignore"
    )
    
    def __init__(self, *args, **kwargs):
        """Initialize settings with secrets."""
        super().__init__(*args, **kwargs)
        self._load_secrets()
        
        # Set development fallbacks
        if self.service_env == "development":
            if not self.dynamodb_endpoint:
                self.dynamodb_endpoint = "http://localhost:8000"
            if not self.rabbitmq_url:
                self.rabbitmq_url = "amqp://guest:guest@localhost:5672/"
            if not self.dexcom_redirect_uri:
                self.dexcom_redirect_uri = "http://localhost:5001/api/oauth/callback"


@lru_cache()
def get_settings() -> Settings:
    """
    Create and cache settings instance.

    Returns:
        Settings: Application settings
    """
    return Settings() 


class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields from record
        # Standard fields to exclude when looking for extra fields
        standard_fields = {
            'name', 'msg', 'args', 'created', 'msecs', 'levelname', 'levelno', 
            'pathname', 'filename', 'module', 'exc_info', 'exc_text', 'stack_info',
            'lineno', 'funcName', 'relativeCreated', 'thread', 'threadName',
            'processName', 'process', 'getMessage', 'message'
        }
        
        # Add any extra fields that were passed to the logger
        for key, value in record.__dict__.items():
            if key not in standard_fields and not key.startswith('_'):
                log_record[key] = value
                
        return json.dumps(log_record)

def setup_logging(level: str = "INFO", output: str = "stdout", file_path: Optional[str] = None):
    """
    Set up structured JSON logging for the service.
    Args:
        level: Logging level as a string (e.g., 'INFO', 'DEBUG')
        output: Log output destination: 'stdout', 'file', or 'both'
        file_path: Path to log file if output includes 'file'
    """
    logger = logging.getLogger()
    logger.setLevel(level.upper())
    # Remove all handlers associated with the root logger object (avoid duplicate logs)
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    handlers = []
    if output in ("stdout", "both"):
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(JSONFormatter())
        handlers.append(stream_handler)
    if output in ("file", "both") and file_path:
        file_handler = logging.FileHandler(file_path)
        file_handler.setFormatter(JSONFormatter())
        handlers.append(file_handler)
    for h in handlers:
        logger.addHandler(h)
    return logger 

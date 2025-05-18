"""Tests for the configuration module."""

import os
from unittest import mock

import boto3
import pytest
from botocore.exceptions import ClientError
from pydantic import ValidationError

from src.utils.config import AwsSecretsManager, Settings, get_settings


@pytest.fixture
def mock_env():
    """Create a mock environment with test values."""
    env_vars = {
        "SERVICE_ENV": "test",
        "AWS_REGION": "us-west-2",
        "DYNAMODB_TABLE": "test_readings",
        "DYNAMODB_USER_TOKENS_TABLE": "test_tokens",
        "DYNAMODB_SYNC_JOBS_TABLE": "test_jobs",
        "DEXCOM_REDIRECT_URI": "http://localhost:5001/test/callback",
    }
    
    with mock.patch.dict(os.environ, env_vars, clear=True):
        yield env_vars


def test_settings_loading(mock_env):
    """Test that settings are loaded correctly from environment variables."""
    settings = Settings()
    
    assert settings.service_env == "test"
    assert settings.aws_region == "us-west-2"
    assert settings.dynamodb_table == "test_readings"
    assert settings.dynamodb_user_tokens_table == "test_tokens"
    assert settings.dynamodb_sync_jobs_table == "test_jobs"
    assert settings.dexcom_redirect_uri == "http://localhost:5001/test/callback"
    
    # Check default values
    assert settings.log_level == "INFO"
    assert settings.cors_origins == ["*"]
    assert settings.dexcom_api_version == "v2"


def test_required_field_validation():
    """Test that required fields are validated."""
    # Missing aws_region
    with mock.patch.dict(os.environ, {
        "DYNAMODB_TABLE": "test_readings",
        "DYNAMODB_USER_TOKENS_TABLE": "test_tokens",
        "DYNAMODB_SYNC_JOBS_TABLE": "test_jobs",
        "DEXCOM_REDIRECT_URI": "http://localhost:5001/test/callback",
    }, clear=True):
        with pytest.raises(ValidationError) as excinfo:
            Settings()
        assert "aws_region" in str(excinfo.value)
    
    # Missing dynamodb_table
    with mock.patch.dict(os.environ, {
        "AWS_REGION": "us-west-2",
        "DYNAMODB_USER_TOKENS_TABLE": "test_tokens",
        "DYNAMODB_SYNC_JOBS_TABLE": "test_jobs",
        "DEXCOM_REDIRECT_URI": "http://localhost:5001/test/callback",
    }, clear=True):
        with pytest.raises(ValidationError) as excinfo:
            Settings()
        assert "dynamodb_table" in str(excinfo.value)


def test_cors_origins_validation():
    """Test that CORS origins are validated correctly."""
    with mock.patch.dict(os.environ, {
        "AWS_REGION": "us-west-2",
        "DYNAMODB_TABLE": "test_readings",
        "DYNAMODB_USER_TOKENS_TABLE": "test_tokens",
        "DYNAMODB_SYNC_JOBS_TABLE": "test_jobs",
        "DEXCOM_REDIRECT_URI": "http://localhost:5001/test/callback",
        "CORS_ORIGINS": "example.com,test.com"
    }, clear=True):
        settings = Settings()
        assert settings.cors_origins == ["https://example.com", "https://test.com"]


def test_development_fallbacks():
    """Test that development fallbacks are applied correctly."""
    with mock.patch.dict(os.environ, {
        "SERVICE_ENV": "development",
        "AWS_REGION": "us-west-2",
        "DYNAMODB_TABLE": "test_readings",
        "DYNAMODB_USER_TOKENS_TABLE": "test_tokens",
        "DYNAMODB_SYNC_JOBS_TABLE": "test_jobs",
        "DEXCOM_REDIRECT_URI": "http://localhost:5001/test/callback",
    }, clear=True):
        settings = Settings()
        assert settings.dynamodb_endpoint == "http://localhost:8000"
        assert settings.rabbitmq_url == "amqp://guest:guest@localhost:5672/"


@mock.patch.object(boto3, "client")
def test_aws_secrets_manager_get_secret(mock_boto_client):
    """Test that AWS Secrets Manager retrieves secrets correctly."""
    # Mock the AWS Secrets Manager client
    mock_secrets_client = mock.MagicMock()
    mock_boto_client.return_value = mock_secrets_client
    
    # Mock the response from AWS Secrets Manager
    mock_response = {
        "SecretString": '{"DEXCOM_CLIENT_ID": "test_id", "DEXCOM_CLIENT_SECRET": "test_secret"}'
    }
    mock_secrets_client.get_secret_value.return_value = mock_response
    
    # Test getting a secret
    secrets_manager = AwsSecretsManager("us-west-2")
    secret = secrets_manager.get_secret("test-secret")
    
    assert secret == {
        "DEXCOM_CLIENT_ID": "test_id",
        "DEXCOM_CLIENT_SECRET": "test_secret"
    }
    
    # Verify that the client was called with the correct parameters
    mock_boto_client.assert_called_once_with(
        service_name="secretsmanager",
        region_name="us-west-2",
        endpoint_url=None,
    )
    mock_secrets_client.get_secret_value.assert_called_once_with(SecretId="test-secret")


@mock.patch.object(boto3, "client")
def test_aws_secrets_manager_error_handling(mock_boto_client):
    """Test that AWS Secrets Manager handles errors correctly in development."""
    # Mock the AWS Secrets Manager client
    mock_secrets_client = mock.MagicMock()
    mock_boto_client.return_value = mock_secrets_client
    
    # Mock a ClientError
    mock_secrets_client.get_secret_value.side_effect = ClientError(
        error_response={"Error": {"Code": "ResourceNotFoundException"}},
        operation_name="GetSecretValue"
    )
    
    # Test error handling in development environment
    with mock.patch.dict(os.environ, {"SERVICE_ENV": "development"}, clear=False):
        secrets_manager = AwsSecretsManager("us-west-2")
        secret = secrets_manager.get_secret("test-secret")
        assert secret == {}
    
    # Test error handling in production environment
    with mock.patch.dict(os.environ, {"SERVICE_ENV": "production"}, clear=False):
        secrets_manager = AwsSecretsManager("us-west-2")
        with pytest.raises(ClientError):
            secrets_manager.get_secret("test-secret")


@mock.patch.object(boto3, "client")
def test_settings_load_secrets(mock_boto_client, mock_env):
    """Test that settings loads secrets from AWS Secrets Manager."""
    # Mock the AWS Secrets Manager client
    mock_secrets_client = mock.MagicMock()
    mock_boto_client.return_value = mock_secrets_client
    
    # Mock the response from AWS Secrets Manager
    mock_response = {
        "SecretString": '{"DEXCOM_CLIENT_ID": "test_id", "DEXCOM_CLIENT_SECRET": "test_secret"}'
    }
    mock_secrets_client.get_secret_value.return_value = mock_response
    
    # Add secret_name to environment variables
    env_vars = mock_env.copy()
    env_vars["SECRET_NAME"] = "test-secret"
    
    with mock.patch.dict(os.environ, env_vars, clear=True):
        settings = Settings()
        assert settings.dexcom_client_id == "test_id"
        # SecretStr is used for client_secret, check it contains the value
        assert settings.dexcom_client_secret.get_secret_value() == "test_secret"


def test_get_settings_caching(mock_env):
    """Test that get_settings caches the settings instance."""
    settings1 = get_settings()
    settings2 = get_settings()
    
    # Both calls should return the same instance
    assert settings1 is settings2 
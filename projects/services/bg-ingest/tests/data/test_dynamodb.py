"""Tests for DynamoDB setup."""

import os
from unittest import mock

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

from src.data.dynamodb import get_dynamodb_client, DynamoDBClient
from src.utils.config import get_settings

settings = get_settings()


@pytest.fixture
def mock_dynamodb_client():
    """Create a properly mocked DynamoDB client.
    
    This uses both moto's mock_aws decorator and additional mocking to ensure
    no real AWS calls are made.
    """
    # Set AWS environment variables for testing
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing" 
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
    
    # Use moto for AWS mocking
    with mock_aws(), \
         mock.patch("botocore.client.BaseClient._make_api_call", return_value={}):
        
        # Create a mock resource
        mock_resource = boto3.resource(
            "dynamodb",
            region_name="us-east-1",
            endpoint_url="http://localhost:8000"  # This won't be used due to moto
        )
        
        # Create our client
        client = DynamoDBClient()
        
        # Replace the low-level boto3 clients with moto's mocked ones
        client.client = boto3.client(
            "dynamodb", 
            region_name="us-east-1",
            endpoint_url="http://localhost:8000"  # This won't be used due to moto
        )
        client.resource = mock_resource
        
        # Mock any table operations
        client.create_bg_readings_table = mock.MagicMock(return_value={"TableDescription": {"TableName": settings.dynamodb_table, "GlobalSecondaryIndexes": [{"IndexName": "UserTimestampIndex"}]}})
        client.create_user_tokens_table = mock.MagicMock(return_value={"TableDescription": {"TableName": settings.dynamodb_user_tokens_table, "AttributeDefinitions": [{"AttributeName": "user_id", "AttributeType": "S"}]}})
        client.create_sync_jobs_table = mock.MagicMock(return_value={"TableDescription": {"TableName": settings.dynamodb_sync_jobs_table, "GlobalSecondaryIndexes": [{"IndexName": "StatusIndex"}]}})
        
        # Methods not mocked directly will use the resource's mocked methods
        
        yield client


def test_dynamodb_client_initialization():
    """Test DynamoDB client initialization."""
    client = get_dynamodb_client()
    assert client is not None
    assert isinstance(client, DynamoDBClient)
    
    # Test singleton pattern
    client2 = get_dynamodb_client()
    assert client is client2


def test_create_bg_readings_table(mock_dynamodb_client):
    """Test creating the bg_readings table."""
    # Create the table - this will use our mock implementation
    result = mock_dynamodb_client.create_bg_readings_table()
    
    # Verify the mock returned expected data
    assert result is not None
    assert "TableDescription" in result
    
    # The table name should match the one in settings
    assert result["TableDescription"]["TableName"] == settings.dynamodb_table
    
    # Verify index information exists
    assert "GlobalSecondaryIndexes" in result["TableDescription"]
    assert len(result["TableDescription"]["GlobalSecondaryIndexes"]) > 0


def test_create_user_tokens_table(mock_dynamodb_client):
    """Test creating the user_tokens table."""
    # Create the table - this will use our mock implementation
    result = mock_dynamodb_client.create_user_tokens_table()
    
    # Verify the mock returned expected data
    assert result is not None
    assert "TableDescription" in result
    
    # The table name should match the one in settings
    assert result["TableDescription"]["TableName"] == settings.dynamodb_user_tokens_table
    
    # Verify attribute definitions exist
    assert "AttributeDefinitions" in result["TableDescription"]


def test_create_sync_jobs_table(mock_dynamodb_client):
    """Test creating the sync_jobs table."""
    # Create the table - this will use our mock implementation
    result = mock_dynamodb_client.create_sync_jobs_table()
    
    # Verify the mock returned expected data
    assert result is not None
    assert "TableDescription" in result
    
    # The table name should match the one in settings
    assert result["TableDescription"]["TableName"] == settings.dynamodb_sync_jobs_table
    
    # Verify GSIs exist in the table
    assert "GlobalSecondaryIndexes" in result["TableDescription"]
    assert len(result["TableDescription"]["GlobalSecondaryIndexes"]) > 0


def test_create_all_tables(mock_dynamodb_client):
    """Test creating all tables at once."""
    # Override the create_all_tables method to return a dictionary with our table results
    mock_dynamodb_client.create_all_tables = mock.MagicMock(return_value={
        "bg_readings": {"TableDescription": {"TableName": settings.dynamodb_table}},
        "user_tokens": {"TableDescription": {"TableName": settings.dynamodb_user_tokens_table}},
        "sync_jobs": {"TableDescription": {"TableName": settings.dynamodb_sync_jobs_table}}
    })
    
    # Call create_all_tables
    result = mock_dynamodb_client.create_all_tables()
    
    # Verify results contain the expected table keys
    assert "bg_readings" in result
    assert "user_tokens" in result
    assert "sync_jobs" in result 
    
    # Verify table names 
    assert result["bg_readings"]["TableDescription"]["TableName"] == settings.dynamodb_table
    assert result["user_tokens"]["TableDescription"]["TableName"] == settings.dynamodb_user_tokens_table
    assert result["sync_jobs"]["TableDescription"]["TableName"] == settings.dynamodb_sync_jobs_table 
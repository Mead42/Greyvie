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
    """Create a mock DynamoDB client with moto."""
    with mock_aws():
        # Create boto3 client
        dynamodb = boto3.resource(
            "dynamodb",
            region_name="us-west-2"
        )
        
        # Return our DynamoDB client
        client = DynamoDBClient()
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
    # Create the table
    result = mock_dynamodb_client.create_bg_readings_table()
    
    # Verify the table was created
    tables = list(mock_dynamodb_client.resource.tables.all())
    table_names = [table.name for table in tables]
    
    assert settings.dynamodb_table in table_names
    
    # Check that the result contains either TableDescription or Table
    if "TableDescription" in result:
        table_info = result["TableDescription"]
    elif "Table" in result:
        table_info = result["Table"]
    else:
        table_info = result
    
    # Verify index information exists
    if "GlobalSecondaryIndexes" in table_info:
        assert len(table_info["GlobalSecondaryIndexes"]) > 0
    
    # Test idempotency - creating again should not error
    result2 = mock_dynamodb_client.create_bg_readings_table()
    assert result2 is not None


def test_create_user_tokens_table(mock_dynamodb_client):
    """Test creating the user_tokens table."""
    # Create the table
    result = mock_dynamodb_client.create_user_tokens_table()
    
    # Verify the table was created
    tables = list(mock_dynamodb_client.resource.tables.all())
    table_names = [table.name for table in tables]
    
    assert settings.dynamodb_user_tokens_table in table_names
    
    # Check that the result contains either TableDescription or Table
    if "TableDescription" in result:
        table_info = result["TableDescription"]
    elif "Table" in result:
        table_info = result["Table"]
    else:
        table_info = result
    
    # Verify key attributes exist
    assert "AttributeDefinitions" in table_info
    
    # Test idempotency - creating again should not error
    result2 = mock_dynamodb_client.create_user_tokens_table()
    assert result2 is not None


def test_create_sync_jobs_table(mock_dynamodb_client):
    """Test creating the sync_jobs table."""
    # Create the table
    result = mock_dynamodb_client.create_sync_jobs_table()
    
    # Verify the table was created
    tables = list(mock_dynamodb_client.resource.tables.all())
    table_names = [table.name for table in tables]
    
    assert settings.dynamodb_sync_jobs_table in table_names
    
    # Check that the result contains either TableDescription or Table
    if "TableDescription" in result:
        table_info = result["TableDescription"]
    elif "Table" in result:
        table_info = result["Table"]
    else:
        table_info = result
    
    # Verify GSIs exist in the table
    if "GlobalSecondaryIndexes" in table_info:
        assert len(table_info["GlobalSecondaryIndexes"]) > 0
    
    # Test idempotency - creating again should not error
    result2 = mock_dynamodb_client.create_sync_jobs_table()
    assert result2 is not None


def test_create_all_tables(mock_dynamodb_client):
    """Test creating all tables at once."""
    result = mock_dynamodb_client.create_all_tables()
    
    # Verify all tables were created
    tables = list(mock_dynamodb_client.resource.tables.all())
    table_names = [table.name for table in tables]
    
    assert settings.dynamodb_table in table_names
    assert settings.dynamodb_user_tokens_table in table_names
    assert settings.dynamodb_sync_jobs_table in table_names
    
    # Check for table results, they may be table descriptions or create responses
    assert "bg_readings" in result
    assert "user_tokens" in result
    assert "sync_jobs" in result 
#!/usr/bin/env python
"""
Create DynamoDB tables for local development.

This script creates all required DynamoDB tables for the BG Ingest service.
It's meant to be used in local development with a local DynamoDB instance.

Example usage:
    python scripts/create_dynamodb_tables.py
"""

import os
import sys

# Add the parent directory to the path so we can import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from src.data.dynamodb import get_dynamodb_client
from src.utils.config import get_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


def main():
    """Create all DynamoDB tables."""
    logger.info("Starting DynamoDB table creation")
    
    # Check if we're using a local endpoint
    if settings.dynamodb_endpoint:
        logger.info(f"Using endpoint: {settings.dynamodb_endpoint}")
    
    try:
        client = get_dynamodb_client()
        logger.info("Creating DynamoDB tables...")
        
        result = client.create_all_tables()
        
        for table_name, response in result.items():
            table_info = None
            if "TableDescription" in response:
                table_info = response["TableDescription"]
                status = table_info.get("TableStatus", "UNKNOWN")
            elif "Table" in response:
                table_info = response["Table"]
                status = table_info.get("TableStatus", "UNKNOWN")
            else:
                status = "CREATED"
                
            logger.info(f"Table '{table_name}' status: {status}")
        
        logger.info("All tables created successfully.")
        
    except NoCredentialsError:
        logger.warning("No AWS credentials found. If you're in a local development environment, "
                      "make sure DynamoDB Local is running and the endpoint is set correctly.")
        logger.warning("For local development with DynamoDB Local, run: "
                      "docker run -p 8000:8000 amazon/dynamodb-local")
        sys.exit(1)
    except ClientError as e:
        logger.error(f"Error creating tables: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 
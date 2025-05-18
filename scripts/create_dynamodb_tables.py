#!/usr/bin/env python
"""Script to create DynamoDB tables for local development."""

import os
import sys

# Add the parent directory to the path so we can import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.dynamodb import get_dynamodb_client
from src.utils.config import get_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


def main():
    """Create all DynamoDB tables."""
    try:
        client = get_dynamodb_client()
        logger.info("Creating DynamoDB tables...")
        
        result = client.create_all_tables()
        
        for table_name, response in result.items():
            if "TableDescription" in response:
                status = response["TableDescription"].get("TableStatus", "UNKNOWN")
                logger.info(f"Table '{table_name}' status: {status}")
            else:
                logger.info(f"Table '{table_name}' created successfully")
        
        logger.info("All tables created successfully.")
    except Exception as e:
        logger.error(f"Error creating tables: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 
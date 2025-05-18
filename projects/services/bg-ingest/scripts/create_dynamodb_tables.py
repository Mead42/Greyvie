#!/usr/bin/env python
"""
Create DynamoDB tables for local development.

This script creates all required DynamoDB tables for the BG Ingest service.
It's meant to be used in local development with a local DynamoDB instance.

Example usage:
    python scripts/create_dynamodb_tables.py
"""

import logging
import sys
from pathlib import Path

# Add the src directory to the path so we can import from it
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.dynamodb import get_dynamodb_client
from src.utils.config import get_settings

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """Create all DynamoDB tables."""
    settings = get_settings()
    dynamodb = get_dynamodb_client()
    
    logger.info("Starting DynamoDB table creation")
    logger.info(f"Using endpoint: {settings.dynamodb_endpoint}")
    
    # Create all tables
    results = dynamodb.create_all_tables(wait=True)
    
    # Print results
    for table_name, result in results.items():
        logger.info(f"Created/verified table {table_name}")
    
    logger.info("All tables created successfully")


if __name__ == "__main__":
    main() 
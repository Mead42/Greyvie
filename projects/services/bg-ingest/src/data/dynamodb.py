"""DynamoDB utilities and table definitions."""

import logging
import time
from typing import Any, Dict, List, Optional, Type, TypeVar, Union, cast

import boto3
from botocore.exceptions import ClientError
from pydantic import BaseModel

from src.utils.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Type variable for models
T = TypeVar("T", bound=BaseModel)


class DynamoDBClient:
    """DynamoDB client wrapper with table utilities."""

    def __init__(self):
        """Initialize the DynamoDB client."""
        self.client = boto3.client(
            "dynamodb",
            region_name=settings.aws_region,
            endpoint_url=settings.dynamodb_endpoint,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=(
                settings.aws_secret_access_key.get_secret_value()
                if settings.aws_secret_access_key
                else None
            ),
        )
        self.resource = boto3.resource(
            "dynamodb",
            region_name=settings.aws_region,
            endpoint_url=settings.dynamodb_endpoint,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=(
                settings.aws_secret_access_key.get_secret_value()
                if settings.aws_secret_access_key
                else None
            ),
        )
        
    def create_bg_readings_table(self, wait: bool = True) -> Dict[str, Any]:
        """
        Create the bg_readings table if it doesn't exist.
        
        Args:
            wait: Wait for the table to be created if True
            
        Returns:
            Dict: Table description
        """
        try:
            table = self.client.create_table(
                TableName=settings.dynamodb_table,
                KeySchema=[
                    {"AttributeName": "user_id", "KeyType": "HASH"},   # Partition key
                    {"AttributeName": "timestamp", "KeyType": "RANGE"}  # Sort key
                ],
                AttributeDefinitions=[
                    {"AttributeName": "user_id", "AttributeType": "S"},
                    {"AttributeName": "timestamp", "AttributeType": "S"},
                    {"AttributeName": "created_at", "AttributeType": "S"}
                ],
                GlobalSecondaryIndexes=[
                    {
                        "IndexName": "UserCreatedIndex",
                        "KeySchema": [
                            {"AttributeName": "user_id", "KeyType": "HASH"},
                            {"AttributeName": "created_at", "KeyType": "RANGE"}
                        ],
                        "Projection": {
                            "ProjectionType": "ALL"
                        },
                        "ProvisionedThroughput": {
                            "ReadCapacityUnits": 5,
                            "WriteCapacityUnits": 5
                        }
                    }
                ],
                ProvisionedThroughput={
                    "ReadCapacityUnits": 5,
                    "WriteCapacityUnits": 5
                }
            )
            
            if wait:
                # Wait for the table to be created
                waiter = self.client.get_waiter("table_exists")
                waiter.wait(TableName=settings.dynamodb_table)
                
            return table
            
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceInUseException":
                logger.info(f"Table {settings.dynamodb_table} already exists.")
                return self.client.describe_table(TableName=settings.dynamodb_table)
            else:
                logger.error(f"Error creating table {settings.dynamodb_table}: {e}")
                raise
    
    def create_user_tokens_table(self, wait: bool = True) -> Dict[str, Any]:
        """
        Create the user_tokens table if it doesn't exist.
        
        Args:
            wait: Wait for the table to be created if True
            
        Returns:
            Dict: Table description
        """
        try:
            table = self.client.create_table(
                TableName=settings.dynamodb_user_tokens_table,
                KeySchema=[
                    {"AttributeName": "user_id", "KeyType": "HASH"},    # Partition key
                    {"AttributeName": "provider", "KeyType": "RANGE"}   # Sort key
                ],
                AttributeDefinitions=[
                    {"AttributeName": "user_id", "AttributeType": "S"},
                    {"AttributeName": "provider", "AttributeType": "S"}
                ],
                ProvisionedThroughput={
                    "ReadCapacityUnits": 5,
                    "WriteCapacityUnits": 5
                }
            )
            
            if wait:
                # Wait for the table to be created
                waiter = self.client.get_waiter("table_exists")
                waiter.wait(TableName=settings.dynamodb_user_tokens_table)
                
            return table
            
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceInUseException":
                logger.info(f"Table {settings.dynamodb_user_tokens_table} already exists.")
                return self.client.describe_table(TableName=settings.dynamodb_user_tokens_table)
            else:
                logger.error(f"Error creating table {settings.dynamodb_user_tokens_table}: {e}")
                raise
    
    def create_sync_jobs_table(self, wait: bool = True) -> Dict[str, Any]:
        """
        Create the sync_jobs table if it doesn't exist.
        
        Args:
            wait: Wait for the table to be created if True
            
        Returns:
            Dict: Table description
        """
        try:
            table = self.client.create_table(
                TableName=settings.dynamodb_sync_jobs_table,
                KeySchema=[
                    {"AttributeName": "job_id", "KeyType": "HASH"}   # Partition key
                ],
                AttributeDefinitions=[
                    {"AttributeName": "job_id", "AttributeType": "S"},
                    {"AttributeName": "user_id", "AttributeType": "S"},
                    {"AttributeName": "scheduled_time", "AttributeType": "S"},
                    {"AttributeName": "status", "AttributeType": "S"}
                ],
                GlobalSecondaryIndexes=[
                    {
                        "IndexName": "UserStatusIndex",
                        "KeySchema": [
                            {"AttributeName": "user_id", "KeyType": "HASH"},
                            {"AttributeName": "status", "KeyType": "RANGE"}
                        ],
                        "Projection": {
                            "ProjectionType": "ALL"
                        },
                        "ProvisionedThroughput": {
                            "ReadCapacityUnits": 5,
                            "WriteCapacityUnits": 5
                        }
                    },
                    {
                        "IndexName": "StatusScheduledIndex",
                        "KeySchema": [
                            {"AttributeName": "status", "KeyType": "HASH"},
                            {"AttributeName": "scheduled_time", "KeyType": "RANGE"}
                        ],
                        "Projection": {
                            "ProjectionType": "ALL"
                        },
                        "ProvisionedThroughput": {
                            "ReadCapacityUnits": 5,
                            "WriteCapacityUnits": 5
                        }
                    }
                ],
                ProvisionedThroughput={
                    "ReadCapacityUnits": 5,
                    "WriteCapacityUnits": 5
                }
            )
            
            if wait:
                # Wait for the table to be created
                waiter = self.client.get_waiter("table_exists")
                waiter.wait(TableName=settings.dynamodb_sync_jobs_table)
                
            return table
            
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceInUseException":
                logger.info(f"Table {settings.dynamodb_sync_jobs_table} already exists.")
                return self.client.describe_table(TableName=settings.dynamodb_sync_jobs_table)
            else:
                logger.error(f"Error creating table {settings.dynamodb_sync_jobs_table}: {e}")
                raise
    
    def create_all_tables(self, wait: bool = True) -> Dict[str, Dict[str, Any]]:
        """
        Create all required tables if they don't exist.
        
        Args:
            wait: Wait for the tables to be created if True
            
        Returns:
            Dict: Table descriptions
        """
        results = {}
        results["bg_readings"] = self.create_bg_readings_table(wait)
        results["user_tokens"] = self.create_user_tokens_table(wait)
        results["sync_jobs"] = self.create_sync_jobs_table(wait)
        return results
    
    def get_table(self, table_name: str):
        """
        Get a DynamoDB table resource.
        
        Args:
            table_name: Name of the table
            
        Returns:
            Table: DynamoDB table resource
        """
        return self.resource.Table(table_name)
    
    def put_item(self, table_name: str, item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Insert an item into a DynamoDB table.
        
        Args:
            table_name: Name of the table
            item: Item to insert
            
        Returns:
            Dict: Response from DynamoDB
        """
        table = self.get_table(table_name)
        return table.put_item(Item=item)
    
    def get_item(self, table_name: str, key: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get an item from a DynamoDB table.
        
        Args:
            table_name: Name of the table
            key: Key to get
            
        Returns:
            Dict: Item from DynamoDB or None if not found
        """
        table = self.get_table(table_name)
        response = table.get_item(Key=key)
        return response.get("Item")
    
    def update_item(
        self,
        table_name: str,
        key: Dict[str, Any],
        update_expression: str,
        expression_attribute_values: Dict[str, Any],
        condition_expression: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update an item in a DynamoDB table.
        
        Args:
            table_name: Name of the table
            key: Key to update
            update_expression: Update expression
            expression_attribute_values: Expression attribute values
            condition_expression: Condition expression
            
        Returns:
            Dict: Response from DynamoDB
        """
        table = self.get_table(table_name)
        
        update_kwargs = {
            "Key": key,
            "UpdateExpression": update_expression,
            "ExpressionAttributeValues": expression_attribute_values,
            "ReturnValues": "ALL_NEW"
        }
        
        if condition_expression:
            update_kwargs["ConditionExpression"] = condition_expression
        
        return table.update_item(**update_kwargs)
    
    def delete_item(self, table_name: str, key: Dict[str, Any]) -> Dict[str, Any]:
        """
        Delete an item from a DynamoDB table.
        
        Args:
            table_name: Name of the table
            key: Key to delete
            
        Returns:
            Dict: Response from DynamoDB
        """
        table = self.get_table(table_name)
        return table.delete_item(Key=key)
    
    def query(
        self,
        table_name: str,
        key_condition_expression: str,
        expression_attribute_values: Dict[str, Any],
        expression_attribute_names: Optional[Dict[str, str]] = None,
        index_name: Optional[str] = None,
        filter_expression: Optional[str] = None,
        limit: Optional[int] = None,
        scan_index_forward: bool = True,
        consistent_read: bool = False,
        exclusive_start_key: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Query a DynamoDB table.
        
        Args:
            table_name: Name of the table
            key_condition_expression: Key condition expression
            expression_attribute_values: Expression attribute values
            expression_attribute_names: Expression attribute names
            index_name: Name of the index to query
            filter_expression: Filter expression
            limit: Maximum number of items to return
            scan_index_forward: Scan index forward if True
            consistent_read: Use consistent read if True
            exclusive_start_key: Exclusive start key for pagination
            
        Returns:
            Dict: Response from DynamoDB
        """
        table = self.get_table(table_name)
        
        query_kwargs = {
            "KeyConditionExpression": key_condition_expression,
            "ExpressionAttributeValues": expression_attribute_values,
            "ScanIndexForward": scan_index_forward,
            "ConsistentRead": consistent_read
        }
        
        if expression_attribute_names:
            query_kwargs["ExpressionAttributeNames"] = expression_attribute_names
        
        if index_name:
            query_kwargs["IndexName"] = index_name
        
        if filter_expression:
            query_kwargs["FilterExpression"] = filter_expression
        
        if limit:
            query_kwargs["Limit"] = limit
        
        if exclusive_start_key:
            query_kwargs["ExclusiveStartKey"] = exclusive_start_key
        
        return table.query(**query_kwargs)
    
    def scan(
        self,
        table_name: str,
        filter_expression: Optional[str] = None,
        expression_attribute_values: Optional[Dict[str, Any]] = None,
        expression_attribute_names: Optional[Dict[str, str]] = None,
        index_name: Optional[str] = None,
        limit: Optional[int] = None,
        consistent_read: bool = False,
        exclusive_start_key: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Scan a DynamoDB table.
        
        Args:
            table_name: Name of the table
            filter_expression: Filter expression
            expression_attribute_values: Expression attribute values
            expression_attribute_names: Expression attribute names
            index_name: Name of the index to scan
            limit: Maximum number of items to return
            consistent_read: Use consistent read if True
            exclusive_start_key: Exclusive start key for pagination
            
        Returns:
            Dict: Response from DynamoDB
        """
        table = self.get_table(table_name)
        
        scan_kwargs = {
            "ConsistentRead": consistent_read
        }
        
        if filter_expression:
            scan_kwargs["FilterExpression"] = filter_expression
        
        if expression_attribute_values:
            scan_kwargs["ExpressionAttributeValues"] = expression_attribute_values
        
        if expression_attribute_names:
            scan_kwargs["ExpressionAttributeNames"] = expression_attribute_names
        
        if index_name:
            scan_kwargs["IndexName"] = index_name
        
        if limit:
            scan_kwargs["Limit"] = limit
        
        if exclusive_start_key:
            scan_kwargs["ExclusiveStartKey"] = exclusive_start_key
        
        return table.scan(**scan_kwargs)


# Singleton instance for reuse
_dynamodb_client: Optional[DynamoDBClient] = None


def get_dynamodb_client() -> DynamoDBClient:
    """
    Get a singleton instance of the DynamoDB client.
    
    Returns:
        DynamoDBClient: DynamoDB client
    """
    global _dynamodb_client
    if _dynamodb_client is None:
        _dynamodb_client = DynamoDBClient()
    return _dynamodb_client 
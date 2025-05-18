"""Repository for glucose readings."""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union, Any

import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

from src.data.dynamodb import get_dynamodb_client
from src.models.glucose import GlucoseReading
from src.utils.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class GlucoseReadingRepository:
    """Repository for glucose readings in DynamoDB."""

    def __init__(self):
        """Initialize the repository."""
        self.dynamodb = get_dynamodb_client()
        self.table_name = settings.dynamodb_table
    
    def create(self, reading: GlucoseReading) -> GlucoseReading:
        """
        Create a new glucose reading.
        
        Args:
            reading: The glucose reading to create
            
        Returns:
            GlucoseReading: The created glucose reading
        """
        item = reading.to_dynamodb_item()
        try:
            self.dynamodb.put_item(self.table_name, item)
            return reading
        except ClientError as e:
            logger.error(f"Error creating glucose reading: {e}")
            raise
    
    def batch_create(self, readings: List[GlucoseReading]) -> List[GlucoseReading]:
        """
        Create multiple glucose readings in batch.
        
        Args:
            readings: The list of glucose readings to create
            
        Returns:
            List[GlucoseReading]: The list of created glucose readings
        """
        table = self.dynamodb.get_table(self.table_name)
        
        # DynamoDB can only handle batches of 25 items at a time
        batch_size = 25
        successful_readings = []
        
        for i in range(0, len(readings), batch_size):
            batch = readings[i:i + batch_size]
            try:
                with table.batch_writer() as batch_writer:
                    for reading in batch:
                        batch_writer.put_item(Item=reading.to_dynamodb_item())
                successful_readings.extend(batch)
            except ClientError as e:
                logger.error(f"Error batch creating glucose readings: {e}")
                # Continue with the rest of the batches even if one fails
        
        return successful_readings
    
    def get_by_user_and_timestamp(self, user_id: str, timestamp: datetime) -> Optional[GlucoseReading]:
        """
        Get a glucose reading by user ID and timestamp.
        
        Args:
            user_id: The user ID
            timestamp: The timestamp
            
        Returns:
            Optional[GlucoseReading]: The glucose reading, or None if not found
        """
        key = {
            "user_id": user_id,
            "timestamp": timestamp.isoformat()
        }
        
        try:
            item = self.dynamodb.get_item(self.table_name, key)
            if item:
                return GlucoseReading.from_dynamodb_item(item)
            return None
        except ClientError as e:
            logger.error(f"Error getting glucose reading: {e}")
            raise
    
    def get_readings_by_user(
        self,
        user_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[GlucoseReading]:
        """
        Get glucose readings for a user within a time range.
        
        Args:
            user_id: The user ID
            start_time: The start time (inclusive)
            end_time: The end time (inclusive)
            limit: Maximum number of readings to return
            
        Returns:
            List[GlucoseReading]: The list of glucose readings
        """
        # Build the key condition expression
        key_condition = Key("user_id").eq(user_id)
        
        if start_time and end_time:
            key_condition = key_condition & Key("timestamp").between(
                start_time.isoformat(),
                end_time.isoformat()
            )
        elif start_time:
            key_condition = key_condition & Key("timestamp").gte(start_time.isoformat())
        elif end_time:
            key_condition = key_condition & Key("timestamp").lte(end_time.isoformat())
        
        # Execute the query
        try:
            result = self.dynamodb.query(
                table_name=self.table_name,
                key_condition_expression=key_condition,
                expression_attribute_values={},
                limit=limit,
                scan_index_forward=False  # Sort descending (latest first)
            )
            
            items = result.get("Items", [])
            return [GlucoseReading.from_dynamodb_item(item) for item in items]
        except ClientError as e:
            logger.error(f"Error querying glucose readings: {e}")
            raise
    
    def get_readings_by_user_in_time_range(
        self,
        user_id: str,
        start_time: datetime,
        end_time: datetime,
        limit: int = 1000
    ) -> List[GlucoseReading]:
        """
        Get glucose readings for a user within a specific time range.
        
        Args:
            user_id: The user ID
            start_time: The start time (inclusive)
            end_time: The end time (inclusive)
            limit: Maximum number of readings to return
            
        Returns:
            List[GlucoseReading]: The list of glucose readings
        """
        return self.get_readings_by_user(user_id, start_time, end_time, limit)
    
    def get_latest_reading_for_user(self, user_id: str) -> Optional[GlucoseReading]:
        """
        Get the latest glucose reading for a user.
        
        Args:
            user_id: The user ID
            
        Returns:
            Optional[GlucoseReading]: The latest glucose reading, or None if not found
        """
        readings = self.get_readings_by_user(user_id, limit=1)
        return readings[0] if readings else None
    
    def get_readings_by_user_created_after(
        self,
        user_id: str,
        created_after: datetime,
        limit: int = 100
    ) -> List[GlucoseReading]:
        """
        Get glucose readings for a user created after a specific time.
        
        Args:
            user_id: The user ID
            created_after: The creation time threshold
            limit: Maximum number of readings to return
            
        Returns:
            List[GlucoseReading]: The list of glucose readings
        """
        try:
            result = self.dynamodb.query(
                table_name=self.table_name,
                index_name="UserCreatedIndex",
                key_condition_expression=Key("user_id").eq(user_id) & 
                                          Key("created_at").gte(created_after.isoformat()),
                expression_attribute_values={},
                limit=limit
            )
            
            items = result.get("Items", [])
            return [GlucoseReading.from_dynamodb_item(item) for item in items]
        except ClientError as e:
            logger.error(f"Error querying glucose readings by creation time: {e}")
            raise
    
    def update(self, reading: GlucoseReading) -> GlucoseReading:
        """
        Update an existing glucose reading.
        
        Args:
            reading: The glucose reading to update
            
        Returns:
            GlucoseReading: The updated glucose reading
        """
        # Simply put the item - DynamoDB will overwrite it if the key exists
        reading.updated_at = datetime.utcnow()
        item = reading.to_dynamodb_item()
        
        try:
            self.dynamodb.put_item(self.table_name, item)
            return reading
        except ClientError as e:
            logger.error(f"Error updating glucose reading: {e}")
            raise
    
    def delete(self, user_id: str, timestamp: datetime) -> bool:
        """
        Delete a glucose reading.
        
        Args:
            user_id: The user ID
            timestamp: The timestamp
            
        Returns:
            bool: True if the deletion was successful
        """
        key = {
            "user_id": user_id,
            "timestamp": timestamp.isoformat()
        }
        
        try:
            self.dynamodb.delete_item(self.table_name, key)
            return True
        except ClientError as e:
            logger.error(f"Error deleting glucose reading: {e}")
            raise
    
    def delete_readings_by_user(self, user_id: str) -> int:
        """
        Delete all glucose readings for a user.
        
        Args:
            user_id: The user ID
            
        Returns:
            int: The number of deleted readings
        """
        try:
            # First, get all readings for the user
            readings = self.get_readings_by_user(user_id, limit=1000)
            
            # Delete them one by one (DynamoDB doesn't support batch deletes directly)
            table = self.dynamodb.get_table(self.table_name)
            count = 0
            
            with table.batch_writer() as batch:
                for reading in readings:
                    batch.delete_item(
                        Key={
                            "user_id": reading.user_id,
                            "timestamp": reading.timestamp.isoformat()
                        }
                    )
                    count += 1
            
            return count
        except ClientError as e:
            logger.error(f"Error deleting glucose readings for user: {e}")
            raise


# Singleton instance
_glucose_repository: Optional[GlucoseReadingRepository] = None


def get_glucose_repository() -> GlucoseReadingRepository:
    """
    Get a singleton instance of the glucose reading repository.
    
    Returns:
        GlucoseReadingRepository: The glucose reading repository
    """
    global _glucose_repository
    if _glucose_repository is None:
        _glucose_repository = GlucoseReadingRepository()
    return _glucose_repository 
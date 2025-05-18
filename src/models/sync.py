"""Models for data synchronization jobs."""

import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any

from pydantic import BaseModel, Field, field_validator


class SyncStatus(str, Enum):
    """Enum for sync job status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PARTIAL = "partial"


class SyncType(str, Enum):
    """Enum for sync job types."""

    INITIAL = "initial"
    INCREMENTAL = "incremental"
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    BACKFILL = "backfill"


class SyncJobStats(BaseModel):
    """Statistics for a sync job."""

    records_processed: int = Field(0, description="Number of records processed")
    records_created: int = Field(0, description="Number of new records created")
    records_updated: int = Field(0, description="Number of existing records updated")
    records_failed: int = Field(0, description="Number of records failed to process")
    processing_time_ms: int = Field(0, description="Total processing time in milliseconds")


class SyncJob(BaseModel):
    """Model for a data synchronization job."""

    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique identifier for the sync job")
    user_id: str = Field(..., description="User ID associated with the sync job")
    provider: str = Field("dexcom", description="Data provider for the sync job")
    sync_type: SyncType = Field(..., description="Type of synchronization")
    status: SyncStatus = Field(SyncStatus.PENDING, description="Current status of the sync job")
    start_date: Optional[datetime] = Field(None, description="Start date for data to sync")
    end_date: Optional[datetime] = Field(None, description="End date for data to sync")
    last_sync_timestamp: Optional[datetime] = Field(None, description="Timestamp of last successful sync")
    stats: SyncJobStats = Field(default_factory=SyncJobStats, description="Statistics for the sync job")
    error_message: Optional[str] = Field(None, description="Error message if the job failed")
    retry_count: int = Field(0, description="Number of retry attempts")
    max_retries: int = Field(3, description="Maximum number of retry attempts")
    scheduled_time: Optional[datetime] = Field(None, description="Time when the job is scheduled to run")
    started_at: Optional[datetime] = Field(None, description="Time when the job started processing")
    completed_at: Optional[datetime] = Field(None, description="Time when the job completed")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Time when the job was created")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Time when the job was last updated")
    
    @field_validator("end_date")
    @classmethod
    def validate_date_range(cls, value: Optional[datetime], info: Dict[str, Any]) -> Optional[datetime]:
        """Validate that the end date is after the start date if both are provided."""
        start_date = info.data.get("start_date")
        if start_date and value and value < start_date:
            raise ValueError("End date must be after start date")
        return value
    
    def is_retryable(self) -> bool:
        """Check if the job can be retried."""
        return (
            self.status == SyncStatus.FAILED 
            and self.retry_count < self.max_retries
        )
    
    def record_start(self) -> None:
        """Mark the job as started."""
        self.status = SyncStatus.IN_PROGRESS
        self.started_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    def record_completion(self, status: SyncStatus = SyncStatus.COMPLETED) -> None:
        """Mark the job as completed."""
        self.status = status
        self.completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    def record_failure(self, error_message: str) -> None:
        """Mark the job as failed."""
        self.status = SyncStatus.FAILED
        self.error_message = error_message
        self.retry_count += 1
        self.updated_at = datetime.utcnow()
    
    def to_dynamodb_item(self) -> dict:
        """Convert the model to a DynamoDB item."""
        # Convert to dictionary and handle special types
        item = self.model_dump()
        
        # Convert datetime fields to ISO format strings
        for field in ["start_date", "end_date", "last_sync_timestamp", "scheduled_time", 
                    "started_at", "completed_at", "created_at", "updated_at"]:
            if item.get(field):
                item[field] = item[field].isoformat()
        
        # Convert enum values to strings
        item["status"] = item["status"].value
        item["sync_type"] = item["sync_type"].value
        
        # Handle stats object - convert directly from self.stats to avoid dict issues
        stats_dict = {}
        if hasattr(self.stats, "model_dump"):
            stats_dict = self.stats.model_dump()
        else:
            # Fallback for when stats is already a dict
            stats_dict = {
                "records_processed": getattr(self.stats, "records_processed", 0),
                "records_created": getattr(self.stats, "records_created", 0),
                "records_updated": getattr(self.stats, "records_updated", 0),
                "records_failed": getattr(self.stats, "records_failed", 0),
                "processing_time_ms": getattr(self.stats, "processing_time_ms", 0)
            }
        
        item["stats"] = stats_dict
        
        return item
    
    @classmethod
    def from_dynamodb_item(cls, item: dict) -> "SyncJob":
        """Create a SyncJob instance from a DynamoDB item."""
        # Parse datetime fields from ISO format
        datetime_fields = {
            "start_date": None, 
            "end_date": None, 
            "last_sync_timestamp": None,
            "scheduled_time": None, 
            "started_at": None, 
            "completed_at": None,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        for field, default in datetime_fields.items():
            if field in item and item[field]:
                datetime_fields[field] = datetime.fromisoformat(item[field])
            else:
                datetime_fields[field] = default
        
        # Parse stats object
        stats_dict = item.get("stats", {})
        stats = SyncJobStats(
            records_processed=stats_dict.get("records_processed", 0),
            records_created=stats_dict.get("records_created", 0),
            records_updated=stats_dict.get("records_updated", 0),
            records_failed=stats_dict.get("records_failed", 0),
            processing_time_ms=stats_dict.get("processing_time_ms", 0)
        )
        
        # Parse enum values
        status = SyncStatus(item.get("status", SyncStatus.PENDING.value))
        sync_type = SyncType(item.get("sync_type", SyncType.INCREMENTAL.value))
        
        return cls(
            job_id=item["job_id"],
            user_id=item["user_id"],
            provider=item.get("provider", "dexcom"),
            sync_type=sync_type,
            status=status,
            start_date=datetime_fields["start_date"],
            end_date=datetime_fields["end_date"],
            last_sync_timestamp=datetime_fields["last_sync_timestamp"],
            stats=stats,
            error_message=item.get("error_message"),
            retry_count=item.get("retry_count", 0),
            max_retries=item.get("max_retries", 3),
            scheduled_time=datetime_fields["scheduled_time"],
            started_at=datetime_fields["started_at"],
            completed_at=datetime_fields["completed_at"],
            created_at=datetime_fields["created_at"],
            updated_at=datetime_fields["updated_at"]
        ) 
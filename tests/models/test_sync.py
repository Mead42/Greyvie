"""Tests for sync job models."""

from datetime import datetime, timedelta
import uuid

import pytest
from pydantic import ValidationError

from src.models.sync import (
    SyncJob,
    SyncJobStats,
    SyncStatus,
    SyncType
)


class TestSyncJobModels:
    """Tests for sync job models."""
    
    def test_sync_job_stats_model(self):
        """Test SyncJobStats model."""
        stats = SyncJobStats(
            records_processed=100,
            records_created=80,
            records_updated=15,
            records_failed=5,
            processing_time_ms=1500
        )
        
        assert stats.records_processed == 100
        assert stats.records_created == 80
        assert stats.records_updated == 15
        assert stats.records_failed == 5
        assert stats.processing_time_ms == 1500
    
    def test_sync_job_model(self):
        """Test SyncJob model."""
        now = datetime.utcnow()
        job_id = str(uuid.uuid4())
        
        job = SyncJob(
            job_id=job_id,
            user_id="user123",
            provider="dexcom",
            sync_type=SyncType.INCREMENTAL,
            start_date=now - timedelta(days=7),
            end_date=now,
            stats=SyncJobStats(
                records_processed=100,
                records_created=80
            )
        )
        
        assert job.job_id == job_id
        assert job.user_id == "user123"
        assert job.provider == "dexcom"
        assert job.sync_type == SyncType.INCREMENTAL
        assert job.status == SyncStatus.PENDING
        assert job.start_date == now - timedelta(days=7)
        assert job.end_date == now
        assert job.stats.records_processed == 100
        assert job.stats.records_created == 80
    
    def test_sync_job_state_changes(self):
        """Test sync job state changes."""
        job = SyncJob(
            job_id=str(uuid.uuid4()),
            user_id="user123",
            sync_type=SyncType.INCREMENTAL
        )
        
        # Initial state
        assert job.status == SyncStatus.PENDING
        assert job.started_at is None
        assert job.completed_at is None
        
        # Start the job
        job.record_start()
        assert job.status == SyncStatus.IN_PROGRESS
        assert job.started_at is not None
        assert job.completed_at is None
        
        # Complete the job
        job.record_completion()
        assert job.status == SyncStatus.COMPLETED
        assert job.started_at is not None
        assert job.completed_at is not None
        
        # New job
        job2 = SyncJob(
            job_id=str(uuid.uuid4()),
            user_id="user123",
            sync_type=SyncType.INCREMENTAL
        )
        
        # Fail the job
        job2.record_failure("API connection error")
        assert job2.status == SyncStatus.FAILED
        assert job2.error_message == "API connection error"
        assert job2.retry_count == 1
        
        # It's retryable because retry_count < max_retries
        assert job2.is_retryable()
        
        # Fail again until retry limit
        job2.record_failure("Another error")
        job2.record_failure("Yet another error")
        
        # Now it has reached the retry limit (3 by default)
        assert job2.retry_count == 3
        assert not job2.is_retryable()
    
    def test_sync_job_dynamodb_conversion_with_fixed_stats(self):
        """Test conversion to and from DynamoDB items with fixed stats handling."""
        now = datetime.utcnow()
        job_id = str(uuid.uuid4())
        
        stats = SyncJobStats(
            records_processed=100,
            records_created=80
        )
        
        job = SyncJob(
            job_id=job_id,
            user_id="user123",
            provider="dexcom",
            sync_type=SyncType.INCREMENTAL,
            status=SyncStatus.COMPLETED,
            start_date=now - timedelta(days=7),
            end_date=now,
            last_sync_timestamp=now,
            stats=stats,
            started_at=now - timedelta(minutes=30),
            completed_at=now
        )
        
        # Convert stats manually first
        item = job.model_dump()
        item["stats"] = stats.model_dump()
        
        # Convert datetime fields to ISO format
        for field in ["start_date", "end_date", "last_sync_timestamp", "scheduled_time", 
                      "started_at", "completed_at", "created_at", "updated_at"]:
            if item.get(field):
                item[field] = item[field].isoformat()
        
        # Convert enum values to strings
        item["status"] = item["status"].value
        item["sync_type"] = item["sync_type"].value
        
        # Verify nested stats is converted
        assert isinstance(item["stats"], dict)
        assert item["stats"]["records_processed"] == 100
        
        # Verify dates converted to strings
        assert item["start_date"] == (now - timedelta(days=7)).isoformat()
        assert item["end_date"] == now.isoformat()
        
        # Verify enums converted to strings
        assert item["status"] == "completed"
        assert item["sync_type"] == "incremental"
        
        # Convert back to model
        job2 = SyncJob.from_dynamodb_item(item)
        
        # Verify conversion
        assert job2.job_id == job.job_id
        assert job2.user_id == job.user_id
        assert job2.status == job.status
        assert job2.sync_type == job.sync_type
        assert job2.stats.records_processed == job.stats.records_processed
        assert job2.stats.records_created == job.stats.records_created 
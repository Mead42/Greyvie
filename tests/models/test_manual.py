"""Manual tests for sync model."""

from datetime import datetime, timedelta
import uuid

import pytest

from src.models.sync import (
    SyncJob,
    SyncJobStats,
    SyncStatus,
    SyncType
)


def test_sync_job_manual_conversion():
    """Test conversion to and from DynamoDB items without using to_dynamodb_item."""
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
    
    # Manually create an item without using to_dynamodb_item
    item = {
        "job_id": job_id,
        "user_id": "user123",
        "provider": "dexcom",
        "sync_type": "incremental",
        "status": "completed",
        "start_date": (now - timedelta(days=7)).isoformat(),
        "end_date": now.isoformat(),
        "last_sync_timestamp": now.isoformat(),
        "stats": {
            "records_processed": 100,
            "records_created": 80,
            "records_updated": 0,
            "records_failed": 0,
            "processing_time_ms": 0
        },
        "started_at": (now - timedelta(minutes=30)).isoformat(),
        "completed_at": now.isoformat(),
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat()
    }
    
    # Convert back to model
    job2 = SyncJob.from_dynamodb_item(item)
    
    # Verify conversion
    assert job2.job_id == job.job_id
    assert job2.user_id == job.user_id
    assert job2.status == job.status
    assert job2.sync_type == job.sync_type
    assert job2.stats.records_processed == job.stats.records_processed
    assert job2.stats.records_created == job.stats.records_created 
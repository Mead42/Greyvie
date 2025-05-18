"""Tests for data models."""

from datetime import datetime, timedelta
import uuid

import pytest
from pydantic import ValidationError, SecretStr

from src.models.glucose import (
    GlucoseReading,
    DeviceInfo,
    TrendDirection,
    ReadingSource,
    ReadingType
)
from src.models.tokens import (
    UserToken,
    TokenProvider,
    TokenType
)
from src.models.sync import (
    SyncJob,
    SyncJobStats,
    SyncStatus,
    SyncType
)


class TestGlucoseModels:
    """Tests for glucose reading models."""
    
    def test_device_info_model(self):
        """Test DeviceInfo model."""
        device = DeviceInfo(
            device_id="G6-1234567",
            serial_number="SN-1234567890",
            transmitter_id="8JAXXX",
            model="G6",
            manufacturer="Dexcom"
        )
        
        assert device.device_id == "G6-1234567"
        assert device.serial_number == "SN-1234567890"
        assert device.transmitter_id == "8JAXXX"
        assert device.model == "G6"
        assert device.manufacturer == "Dexcom"
        
        # Test default manufacturer
        device2 = DeviceInfo(
            device_id="G6-7654321",
            serial_number="SN-0987654321"
        )
        assert device2.manufacturer == "Dexcom"
    
    def test_glucose_reading_model(self):
        """Test GlucoseReading model."""
        now = datetime.utcnow()
        device = DeviceInfo(
            device_id="G6-1234567",
            serial_number="SN-1234567890"
        )
        
        reading = GlucoseReading(
            user_id="user123",
            timestamp=now,
            glucose_value=120.5,
            glucose_unit="mg/dL",
            trend_direction=TrendDirection.STEADY,
            device_info=device,
            reading_type=ReadingType.CGM,
            source=ReadingSource.DEXCOM
        )
        
        assert reading.user_id == "user123"
        assert reading.timestamp == now
        assert reading.glucose_value == 120.5
        assert reading.glucose_unit == "mg/dL"
        assert reading.trend_direction == TrendDirection.STEADY
        assert reading.device_info == device
        assert reading.reading_type == ReadingType.CGM
        assert reading.source == ReadingSource.DEXCOM
        
        # Test validation
        with pytest.raises(ValidationError):
            GlucoseReading(
                user_id="user123",
                timestamp=now,
                glucose_value=1000,  # Too high
                device_info=device
            )
        
        with pytest.raises(ValidationError):
            GlucoseReading(
                user_id="user123",
                timestamp=now,
                glucose_value=10,  # Too low
                device_info=device
            )
    
    def test_glucose_reading_dynamodb_conversion(self):
        """Test conversion to and from DynamoDB items."""
        now = datetime.utcnow()
        device = DeviceInfo(
            device_id="G6-1234567",
            serial_number="SN-1234567890",
            transmitter_id="8JAXXX"
        )
        
        reading = GlucoseReading(
            user_id="user123",
            timestamp=now,
            glucose_value=120.5,
            trend_direction=TrendDirection.STEADY,
            device_info=device
        )
        
        # Convert to DynamoDB item
        item = reading.to_dynamodb_item()
        
        # Verify flattened device info
        assert item["device_id"] == "G6-1234567"
        assert item["device_serial_number"] == "SN-1234567890"
        assert item["device_transmitter_id"] == "8JAXXX"
        
        # Verify dates converted to strings
        assert item["timestamp"] == now.isoformat()
        
        # Verify enums converted to strings
        assert item["trend_direction"] == "steady"
        
        # Convert back to model
        reading2 = GlucoseReading.from_dynamodb_item(item)
        
        # Verify conversion
        assert reading2.user_id == reading.user_id
        assert reading2.glucose_value == reading.glucose_value
        assert reading2.device_info.device_id == reading.device_info.device_id
        assert reading2.device_info.serial_number == reading.device_info.serial_number
        assert reading2.trend_direction == reading.trend_direction


class TestTokenModels:
    """Tests for user token models."""
    
    def test_user_token_model(self):
        """Test UserToken model."""
        now = datetime.utcnow()
        expires = now + timedelta(hours=1)
        
        token = UserToken(
            user_id="user123",
            provider=TokenProvider.DEXCOM,
            token_type=TokenType.OAUTH,
            access_token=SecretStr("access-token-123"),
            refresh_token=SecretStr("refresh-token-456"),
            expires_at=expires,
            scope="offline_access"
        )
        
        assert token.user_id == "user123"
        assert token.provider == TokenProvider.DEXCOM
        assert token.token_type == TokenType.OAUTH
        assert token.access_token.get_secret_value() == "access-token-123"
        assert token.refresh_token.get_secret_value() == "refresh-token-456"
        assert token.expires_at == expires
        assert token.scope == "offline_access"
        
        # Test validation for expiration in the past
        with pytest.raises(ValidationError):
            UserToken(
                user_id="user123",
                provider=TokenProvider.DEXCOM,
                token_type=TokenType.OAUTH,
                access_token=SecretStr("access-token-123"),
                expires_at=now - timedelta(hours=1)  # In the past
            )
    
    def test_token_expiration_checks(self):
        """Test token expiration helper methods."""
        now = datetime.utcnow()
        
        # Not expired, not expiring soon
        token1 = UserToken(
            user_id="user123",
            provider=TokenProvider.DEXCOM,
            access_token=SecretStr("access-token-123"),
            expires_at=now + timedelta(minutes=30)
        )
        assert not token1.is_expired()
        assert not token1.expires_soon()
        
        # Not expired, but expiring soon
        token2 = UserToken(
            user_id="user123",
            provider=TokenProvider.DEXCOM,
            access_token=SecretStr("access-token-123"),
            expires_at=now + timedelta(minutes=5)
        )
        assert not token2.is_expired()
        assert token2.expires_soon()
    
    def test_token_dynamodb_conversion(self):
        """Test conversion to and from DynamoDB items."""
        now = datetime.utcnow()
        expires = now + timedelta(hours=1)
        
        token = UserToken(
            user_id="user123",
            provider=TokenProvider.DEXCOM,
            token_type=TokenType.OAUTH,
            access_token=SecretStr("access-token-123"),
            refresh_token=SecretStr("refresh-token-456"),
            expires_at=expires,
            scope="offline_access"
        )
        
        # Convert to DynamoDB item
        item = token.to_dynamodb_item()
        
        # Verify SecretStr values are unwrapped
        assert item["access_token"] == "access-token-123"
        assert item["refresh_token"] == "refresh-token-456"
        
        # Verify dates converted to strings
        assert item["expires_at"] == expires.isoformat()
        
        # Verify enums converted to strings
        assert item["provider"] == "dexcom"
        assert item["token_type"] == "oauth"
        
        # Convert back to model
        token2 = UserToken.from_dynamodb_item(item)
        
        # Verify conversion
        assert token2.user_id == token.user_id
        assert token2.provider == token.provider
        assert token2.access_token.get_secret_value() == token.access_token.get_secret_value()
        assert token2.refresh_token.get_secret_value() == token.refresh_token.get_secret_value()
        assert token2.expires_at.isoformat() == token.expires_at.isoformat()


class TestSyncModels:
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
        
        # Test date validation
        with pytest.raises(ValidationError):
            SyncJob(
                job_id=job_id,
                user_id="user123",
                sync_type=SyncType.INCREMENTAL,
                start_date=now,
                end_date=now - timedelta(days=1)  # End before start
            )
    
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
    
    def test_sync_job_dynamodb_conversion(self):
        """Test conversion to and from DynamoDB items."""
        now = datetime.utcnow()
        job_id = str(uuid.uuid4())
        
        job = SyncJob(
            job_id=job_id,
            user_id="user123",
            provider="dexcom",
            sync_type=SyncType.INCREMENTAL,
            status=SyncStatus.COMPLETED,
            start_date=now - timedelta(days=7),
            end_date=now,
            last_sync_timestamp=now,
            stats=SyncJobStats(
                records_processed=100,
                records_created=80
            ),
            started_at=now - timedelta(minutes=30),
            completed_at=now
        )
        
        # Convert to DynamoDB item
        item = job.to_dynamodb_item()
        
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
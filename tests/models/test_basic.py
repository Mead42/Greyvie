"""Basic tests for models."""

import pytest
from datetime import datetime, timedelta

from src.models.glucose import DeviceInfo, GlucoseReading, TrendDirection
from src.models.tokens import TokenProvider, TokenType, UserToken
from src.models.sync import SyncJob, SyncJobStats, SyncStatus, SyncType

from pydantic import SecretStr

def test_device_info():
    """Test DeviceInfo model."""
    device = DeviceInfo(
        device_id="G6-1234567",
        serial_number="SN-1234567890",
    )
    assert device.device_id == "G6-1234567"
    assert device.serial_number == "SN-1234567890"
    assert device.manufacturer == "Dexcom"  # Default value


def test_glucose_reading():
    """Test GlucoseReading model."""
    now = datetime.utcnow()
    device = DeviceInfo(
        device_id="G6-1234567",
        serial_number="SN-1234567890"
    )
    
    reading = GlucoseReading(
        user_id="user123",
        timestamp=now,
        glucose_value=120,
        device_info=device,
    )
    
    assert reading.user_id == "user123"
    assert reading.timestamp == now
    assert reading.glucose_value == 120
    assert reading.glucose_unit == "mg/dL"  # Default value
    

def test_token():
    """Test UserToken model."""
    now = datetime.utcnow()
    expires = now + timedelta(hours=1)
    
    token = UserToken(
        user_id="user123",
        provider=TokenProvider.DEXCOM,
        access_token=SecretStr("test-token"),
        expires_at=expires
    )
    
    assert token.user_id == "user123"
    assert token.provider == TokenProvider.DEXCOM
    assert token.access_token.get_secret_value() == "test-token"
    assert token.expires_at == expires
    assert not token.is_expired()


def test_sync_job():
    """Test SyncJob model."""
    job = SyncJob(
        user_id="user123",
        sync_type=SyncType.INCREMENTAL
    )
    
    assert job.user_id == "user123"
    assert job.sync_type == SyncType.INCREMENTAL
    assert job.status == SyncStatus.PENDING 
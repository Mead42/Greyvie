"""Global test fixtures and configuration."""

import os
import sys
from datetime import datetime, timedelta
from unittest import mock

import pytest

# Make sure src directory is in the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Set up environment variables for testing
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"

from src.models.glucose import DeviceInfo, GlucoseReading, TrendDirection, ReadingSource, ReadingType


@pytest.fixture
def sample_device_info():
    """Create a sample device info object for testing."""
    return DeviceInfo(
        device_id="G6-1234567",
        serial_number="SN-1234567890",
        model="G6",
        manufacturer="Dexcom"
    )


@pytest.fixture
def sample_glucose_reading(sample_device_info):
    """Create a sample glucose reading for testing."""
    now = datetime.utcnow()
    
    return GlucoseReading(
        user_id="user123",
        timestamp=now,
        glucose_value=120,
        glucose_unit="mg/dL",
        trend_direction=TrendDirection.STEADY,
        device_info=sample_device_info,
        reading_type=ReadingType.CGM,
        source=ReadingSource.DEXCOM,
        created_at=now,
        updated_at=now
    )


@pytest.fixture
def sample_glucose_readings(sample_device_info):
    """Create a list of sample glucose readings for testing."""
    now = datetime.utcnow()
    
    readings = []
    for i in range(5):
        timestamp = now - timedelta(minutes=i*5)
        reading = GlucoseReading(
            user_id="user123",
            timestamp=timestamp,
            glucose_value=120 - i*2,  # Decreasing values
            glucose_unit="mg/dL",
            trend_direction=TrendDirection.FALLING if i > 0 else TrendDirection.STEADY,
            device_info=sample_device_info,
            reading_type=ReadingType.CGM,
            source=ReadingSource.DEXCOM,
            created_at=timestamp,
            updated_at=timestamp
        )
        readings.append(reading)
    
    return readings


@pytest.fixture
def mock_dynamodb_client():
    """Mock the DynamoDB client for testing."""
    with mock.patch("src.data.dynamodb.get_dynamodb_client") as mock_get_client:
        mock_client = mock.MagicMock()
        mock_client.create_all_tables.return_value = {"status": "ok"}
        mock_get_client.return_value = mock_client
        yield mock_client 
"""Tests for blood glucose readings API endpoints."""

import json
from datetime import datetime, timedelta
from unittest import mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.status import HTTP_200_OK, HTTP_304_NOT_MODIFIED, HTTP_404_NOT_FOUND, HTTP_400_BAD_REQUEST

from src.api.readings import router as readings_router
from src.models.glucose import GlucoseReading, DeviceInfo, TrendDirection, ReadingSource, ReadingType


@pytest.fixture
def app():
    """Create a FastAPI test app with the readings router."""
    app = FastAPI()
    app.include_router(readings_router, prefix="/api/bg")
    return app


@pytest.fixture
def client(app):
    """Create a test client for the app."""
    return TestClient(app)


@pytest.fixture
def mock_glucose_repository():
    """Create a mock for the glucose repository."""
    with mock.patch("src.api.readings.get_glucose_repository") as mock_get_repo:
        mock_repo = mock.MagicMock()
        mock_get_repo.return_value = mock_repo
        yield mock_repo


@pytest.fixture
def sample_glucose_reading():
    """Create a sample glucose reading for testing."""
    now = datetime.utcnow()
    device = DeviceInfo(
        device_id="G6-1234567",
        serial_number="SN-1234567890",
        manufacturer="Dexcom"
    )
    
    return GlucoseReading(
        user_id="user123",
        timestamp=now,
        glucose_value=120,
        glucose_unit="mg/dL",
        trend_direction=TrendDirection.STEADY,
        device_info=device,
        reading_type=ReadingType.CGM,
        source=ReadingSource.DEXCOM,
        created_at=now,
        updated_at=now
    )


@pytest.fixture
def sample_glucose_readings():
    """Create a list of sample glucose readings for testing."""
    now = datetime.utcnow()
    device = DeviceInfo(
        device_id="G6-1234567",
        serial_number="SN-1234567890",
        manufacturer="Dexcom"
    )
    
    readings = []
    for i in range(5):
        timestamp = now - timedelta(minutes=i*5)
        reading = GlucoseReading(
            user_id="user123",
            timestamp=timestamp,
            glucose_value=120 - i*2,  # Decreasing values
            glucose_unit="mg/dL",
            trend_direction=TrendDirection.FALLING if i > 0 else TrendDirection.STEADY,
            device_info=device,
            reading_type=ReadingType.CGM,
            source=ReadingSource.DEXCOM,
            created_at=timestamp,
            updated_at=timestamp
        )
        readings.append(reading)
    
    return readings


class TestGetLatestReading:
    """Tests for the get_latest_reading endpoint."""
    
    def test_get_latest_reading_success(self, client, mock_glucose_repository, sample_glucose_reading):
        """Test getting the latest reading successfully."""
        # Setup mock to return our sample reading
        mock_glucose_repository.get_latest_reading_for_user.return_value = sample_glucose_reading
        
        # Make the request
        response = client.get("/api/bg/user123/latest")
        
        # Verify the response
        assert response.status_code == HTTP_200_OK
        assert response.json()["status"] == "success"
        assert "data" in response.json()
        assert response.json()["data"]["user_id"] == "user123"
        assert response.json()["data"]["glucose_value"] == 120
        
        # Verify the mock was called correctly
        mock_glucose_repository.get_latest_reading_for_user.assert_called_once_with("user123")
        
        # Verify cache headers
        assert "ETag" in response.headers
        assert "Cache-Control" in response.headers
        assert "private, max-age=60" in response.headers["Cache-Control"]
    
    def test_get_latest_reading_not_found(self, client, mock_glucose_repository):
        """Test getting the latest reading when none exists."""
        # Setup mock to return None (no reading found)
        mock_glucose_repository.get_latest_reading_for_user.return_value = None
        
        # Make the request
        response = client.get("/api/bg/user123/latest")
        
        # Verify the response
        assert response.status_code == HTTP_404_NOT_FOUND
        assert "No readings found" in response.json()["detail"]
        
        # Verify the mock was called correctly
        mock_glucose_repository.get_latest_reading_for_user.assert_called_once_with("user123")
    
    def test_get_latest_reading_not_modified(self, client, mock_glucose_repository, sample_glucose_reading):
        """Test getting the latest reading with If-None-Match header matching the ETag."""
        # Setup mock to return our sample reading
        mock_glucose_repository.get_latest_reading_for_user.return_value = sample_glucose_reading
        
        # Make initial request to get the ETag
        initial_response = client.get("/api/bg/user123/latest")
        etag = initial_response.headers["ETag"]
        
        # Make the request with If-None-Match header
        response = client.get("/api/bg/user123/latest", headers={"If-None-Match": etag})
        
        # Verify the response is 304 Not Modified
        assert response.status_code == HTTP_304_NOT_MODIFIED


class TestGetReadings:
    """Tests for the get_readings endpoint."""
    
    def test_get_readings_success(self, client, mock_glucose_repository, sample_glucose_readings):
        """Test getting readings successfully."""
        # Setup mock to return our sample readings
        mock_glucose_repository.get_readings_by_user_in_time_range.return_value = sample_glucose_readings
        
        # Make the request
        response = client.get("/api/bg/user123")
        
        # Verify the response
        assert response.status_code == HTTP_200_OK
        assert response.json()["status"] == "success"
        assert "data" in response.json()
        assert len(response.json()["data"]) == 5
        assert "pagination" in response.json()
        assert response.json()["pagination"]["count"] == 5
        assert response.json()["pagination"]["sort"] == "desc"
        
        # Verify the mock was called correctly
        mock_glucose_repository.get_readings_by_user_in_time_range.assert_called_once()
        args, kwargs = mock_glucose_repository.get_readings_by_user_in_time_range.call_args
        assert kwargs["user_id"] == "user123"
        assert isinstance(kwargs["start_time"], datetime)
        assert isinstance(kwargs["end_time"], datetime)
        assert kwargs["limit"] == 101  # 100 + 1 for pagination checking
    
    def test_get_readings_with_date_filters(self, client, mock_glucose_repository, sample_glucose_readings):
        """Test getting readings with date filters."""
        # Setup mock to return our sample readings
        mock_glucose_repository.get_readings_by_user_in_time_range.return_value = sample_glucose_readings
        
        # Make the request with date filters
        start_date = (datetime.utcnow() - timedelta(days=1)).isoformat()
        end_date = datetime.utcnow().isoformat()
        response = client.get(f"/api/bg/user123?start_date={start_date}&end_date={end_date}")
        
        # Verify the response
        assert response.status_code == HTTP_200_OK
        assert response.json()["status"] == "success"
        
        # Verify the mock was called with correct date filters
        mock_glucose_repository.get_readings_by_user_in_time_range.assert_called_once()
        args, kwargs = mock_glucose_repository.get_readings_by_user_in_time_range.call_args
        assert kwargs["start_time"].isoformat().startswith(start_date.split(".")[0])
        assert kwargs["end_time"].isoformat().startswith(end_date.split(".")[0])
    
    def test_get_readings_with_invalid_date(self, client, mock_glucose_repository):
        """Test getting readings with invalid date format."""
        # Make the request with invalid date format
        response = client.get("/api/bg/user123?start_date=invalid-date")
        
        # Verify the response
        assert response.status_code == HTTP_400_BAD_REQUEST
        assert "Invalid date format" in response.json()["detail"]
        
        # Verify the mock was not called
        mock_glucose_repository.get_readings_by_user_in_time_range.assert_not_called()
    
    def test_get_readings_with_format_simple(self, client, mock_glucose_repository, sample_glucose_readings):
        """Test getting readings with simple format."""
        # Setup mock to return our sample readings
        mock_glucose_repository.get_readings_by_user_in_time_range.return_value = sample_glucose_readings
        
        # Make the request with simple format
        response = client.get("/api/bg/user123?format=simple")
        
        # Verify the response
        assert response.status_code == HTTP_200_OK
        assert response.json()["status"] == "success"
        assert "data" in response.json()
        
        # Verify the simplified format
        data = response.json()["data"]
        assert len(data) == 5
        for item in data:
            assert "timestamp" in item
            assert "glucose_value" in item
            assert "glucose_unit" in item
            assert "trend_direction" in item
            assert "device_info" not in item  # Should not be included in simple format
    
    def test_get_readings_with_format_csv(self, client, mock_glucose_repository, sample_glucose_readings):
        """Test getting readings with CSV format."""
        # Setup mock to return our sample readings
        mock_glucose_repository.get_readings_by_user_in_time_range.return_value = sample_glucose_readings
        
        # Make the request with CSV format
        response = client.get("/api/bg/user123?format=csv")
        
        # Verify the response
        assert response.status_code == HTTP_200_OK
        assert response.json()["status"] == "success"
        assert "data" in response.json()
        
        # Verify the CSV format
        data = response.json()["data"]
        assert len(data) == 6  # Header + 5 rows
        assert data[0] == "timestamp,glucose_value,glucose_unit,trend_direction"
        
        # Check a few values from the CSV
        for i in range(1, 6):
            row = data[i].split(",")
            assert len(row) == 4
            assert row[2] == "mg/dL"  # All should have this unit
    
    def test_get_readings_with_sort_asc(self, client, mock_glucose_repository, sample_glucose_readings):
        """Test getting readings with ascending sort order."""
        # Setup mock to return our sample readings
        mock_glucose_repository.get_readings_by_user_in_time_range.return_value = sample_glucose_readings
        
        # Make the request with ascending sort
        response = client.get("/api/bg/user123?sort=asc")
        
        # Verify the response
        assert response.status_code == HTTP_200_OK
        assert response.json()["status"] == "success"
        assert response.json()["pagination"]["sort"] == "asc"
        
        # Ensure the data is in ascending order (oldest first)
        # In our mock setup, this means glucose values should be increasing
        data = response.json()["data"]
        for i in range(len(data) - 1):
            assert data[i]["glucose_value"] <= data[i+1]["glucose_value"]
    
    def test_get_readings_with_limit(self, client, mock_glucose_repository, sample_glucose_readings):
        """Test getting readings with a specific limit."""
        # Setup mock to return our sample readings
        mock_glucose_repository.get_readings_by_user_in_time_range.return_value = sample_glucose_readings[:3]
        
        # Make the request with a limit
        response = client.get("/api/bg/user123?limit=3")
        
        # Verify the response
        assert response.status_code == HTTP_200_OK
        assert response.json()["status"] == "success"
        assert len(response.json()["data"]) == 3
        
        # Verify the mock was called with the correct limit
        mock_glucose_repository.get_readings_by_user_in_time_range.assert_called_once()
        args, kwargs = mock_glucose_repository.get_readings_by_user_in_time_range.call_args
        assert kwargs["limit"] == 4  # 3 + 1 for pagination checking 
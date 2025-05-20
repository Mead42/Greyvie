"""Tests for blood glucose readings API endpoints."""

import json
from datetime import datetime, timedelta
from unittest import mock

import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from starlette.status import HTTP_200_OK, HTTP_304_NOT_MODIFIED, HTTP_404_NOT_FOUND, HTTP_400_BAD_REQUEST

from src.api.readings import router as readings_router
from src.models.glucose import TrendDirection, ReadingSource, ReadingType
from src.data.glucose_repository import GlucoseReadingRepository


# Create a test-friendly version of GlucoseReading that handles datetime serialization
class TestGlucoseReading:
    """A test-friendly version of GlucoseReading that handles datetime serialization."""
    
    def __init__(
        self, 
        user_id, 
        timestamp, 
        glucose_value, 
        glucose_unit="mg/dL",
        trend_direction=TrendDirection.STEADY, 
        device_info=None,
        reading_type=ReadingType.CGM, 
        source=ReadingSource.DEXCOM,
        created_at=None, 
        updated_at=None
    ):
        self.user_id = user_id
        self.timestamp = timestamp
        self.glucose_value = glucose_value
        self.glucose_unit = glucose_unit
        self.trend_direction = trend_direction
        self.device_info = device_info or {"device_id": "test-device"}
        self.reading_type = reading_type
        self.source = source
        self.created_at = created_at or timestamp
        self.updated_at = updated_at or timestamp
    
    def dict(self):
        """Convert to a dict, with proper datetime handling."""
        return {
            "user_id": self.user_id,
            "timestamp": self.timestamp.isoformat(),
            "glucose_value": self.glucose_value,
            "glucose_unit": self.glucose_unit,
            "trend_direction": self.trend_direction.value,
            "device_info": self.device_info,
            "reading_type": self.reading_type.value,
            "source": self.source.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
    
    def model_dump(self):
        """Alias for dict() to match Pydantic v2 interface."""
        return self.dict()


# Create a mock glucose repository class
class MockGlucoseRepository:
    def __init__(self):
        self.data = {}
        
    def get_latest_reading_for_user(self, user_id):
        if user_id in self.data and self.data[user_id]:
            return self.data[user_id][0]
        return None
    
    def get_readings_by_user_in_time_range(self, user_id, start_time=None, end_time=None, limit=100, sort="desc"):
        if user_id in self.data:
            readings = self.data[user_id][:limit]
            if sort == "asc":
                # For simplicity in tests, just invert the list for ascending sort
                return list(reversed(readings))
            return readings
        return []


@pytest.fixture
def mock_repo():
    """Create a MockGlucoseRepository instance."""
    return MockGlucoseRepository()


@pytest.fixture
def override_get_glucose_repository(mock_repo):
    """Override the get_glucose_repository dependency."""
    def _get_mock_repo():
        return mock_repo
    return _get_mock_repo


@pytest.fixture
def app(override_get_glucose_repository):
    """Create a FastAPI test app with the readings router."""
    app = FastAPI()
    
    # Override the repository dependency
    from src.api.readings import get_glucose_repository
    app.dependency_overrides[get_glucose_repository] = override_get_glucose_repository
    
    app.include_router(readings_router, prefix="/api/bg")
    return app


@pytest.fixture
def client(app):
    """Create a test client for the app."""
    return TestClient(app)


@pytest.fixture
def sample_glucose_reading():
    """Create a sample glucose reading for testing using our TestGlucoseReading."""
    now = datetime.utcnow()
    
    device_info = {
        "device_id": "G6-1234567",
        "serial_number": "SN-1234567890",
        "manufacturer": "Dexcom",
        "model": "G6"
    }
    
    return TestGlucoseReading(
        user_id="user123",
        timestamp=now,
        glucose_value=120,
        glucose_unit="mg/dL",
        trend_direction=TrendDirection.STEADY,
        device_info=device_info,
        reading_type=ReadingType.CGM,
        source=ReadingSource.DEXCOM,
        created_at=now,
        updated_at=now
    )


@pytest.fixture
def sample_glucose_readings():
    """Create a list of sample glucose readings for testing using our TestGlucoseReading."""
    now = datetime.utcnow()
    
    device_info = {
        "device_id": "G6-1234567",
        "serial_number": "SN-1234567890",
        "manufacturer": "Dexcom",
        "model": "G6"
    }
    
    readings = []
    for i in range(5):
        timestamp = now - timedelta(minutes=i*5)
        reading = TestGlucoseReading(
            user_id="user123",
            timestamp=timestamp,
            glucose_value=120 - i*2,  # Decreasing values
            glucose_unit="mg/dL",
            trend_direction=TrendDirection.FALLING if i > 0 else TrendDirection.STEADY,
            device_info=device_info,
            reading_type=ReadingType.CGM,
            source=ReadingSource.DEXCOM,
            created_at=timestamp,
            updated_at=timestamp
        )
        readings.append(reading)
    
    return readings


class TestGetLatestReading:
    """Tests for the get_latest_reading endpoint."""
    
    def test_get_latest_reading_success(self, client, mock_repo, sample_glucose_reading):
        """Test getting the latest reading successfully."""
        # Setup mock repository with sample data
        mock_repo.data = {"user123": [sample_glucose_reading]}
        
        # Make the request
        response = client.get("/api/bg/user123/latest")
        
        # Verify the response
        assert response.status_code == HTTP_200_OK
        assert response.json()["status"] == "success"
        assert "data" in response.json()
        assert response.json()["data"]["user_id"] == "user123"
        assert response.json()["data"]["glucose_value"] == 120
        
        # Verify cache headers
        assert "ETag" in response.headers
        assert "Cache-Control" in response.headers
        assert "private, max-age=" in response.headers["Cache-Control"]
    
    def test_get_latest_reading_not_found(self, client, mock_repo):
        """Test getting the latest reading when none exists."""
        # Setup mock repository with no data
        mock_repo.data = {}
        
        # Make the request
        response = client.get("/api/bg/user123/latest")
        
        # Verify the response
        assert response.status_code == HTTP_404_NOT_FOUND
        assert "No readings found" in response.json()["detail"]
    
    def test_get_latest_reading_not_modified(self, client, mock_repo, sample_glucose_reading):
        """Test getting the latest reading with If-None-Match header matching the ETag."""
        # Setup mock repository with sample data
        mock_repo.data = {"user123": [sample_glucose_reading]}
        
        # Make initial request to get the ETag
        initial_response = client.get("/api/bg/user123/latest")
        etag = initial_response.headers["ETag"]
        
        # Make the request with If-None-Match header
        response = client.get("/api/bg/user123/latest", headers={"If-None-Match": etag})
        
        # Verify the response is 304 Not Modified
        assert response.status_code == HTTP_304_NOT_MODIFIED


class TestGetReadings:
    """Tests for the get_readings endpoint."""
    
    def test_get_readings_success(self, client, mock_repo, sample_glucose_readings):
        """Test getting readings successfully."""
        # Setup mock repository with sample data
        mock_repo.data = {"user123": sample_glucose_readings}
        
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
    
    def test_get_readings_with_date_filters(self, client, mock_repo, sample_glucose_readings):
        """Test getting readings with date filters."""
        # Setup mock repository with sample data
        mock_repo.data = {"user123": sample_glucose_readings}
        
        # Make the request with date filters
        start_date = (datetime.utcnow() - timedelta(days=1)).isoformat()
        end_date = datetime.utcnow().isoformat()
        response = client.get(f"/api/bg/user123?start_date={start_date}&end_date={end_date}")
        
        # Verify the response
        assert response.status_code == HTTP_200_OK
        assert response.json()["status"] == "success"
    
    def test_get_readings_with_invalid_date(self, client):
        """Test getting readings with invalid date format."""
        # Make the request with invalid date format
        response = client.get("/api/bg/user123?start_date=invalid-date")
        
        # Verify the response
        assert response.status_code == HTTP_400_BAD_REQUEST
        assert "Invalid date format" in response.json()["detail"]
    
    def test_get_readings_with_format_simple(self, client, mock_repo, sample_glucose_readings):
        """Test getting readings with simple format."""
        # Setup mock repository with sample data
        mock_repo.data = {"user123": sample_glucose_readings}
        
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
    
    def test_get_readings_with_format_csv(self, client, mock_repo, sample_glucose_readings):
        """Test getting readings with CSV format."""
        # Setup mock repository with sample data
        mock_repo.data = {"user123": sample_glucose_readings}
        
        # Make the request with CSV format
        response = client.get("/api/bg/user123?format=csv")
        
        # Verify the response
        assert response.status_code == HTTP_200_OK
        assert response.json()["status"] == "success"
        assert "data" in response.json()
        
        # Verify the CSV format
        data = response.json()["data"]
        assert len(data) == 6  # Header + 5 rows
        assert "timestamp,glucose_value,glucose_unit,trend_direction" in data[0]
        
        # Check a few values from the CSV
        for i in range(1, 6):
            row = data[i].split(",")
            assert len(row) == 4
            assert "mg/dL" in row[2]  # All should have this unit
    
    def test_get_readings_with_sort_asc(self, client, mock_repo, sample_glucose_readings):
        """Test getting readings with ascending sort order."""
        # Setup mock repository with sample data
        mock_repo.data = {"user123": sample_glucose_readings}
        
        # Make the request with ascending sort
        response = client.get("/api/bg/user123?sort=asc")
        
        # Verify the response
        assert response.status_code == HTTP_200_OK
        assert response.json()["status"] == "success"
        assert response.json()["pagination"]["sort"] == "asc"
        
        # Verify the order (oldest first = lowest indexes first in our mock implementation)
        data = response.json()["data"]
        for i in range(len(data) - 1):
            # In our sample data, older readings have lower glucose values
            assert data[i]["glucose_value"] <= data[i + 1]["glucose_value"]
    
    def test_get_readings_with_limit(self, client, mock_repo, sample_glucose_readings):
        """Test getting readings with a specific limit."""
        # Setup mock repository with sample data
        mock_repo.data = {"user123": sample_glucose_readings}
        
        # Make the request with a limit
        response = client.get("/api/bg/user123?limit=3")
        
        # Verify the response
        assert response.status_code == HTTP_200_OK
        assert response.json()["status"] == "success"
        assert len(response.json()["data"]) == 3 
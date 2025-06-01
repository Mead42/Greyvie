import pytest
from fastapi.testclient import TestClient
from src.main import create_app

app = create_app()
client = TestClient(app)

VALID_READING = {
    "user_id": "testuser",
    "timestamp": "2024-06-01T12:00:00Z",
    "glucose_value": 120,
    "trend_direction": "rising",
    "device_info": {"id": "dev1", "serial": "s1", "model": "M", "manufacturer": "Dexcom"}
}

INVALID_READING = {
    "user_id": "testuser",
    "timestamp": "2024-06-01T12:00:00Z",
    "glucose_value": 700  # out of range
}

def test_ingest_valid():
    resp = client.post("/api/bg/ingest", json=VALID_READING)
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "success"
    assert data["data"]["user_id"] == "testuser"

def test_ingest_invalid():
    resp = client.post("/api/bg/ingest", json=INVALID_READING)
    assert resp.status_code == 400
    data = resp.json()
    assert "glucose_value" in data["detail"]

def test_ingest_batch_mixed():
    batch = [VALID_READING, INVALID_READING]
    resp = client.post("/api/bg/ingest/batch", json=batch)
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "partial"
    assert data["processed"] == 1
    assert data["failed"] == 1
    assert any("glucose_value" in err["field"] for err in data["errors"]) 
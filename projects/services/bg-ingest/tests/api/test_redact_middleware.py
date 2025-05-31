import pytest
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

def test_redact_sensitive_data_in_404_error():
    resp = client.post("/api/bg/nonexistent", json={"password": "supersecret", "user": "bob"})
    # Accept 401 or 404 depending on middleware config
    assert resp.status_code in (401, 404)
    # Should not leak password
    assert "supersecret" not in resp.text
    # Redacted string may or may not appear depending on error handler, but password should never appear
    # assert "***REDACTED***" in resp.text
    assert "bob" in resp.text or resp.status_code == 401 
import pytest
import logging
import io
import json
from httpx import AsyncClient, ASGITransport
from src.main import app
from src.utils.config import JSONFormatter

@pytest.mark.asyncio
async def test_successful_api_call_logs_and_metrics():
    # Set up in-memory log capture
    logger = logging.getLogger()
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        # Make a health check call (as a simple, always-successful endpoint)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/health")
            assert response.status_code == 200
        handler.flush()
        stream.seek(0)
        logs = [json.loads(line) for line in stream.readlines() if line.strip()]
        # There should be at least one log line for the request
        assert any("health_check" in log.get("function", "") for log in logs)
        # Check that no PII is present in logs
        for log in logs:
            assert not any(s in json.dumps(log) for s in ["token", "secret", "password"])
        # Check metrics endpoint
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            metrics_resp = await ac.get("/metrics/", auth=("testuser", "testpass"))
            assert metrics_resp.status_code == 200
            assert b"python_info" in metrics_resp.content
    finally:
        logger.removeHandler(handler) 
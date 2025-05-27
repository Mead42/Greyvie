import pytest
from httpx import AsyncClient, ASGITransport
from src.main import app
from src.utils.config import get_settings

@pytest.mark.asyncio
async def test_metrics_requires_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/metrics/")
        assert response.status_code == 401
        assert "WWW-Authenticate" in response.headers

@pytest.mark.asyncio
async def test_metrics_with_auth(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "metrics_user", "testuser")
    monkeypatch.setattr(settings, "metrics_pass", "testpass")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/metrics/", auth=("testuser", "testpass"))
        assert response.status_code == 200
        # Check for standard Python metrics that should always be present
        assert b'python_gc_objects_collected_total' in response.content
        assert b'python_info' in response.content
        # TODO: Add custom metrics like dexcom_api_call_total when implemented 
import pytest
import jwt
from datetime import datetime, timedelta
from httpx import AsyncClient, ASGITransport
from unittest.mock import MagicMock
from src.main import app
from src.utils.config import get_settings
from src.api.readings import get_glucose_repository

settings = get_settings()
SECRET = settings.jwt_secret_key
ISSUER = settings.jwt_issuer
AUDIENCE = settings.jwt_audience

USER_ID = "testuser"

# Helper to create JWTs
def make_jwt(sub=USER_ID, exp=None, secret=SECRET, issuer=ISSUER, audience=AUDIENCE, **kwargs):
    payload = {
        "sub": sub,
        "iss": issuer,
        "aud": audience,
        "exp": exp or (datetime.utcnow() + timedelta(minutes=5)),
        **kwargs
    }
    return jwt.encode(payload, secret, algorithm="HS256")

@pytest.fixture(autouse=True)
def override_glucose_repo():
    mock_instance = MagicMock()
    mock_instance.get_latest_reading_for_user.return_value = None
    app.dependency_overrides[get_glucose_repository] = lambda: mock_instance
    yield
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_protected_endpoint_with_valid_jwt():
    token = make_jwt()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get(f"/api/bg/{USER_ID}/latest", headers={"Authorization": f"Bearer {token}"})
        # 404 is expected if user/data doesn't exist, but not 401
        assert resp.status_code != 401

@pytest.mark.asyncio
async def test_protected_endpoint_with_expired_jwt():
    exp = datetime.utcnow() - timedelta(minutes=1)
    token = make_jwt(exp=exp)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get(f"/api/bg/{USER_ID}/latest", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401
        assert "expired" in resp.text.lower()

@pytest.mark.asyncio
async def test_protected_endpoint_with_invalid_signature():
    token = make_jwt(secret="wrongsecret")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get(f"/api/bg/{USER_ID}/latest", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401
        assert "invalid token" in resp.text.lower()

@pytest.mark.asyncio
async def test_protected_endpoint_with_missing_token():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get(f"/api/bg/{USER_ID}/latest")
        assert resp.status_code == 401
        assert "authorization" in resp.text.lower() 
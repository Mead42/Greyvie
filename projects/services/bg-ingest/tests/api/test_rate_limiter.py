import pytest
import jwt
from datetime import datetime, timedelta
from httpx import AsyncClient, ASGITransport
from unittest.mock import MagicMock
from fastapi import FastAPI
from fastapi import APIRouter
from src.api.middleware import RateLimiter
from src.utils.config import get_settings
from src.main import JWTAuthMiddleware
import time

settings = get_settings()
SECRET = settings.jwt_secret_key
ISSUER = settings.jwt_issuer
AUDIENCE = settings.jwt_audience

# Helper to create JWTs
def make_jwt(sub, exp=None, secret=SECRET, issuer=ISSUER, audience=AUDIENCE, **kwargs):
    payload = {
        "sub": sub,
        "iss": issuer,
        "aud": audience,
        "exp": exp or (datetime.utcnow() + timedelta(minutes=5)),
        **kwargs
    }
    return jwt.encode(payload, secret, algorithm="HS256")

endpoint_limits = {
    "/api/test/always_ok": {"rate_limit_per_minute": 3, "rate_limit_burst": 2},
}

def create_test_app():
    app = FastAPI()
    # Dummy router for always-ok endpoint
    router = APIRouter()
    @router.get("/always_ok")
    async def always_ok():
        return {"ok": True}
    app.include_router(router, prefix="/api/test")
    # Add middlewares in correct order (reverse execution order)
    # RateLimiter first (executes second)
    app.add_middleware(
        RateLimiter,
        default_rate_limit_per_minute=5,
        default_rate_limit_burst=2,
        endpoint_limits=endpoint_limits,
        include_paths=["/api/"],
        exclude_paths=["/health", "/metrics"]
    )
    # JWT middleware second (executes first)
    app.add_middleware(JWTAuthMiddleware)
    return app

@pytest.mark.asyncio
async def test_user_based_rate_limiting():
    user_id = "user1"
    token = make_jwt(sub=user_id)
    app = create_test_app()
    
    # Get the RateLimiter instance to inspect buckets
    rate_limiter = None
    for middleware in app.user_middleware:
        if middleware.cls == RateLimiter:
            # Note: We can't access the instance directly in test, but we can verify the headers
            break
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        for i in range(2):
            resp = await ac.get("/api/test/always_ok", headers={"Authorization": f"Bearer {token}"})
            assert resp.status_code == 200
        resp = await ac.get("/api/test/always_ok", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 429
        assert "rate limit" in resp.text.lower()

@pytest.mark.asyncio
async def test_separate_limits_for_different_users():
    token1 = make_jwt(sub="userA")
    token2 = make_jwt(sub="userB")
    app = create_test_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Exhaust userA
        for i in range(2):
            resp = await ac.get("/api/test/always_ok", headers={"Authorization": f"Bearer {token1}"})
            assert resp.status_code == 200
        resp = await ac.get("/api/test/always_ok", headers={"Authorization": f"Bearer {token1}"})
        assert resp.status_code == 429
        # userB should still be allowed
        resp = await ac.get("/api/test/always_ok", headers={"Authorization": f"Bearer {token2}"})
        assert resp.status_code == 200

@pytest.mark.asyncio
async def test_per_endpoint_limits():
    # /api/test/always_ok should allow 2, then 429
    token = make_jwt(sub="loginuser")
    app = create_test_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        for i in range(2):
            resp = await ac.get("/api/test/always_ok", headers={"Authorization": f"Bearer {token}"})
            assert resp.status_code == 200
        resp = await ac.get("/api/test/always_ok", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 429

@pytest.mark.asyncio
async def test_rate_limit_reset(monkeypatch):
    # Simulate time passing to reset the bucket
    user_id = "resetuser"
    token = make_jwt(sub=user_id)
    app = create_test_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Hit the limit
        for i in range(2):
            resp = await ac.get("/api/test/always_ok", headers={"Authorization": f"Bearer {token}"})
            assert resp.status_code == 200
        resp = await ac.get("/api/test/always_ok", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 429
        # Patch time to simulate 1 minute passing
        orig_time = time.time
        now = orig_time()
        monkeypatch.setattr("time.time", lambda: now + 61)
        # Should be allowed again
        resp = await ac.get("/api/test/always_ok", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        monkeypatch.setattr("time.time", orig_time) 
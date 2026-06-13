"""Broker endpoint tests (auth gating + login-url construction)."""

import time

import jwt
import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app

client = TestClient(app)


def test_broker_status_requires_auth():
    assert client.get("/broker/status").status_code == 401


def test_login_url_requires_auth():
    assert client.get("/broker/upstox/login-url").status_code == 401


def test_connect_requires_auth():
    assert client.post("/auth/broker/connect", json={"code": "x"}).status_code == 401


def test_bad_bearer_token_rejected(auth_header):
    # auth_header fixture configures the secret; a malformed token must 401.
    r = client.get("/broker/status", headers={"Authorization": "Bearer not-a-jwt"})
    assert r.status_code == 401


@pytest.fixture
def auth_header(monkeypatch):
    secret = "test-jwt-secret-0123456789abcdef0123456789"
    monkeypatch.setenv("SUPABASE_JWT_SECRET", secret)
    get_settings.cache_clear()
    token = jwt.encode(
        {"sub": "user-xyz", "aud": "authenticated", "exp": int(time.time()) + 3600},
        secret,
        algorithm="HS256",
    )
    yield {"Authorization": f"Bearer {token}"}
    get_settings.cache_clear()


def test_login_url_authorized(auth_header):
    r = client.get("/broker/upstox/login-url", headers=auth_header)
    assert r.status_code == 200
    url = r.json()["url"]
    assert "login/authorization/dialog" in url
    assert "response_type=code" in url
    assert "state=user-xyz" in url  # state carries the user id

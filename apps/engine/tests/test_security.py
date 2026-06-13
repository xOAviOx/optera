"""Tests for token encryption and Supabase JWT verification."""

import time

import jwt
import pytest
from cryptography.fernet import Fernet

from app.config import get_settings


@pytest.fixture
def fernet_key(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", key)
    get_settings.cache_clear()
    from app.security import crypto

    crypto._fernet.cache_clear()
    yield key
    crypto._fernet.cache_clear()
    get_settings.cache_clear()


def test_token_encryption_round_trip(fernet_key):
    from app.security.crypto import decrypt_token, encrypt_token

    secret = "upstox-access-token-abc123"
    enc = encrypt_token(secret)
    assert enc != secret  # actually encrypted
    assert decrypt_token(enc) == secret


def test_encryption_not_configured(monkeypatch):
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", "")
    get_settings.cache_clear()
    from app.security import crypto
    from app.security.crypto import EncryptionNotConfigured

    crypto._fernet.cache_clear()
    with pytest.raises(EncryptionNotConfigured):
        crypto.encrypt_token("x")
    crypto._fernet.cache_clear()
    get_settings.cache_clear()


@pytest.fixture
def jwt_secret(monkeypatch):
    secret = "test-jwt-secret-0123456789abcdef0123456789"
    monkeypatch.setenv("SUPABASE_JWT_SECRET", secret)
    get_settings.cache_clear()
    yield secret
    get_settings.cache_clear()


def _mint(secret, sub="user-123", **claims):
    payload = {"sub": sub, "aud": "authenticated", "exp": int(time.time()) + 3600, **claims}
    return jwt.encode(payload, secret, algorithm="HS256")


def test_verify_jwt_valid(jwt_secret):
    from app.security.auth import verify_jwt

    assert verify_jwt(_mint(jwt_secret)) == "user-123"


def test_verify_jwt_bad_signature(jwt_secret):
    from app.security.auth import verify_jwt

    forged = _mint("wrong-secret")
    with pytest.raises(ValueError):
        verify_jwt(forged)


def test_verify_jwt_expired(jwt_secret):
    from app.security.auth import verify_jwt

    expired = _mint(jwt_secret, exp=int(time.time()) - 10)
    with pytest.raises(ValueError):
        verify_jwt(expired)

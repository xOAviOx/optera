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


def test_verify_jwt_es256_via_jwks(monkeypatch):
    """Modern Supabase projects sign with ES256 (asymmetric, JWKS). The verifier
    must branch on the token `alg` and validate against the JWKS public key."""
    from cryptography.hazmat.primitives.asymmetric import ec

    from app.security import auth

    priv = ec.generate_private_key(ec.SECP256R1())

    class _FakeSigningKey:
        key = priv.public_key()

    class _FakeJwksClient:
        def get_signing_key_from_jwt(self, _token):
            return _FakeSigningKey()

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    get_settings.cache_clear()
    # Stub out the network fetch — we only want to prove the ES256 decode path.
    monkeypatch.setattr(auth, "_jwks_client", lambda _url: _FakeJwksClient())

    token = jwt.encode(
        {"sub": "user-es256", "aud": "authenticated", "exp": int(time.time()) + 3600},
        priv,
        algorithm="ES256",
    )
    assert auth.verify_jwt(token) == "user-es256"
    get_settings.cache_clear()

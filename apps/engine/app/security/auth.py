"""Supabase JWT verification.

Supabase signs end-user access tokens and sets aud="authenticated". Two signing
schemes exist across projects, and we support both transparently by branching on
the token header's `alg`:

  * asymmetric (ES256/RS256/EdDSA) via JWKS — the modern default. We fetch the
    project's public keys from `/auth/v1/.well-known/jwks.json` (public endpoint)
    and verify against the key matching the token's `kid`.
  * symmetric (HS256) with the project's shared JWT secret — legacy projects.

Either way we return the user id (`sub`).
"""

from __future__ import annotations

from functools import lru_cache

import jwt
from fastapi import Header, HTTPException, status

from app.config import get_settings

# Asymmetric algorithms Supabase may use (verified via JWKS, not the shared secret).
_ASYMMETRIC_ALGS = ("ES256", "RS256", "EdDSA")


@lru_cache(maxsize=4)
def _jwks_client(jwks_url: str) -> jwt.PyJWKClient:
    """Cached JWKS client — keeps its fetched key set warm across requests."""
    return jwt.PyJWKClient(jwks_url)


def _jwks_url() -> str:
    base = get_settings().supabase_url.rstrip("/")
    if not base:
        raise RuntimeError("SUPABASE_URL is not configured (needed for JWKS verification)")
    return f"{base}/auth/v1/.well-known/jwks.json"


def verify_jwt(token: str) -> str:
    """Return the Supabase user id for a valid access token, else raise ValueError."""
    # verify_iat is disabled to tolerate minor clock skew between Supabase's issuer
    # clock and this host (a few seconds of "not yet valid (iat)" otherwise 401s real
    # users). `iat` is informational per RFC 7519; `exp` still strictly bounds lifetime.
    common = {
        "audience": "authenticated",
        "options": {"require": ["sub", "exp"], "verify_iat": False},
    }
    try:
        alg = jwt.get_unverified_header(token).get("alg", "")
        if alg in _ASYMMETRIC_ALGS:
            signing_key = _jwks_client(_jwks_url()).get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token, signing_key.key, algorithms=list(_ASYMMETRIC_ALGS), **common
            )
        else:
            secret = get_settings().supabase_jwt_secret
            if not secret:
                raise RuntimeError("SUPABASE_JWT_SECRET is not configured")
            payload = jwt.decode(token, secret, algorithms=["HS256"], **common)
    except jwt.PyJWTError as exc:  # invalid signature / expired / wrong aud / malformed
        raise ValueError(str(exc)) from exc
    return payload["sub"]


async def get_current_user(authorization: str | None = Header(default=None)) -> str:
    """FastAPI dependency: extract + verify the Bearer token, return user id."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token"
        )
    token = authorization.split(" ", 1)[1].strip()
    try:
        return verify_jwt(token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {exc}"
        ) from exc

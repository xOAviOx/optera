"""Supabase JWT verification.

Supabase signs end-user access tokens with the project's JWT secret (HS256) and
sets aud="authenticated". We verify the signature and return the user id (`sub`).

NOTE: projects using asymmetric signing keys (ES256/RS256 via JWKS) should swap
_decode for a JWKS-based verifier; the dependency surface below stays the same.
"""

from __future__ import annotations

import jwt
from fastapi import Header, HTTPException, status

from app.config import get_settings


def verify_jwt(token: str) -> str:
    """Return the Supabase user id for a valid access token, else raise ValueError."""
    secret = get_settings().supabase_jwt_secret
    if not secret:
        raise RuntimeError("SUPABASE_JWT_SECRET is not configured")
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience="authenticated",
            options={"require": ["sub", "exp"]},
        )
    except jwt.PyJWTError as exc:  # invalid signature / expired / wrong aud
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

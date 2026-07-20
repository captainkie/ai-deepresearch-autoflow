"""JWT access tokens (HS256) + opaque refresh-token helpers.

Access tokens are short-lived JWTs carrying ``sub`` (user id) and ``role``.
Refresh tokens are long, random, opaque strings — never JWTs — stored only as a
SHA-256 hash so a DB leak can't be replayed, and rotated on every use.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt as pyjwt

ALGORITHM = "HS256"
ACCESS_TTL_SECONDS = 15 * 60  # 15 minutes


class TokenError(Exception):
    """Raised when an access token is missing/expired/tampered/invalid."""


def make_access_token(
    *,
    secret: str,
    sub: str,
    role: str,
    expires_in: int = ACCESS_TTL_SECONDS,
    now: datetime | None = None,
) -> str:
    issued = now or datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": sub,
        "role": role,
        "iat": int(issued.timestamp()),
        "exp": int((issued + timedelta(seconds=expires_in)).timestamp()),
    }
    return pyjwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_access_token(token: str, secret: str) -> dict[str, Any]:
    try:
        return pyjwt.decode(token, secret, algorithms=[ALGORITHM])
    except pyjwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc


def generate_refresh_token() -> str:
    """A long, URL-safe, opaque refresh token (~64 chars)."""
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    """SHA-256 hex of a refresh token — what we store and look up."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

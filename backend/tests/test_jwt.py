"""JWT access tokens + refresh-token helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.security import jwt

# ≥32 bytes — HS256 keys shorter than this trigger pyjwt's InsecureKeyLengthWarning.
SECRET = "test-secret-value-that-is-long-enough-1234567890"


def test_access_token_round_trip():
    token = jwt.make_access_token(secret=SECRET, sub="u1", role="admin")
    claims = jwt.decode_access_token(token, SECRET)
    assert claims["sub"] == "u1"
    assert claims["role"] == "admin"


def test_expired_token_is_rejected():
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    token = jwt.make_access_token(secret=SECRET, sub="u1", role="member", expires_in=1, now=past)
    with pytest.raises(jwt.TokenError):
        jwt.decode_access_token(token, SECRET)


def test_wrong_secret_is_rejected():
    token = jwt.make_access_token(secret=SECRET, sub="u1", role="member")
    with pytest.raises(jwt.TokenError):
        jwt.decode_access_token(token, "a-different-secret-also-long-enough-0987654321")


def test_tampered_token_is_rejected():
    token = jwt.make_access_token(secret=SECRET, sub="u1", role="member")
    tampered = token[:-3] + ("abc" if token[-3:] != "abc" else "xyz")
    with pytest.raises(jwt.TokenError):
        jwt.decode_access_token(tampered, SECRET)


def test_refresh_tokens_are_unique_and_hashed():
    a, b = jwt.generate_refresh_token(), jwt.generate_refresh_token()
    assert a != b and len(a) > 40
    h = jwt.hash_refresh_token(a)
    assert h != a
    assert h == jwt.hash_refresh_token(a)  # deterministic
    assert h != jwt.hash_refresh_token(b)

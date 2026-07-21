"""GoogleOAuthService (PKCE + token/userinfo, Google mocked) + account linking."""

from __future__ import annotations

import httpx
import pytest

from app.db.database import Database
from app.db.repositories import RefreshTokenRepo, UserRepo
from app.services.auth_service import AuthService
from app.services.oauth_service import (
    TOKEN_ENDPOINT,
    USERINFO_ENDPOINT,
    GoogleOAuthService,
    OAuthError,
)

JWT_SECRET = "unit-test-jwt-secret-long-enough-1234567890"


def _service(*, token_status: int = 200, userinfo: dict | None = None) -> GoogleOAuthService:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.startswith(TOKEN_ENDPOINT):
            if token_status != 200:
                return httpx.Response(token_status, json={"error": "invalid_grant"})
            return httpx.Response(200, json={"access_token": "ya29.mock"})
        if url.startswith(USERINFO_ENDPOINT):
            return httpx.Response(200, json=userinfo or {})
        return httpx.Response(404)

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return GoogleOAuthService(
        client_id="cid",
        client_secret="secret",
        redirect_uri="http://localhost:8000/api/v1/auth/google/callback",
        http=http,
    )


def test_start_builds_pkce_auth_url():
    url, state, verifier = _service().start()
    assert "code_challenge_method=S256" in url
    assert "code_challenge=" in url
    assert "client_id=cid" in url
    assert f"state={state}" in url
    assert len(verifier) > 40


async def test_complete_returns_normalized_profile():
    svc = _service(
        userinfo={
            "sub": "g-123",
            "email": "User@Example.com",
            "email_verified": True,
            "name": "User",
        }
    )
    profile = await svc.complete("auth-code", "verifier")
    assert profile == {"sub": "g-123", "email": "user@example.com", "name": "User"}


async def test_complete_rejects_unverified_email():
    svc = _service(userinfo={"sub": "g-1", "email": "u@x.com", "email_verified": False})
    with pytest.raises(OAuthError):
        await svc.complete("code", "verifier")


async def test_complete_rejects_token_failure():
    svc = _service(token_status=400)
    with pytest.raises(OAuthError):
        await svc.complete("bad-code", "verifier")


@pytest.fixture
async def auth_service():
    db = Database(":memory:")
    await db.init()
    try:
        yield AuthService(
            users=UserRepo(db), refresh_tokens=RefreshTokenRepo(db), jwt_secret=JWT_SECRET
        )
    finally:
        await db.close()


async def test_link_or_create_google_user(auth_service):
    # New email → creates a member.
    new = await auth_service.link_or_create_google_user(sub="g1", email="New@X.com", name="New")
    assert new["role"] == "member" and new["email"] == "new@x.com" and new["google_sub"] == "g1"

    # Same sub → same user (idempotent).
    again = await auth_service.link_or_create_google_user(sub="g1", email="x@x.com", name="X")
    assert again["id"] == new["id"]

    # Existing password account with the same email → linked, not duplicated.
    await auth_service.register(email="pw@x.com", name="PW", password="password1", role="admin")
    linked = await auth_service.link_or_create_google_user(sub="g2", email="pw@x.com", name="PW2")
    assert linked["google_sub"] == "g2" and linked["role"] == "admin"  # keeps existing role

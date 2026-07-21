"""AuthService — registration, login, and rotating refresh sessions."""

from __future__ import annotations

import pytest

from app.db.database import Database
from app.db.repositories import RefreshTokenRepo, UserRepo
from app.security import jwt as jwt_helper
from app.services.auth_service import AuthService, EmailExistsError

JWT_SECRET = "unit-test-jwt-secret-long-enough-1234567890"


@pytest.fixture
async def db():
    database = Database(":memory:")
    await database.init()
    try:
        yield database
    finally:
        await database.close()


def make_auth(db: Database) -> AuthService:
    return AuthService(
        users=UserRepo(db), refresh_tokens=RefreshTokenRepo(db), jwt_secret=JWT_SECRET
    )


async def test_register_hides_password_hash_and_blocks_duplicates(db):
    auth = make_auth(db)
    user = await auth.register(
        email="A@Example.com ", name="Ada", password="pw12345", role="member"
    )
    assert user["email"] == "a@example.com"  # normalized
    assert "password_hash" not in user
    with pytest.raises(EmailExistsError):
        await auth.register(email="a@example.com", name="Dup", password="x", role="member")


async def test_authenticate_paths(db):
    auth = make_auth(db)
    await auth.register(email="u@x.com", name="U", password="secretpw", role="member")
    assert await auth.authenticate("u@x.com", "secretpw") is not None
    assert await auth.authenticate("u@x.com", "wrong") is None
    assert await auth.authenticate("nobody@x.com", "secretpw") is None


async def test_issue_and_decode_access(db):
    auth = make_auth(db)
    await auth.register(email="u@x.com", name="U", password="secretpw", role="admin")
    user = await auth.authenticate("u@x.com", "secretpw")
    access, refresh = await auth.issue_tokens(user)
    claims = jwt_helper.decode_access_token(access, JWT_SECRET)
    assert claims["sub"] == user["id"] and claims["role"] == "admin"
    assert len(refresh) > 40


async def test_refresh_rotation_mints_working_token(db):
    auth = make_auth(db)
    await auth.register(email="u@x.com", name="U", password="secretpw", role="member")
    user = await auth.authenticate("u@x.com", "secretpw")
    _, refresh = await auth.issue_tokens(user)

    rotated = await auth.rotate_refresh(refresh)
    assert rotated is not None
    _, new_refresh, _ = rotated
    assert new_refresh != refresh
    # The freshly rotated token works for the next rotation.
    assert await auth.rotate_refresh(new_refresh) is not None


async def test_refresh_reuse_revokes_whole_family(db):
    # Replaying an already-rotated (revoked) token is the signature of a stolen
    # token: it is rejected AND kills every token for that user, so the thief's
    # parallel chain and the victim's current token both die.
    auth = make_auth(db)
    await auth.register(email="u@x.com", name="U", password="secretpw", role="member")
    user = await auth.authenticate("u@x.com", "secretpw")
    _, refresh = await auth.issue_tokens(user)

    rotated = await auth.rotate_refresh(refresh)
    assert rotated is not None
    _, new_refresh, _ = rotated

    assert await auth.rotate_refresh(refresh) is None  # reuse detected
    assert await auth.rotate_refresh(new_refresh) is None  # family revoked


async def test_logout_revokes_refresh(db):
    auth = make_auth(db)
    await auth.register(email="u@x.com", name="U", password="secretpw", role="member")
    user = await auth.authenticate("u@x.com", "secretpw")
    _, refresh = await auth.issue_tokens(user)
    await auth.logout(refresh)
    assert await auth.rotate_refresh(refresh) is None


async def test_disabled_user_is_locked_out(db):
    auth = make_auth(db)
    users = UserRepo(db)
    await auth.register(email="u@x.com", name="U", password="secretpw", role="member")
    user = await auth.authenticate("u@x.com", "secretpw")
    access, refresh = await auth.issue_tokens(user)
    await users.set_disabled(user["id"], True)
    assert await auth.authenticate("u@x.com", "secretpw") is None
    assert await auth.user_from_access(access) is None
    assert await auth.rotate_refresh(refresh) is None


async def test_user_from_access_rejects_bad_token(db):
    auth = make_auth(db)
    assert await auth.user_from_access("garbage.token.here") is None


async def test_count_users(db):
    auth = make_auth(db)
    assert await auth.count_users() == 0
    await auth.register(email="u@x.com", name="U", password="pw", role="superadmin")
    assert await auth.count_users() == 1


async def test_email_unique_constraint(db):
    users = UserRepo(db)
    await users.create(
        id="u1",
        email="e@x.com",
        name="A",
        password_hash="h",
        google_sub=None,
        role="member",
        created_at="2026-07-20T00:00:00+00:00",
    )
    with pytest.raises(Exception):
        await users.create(
            id="u2",
            email="e@x.com",
            name="B",
            password_hash="h",
            google_sub=None,
            role="member",
            created_at="2026-07-20T00:00:01+00:00",
        )

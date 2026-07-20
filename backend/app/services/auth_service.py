"""Authentication: registration, password login, and JWT + refresh sessions.

Access is a short-lived JWT; the refresh token is a long opaque string stored
only as a hash and **rotated on every use** (the old one is revoked, so a stolen
-then-reused refresh token is detectable/dead). ``public()`` never exposes
``password_hash``.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import aiosqlite

from app.db.repositories import RefreshTokenRepo, UserRepo
from app.security import jwt as jwt_helper
from app.security.passwords import hash_password, verify_password


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AuthError(Exception):
    pass


class EmailExistsError(AuthError):
    pass


class AuthService:
    def __init__(
        self,
        *,
        users: UserRepo,
        refresh_tokens: RefreshTokenRepo,
        jwt_secret: str,
        access_ttl: int = jwt_helper.ACCESS_TTL_SECONDS,
        refresh_ttl_days: int = 30,
        now: Callable[[], str] | None = None,
        new_id: Callable[[], str] | None = None,
    ) -> None:
        self._users = users
        self._refresh = refresh_tokens
        self._secret = jwt_secret
        self._access_ttl = access_ttl
        self._refresh_ttl = timedelta(days=refresh_ttl_days)
        self._now = now or _utc_now_iso
        self._new_id = new_id or (lambda: uuid4().hex)

    # --- registration / login ---------------------------------------------- #

    async def register(self, *, email: str, name: str, password: str, role: str) -> dict[str, Any]:
        email = email.strip().lower()
        if await self._users.get_by_email(email) is not None:
            raise EmailExistsError(email)
        user_id = self._new_id()
        await self._users.create(
            id=user_id,
            email=email,
            name=name,
            password_hash=hash_password(password),
            google_sub=None,
            role=role,
            created_at=self._now(),
        )
        row = await self._users.get(user_id)
        assert row is not None
        return self.public(row)

    async def authenticate(self, email: str, password: str) -> aiosqlite.Row | None:
        row = await self._users.get_by_email(email.strip().lower())
        if row is None or row["disabled"] or not row["password_hash"]:
            return None
        if not verify_password(row["password_hash"], password):
            return None
        return row

    # --- sessions ----------------------------------------------------------- #

    async def issue_tokens(
        self, user: aiosqlite.Row, *, user_agent: str | None = None
    ) -> tuple[str, str]:
        access = jwt_helper.make_access_token(
            secret=self._secret, sub=user["id"], role=user["role"], expires_in=self._access_ttl
        )
        refresh_plain = jwt_helper.generate_refresh_token()
        expires = datetime.now(timezone.utc) + self._refresh_ttl
        await self._refresh.create(
            id=self._new_id(),
            user_id=user["id"],
            token_hash=jwt_helper.hash_refresh_token(refresh_plain),
            expires_at=expires.isoformat(),
            user_agent=user_agent,
            created_at=self._now(),
        )
        return access, refresh_plain

    async def rotate_refresh(
        self, refresh_plain: str, *, user_agent: str | None = None
    ) -> tuple[str, str, aiosqlite.Row] | None:
        row = await self._refresh.get_by_hash(jwt_helper.hash_refresh_token(refresh_plain))
        if row is None or row["revoked_at"] is not None:
            return None
        if self._is_expired(row["expires_at"]):
            return None
        user = await self._users.get(row["user_id"])
        if user is None or user["disabled"]:
            return None
        # Rotate: revoke the presented token, then mint a fresh pair.
        await self._refresh.revoke(row["id"], self._now())
        access, new_refresh = await self.issue_tokens(user, user_agent=user_agent)
        return access, new_refresh, user

    async def logout(self, refresh_plain: str) -> None:
        row = await self._refresh.get_by_hash(jwt_helper.hash_refresh_token(refresh_plain))
        if row is not None:
            await self._refresh.revoke(row["id"], self._now())

    async def user_from_access(self, access_token: str) -> aiosqlite.Row | None:
        try:
            claims = jwt_helper.decode_access_token(access_token, self._secret)
        except jwt_helper.TokenError:
            return None
        user = await self._users.get(claims.get("sub", ""))
        if user is None or user["disabled"]:
            return None
        return user

    async def count_users(self) -> int:
        return await self._users.count()

    # --- user management (admin) ------------------------------------------- #

    async def list_users(self) -> list[dict[str, Any]]:
        return [self.public(u) for u in await self._users.list()]

    async def get_user(self, user_id: str) -> aiosqlite.Row | None:
        return await self._users.get(user_id)

    async def set_role(self, user_id: str, role: str) -> None:
        await self._users.set_role(user_id, role)

    async def set_disabled(self, user_id: str, disabled: bool) -> None:
        await self._users.set_disabled(user_id, disabled)

    # --- helpers ------------------------------------------------------------ #

    @staticmethod
    def public(row: aiosqlite.Row) -> dict[str, Any]:
        """User view without secrets — never includes ``password_hash``."""
        return {
            "id": row["id"],
            "email": row["email"],
            "name": row["name"],
            "role": row["role"],
            "disabled": bool(row["disabled"]),
            "created_at": row["created_at"],
        }

    def _is_expired(self, expires_at: str) -> bool:
        try:
            return datetime.fromisoformat(expires_at) <= datetime.now(timezone.utc)
        except ValueError:
            return True

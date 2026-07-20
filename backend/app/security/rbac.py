"""RBAC dependencies for FastAPI routes.

The access token is presented as ``Authorization: Bearer <jwt>``. Roles are
ranked ``viewer < member < admin < superadmin``; ``require_role(min)`` enforces a
minimum. A disabled user is already rejected by ``AuthService.user_from_access``.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

import aiosqlite
from fastapi import Depends, HTTPException, Request, status

from app.api.deps import get_auth_service

if TYPE_CHECKING:
    from app.services.auth_service import AuthService

ROLE_RANK = {"viewer": 0, "member": 1, "admin": 2, "superadmin": 3}


async def get_current_user(
    request: Request, auth: "AuthService" = Depends(get_auth_service)
) -> aiosqlite.Row:
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not authenticated")
    user = await auth.user_from_access(token)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or expired token")
    return user


def require_role(minimum: str) -> Callable[..., Awaitable[aiosqlite.Row]]:
    threshold = ROLE_RANK[minimum]

    async def dependency(user: aiosqlite.Row = Depends(get_current_user)) -> aiosqlite.Row:
        if ROLE_RANK.get(user["role"], -1) < threshold:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "insufficient role")
        return user

    return dependency


require_member = require_role("member")
require_admin = require_role("admin")
require_superadmin = require_role("superadmin")

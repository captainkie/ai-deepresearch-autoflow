"""Admin endpoints: encrypted provider credentials + audit log.

M3a ships these **open** (no auth) so the vault is usable end-to-end; M3b wraps
them with RBAC (``admin`` and above). Every read returns a masked hint plus
metadata only — a credential's plaintext is never returned by any route.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_auth_service, get_vault_service
from app.security.keys import MasterKeyError, decode_master_key
from app.security.rbac import ROLE_RANK, get_current_user, require_admin, require_superadmin
from app.services.auth_service import AuthService

if TYPE_CHECKING:
    from app.services.vault_service import VaultService

# Every admin route requires the `admin` role or above.
router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


class CredentialCreate(BaseModel):
    provider: str = Field(min_length=1)
    label: str = Field(min_length=1)
    secret: str = Field(min_length=1)
    expires_at: str | None = None


class RotateRequest(BaseModel):
    new_master_key: str = Field(min_length=1)  # base64-encoded 32 bytes


@router.get("/credentials")
async def list_credentials(
    provider: str | None = None,
    vault: "VaultService" = Depends(get_vault_service),
) -> dict:
    return {"credentials": await vault.list_credentials(provider)}


@router.post("/credentials", status_code=status.HTTP_201_CREATED)
async def create_credential(
    body: CredentialCreate,
    vault: "VaultService" = Depends(get_vault_service),
) -> dict:
    # actor_id is None until auth lands in M3b.
    return await vault.add_credential(
        provider=body.provider,
        label=body.label,
        plaintext=body.secret,
        actor_id=None,
        expires_at=body.expires_at,
    )


@router.post("/credentials/rotate", dependencies=[Depends(require_superadmin)])
async def rotate_master_key(
    body: RotateRequest,
    vault: "VaultService" = Depends(get_vault_service),
) -> dict:
    try:
        new_key = decode_master_key(body.new_master_key)
    except MasterKeyError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    version = await vault.rotate_master_key(new_key, actor_id=None)
    return {"ok": True, "key_version": version}


@router.post("/credentials/{cred_id}/revoke")
async def revoke_credential(
    cred_id: str,
    vault: "VaultService" = Depends(get_vault_service),
) -> dict:
    if not await vault.revoke(cred_id, actor_id=None):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "credential not found")
    return {"ok": True}


@router.delete("/credentials/{cred_id}")
async def delete_credential(
    cred_id: str,
    vault: "VaultService" = Depends(get_vault_service),
) -> dict:
    # Soft-delete = revoke: secrets are never hard-removed, so the audit trail holds.
    if not await vault.revoke(cred_id, actor_id=None):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "credential not found")
    return {"ok": True}


@router.get("/audit")
async def list_audit(
    limit: int = 200,
    vault: "VaultService" = Depends(get_vault_service),
) -> dict:
    return {"audit": await vault.list_audit(limit)}


class UserUpdate(BaseModel):
    role: str | None = None
    disabled: bool | None = None


@router.get("/users")
async def list_users(auth: AuthService = Depends(get_auth_service)) -> dict:
    return {"users": await auth.list_users()}


@router.patch("/users/{user_id}")
async def update_user(
    user_id: str,
    body: UserUpdate,
    actor: aiosqlite.Row = Depends(get_current_user),
    auth: AuthService = Depends(get_auth_service),
) -> dict:
    target = await auth.get_user(user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")

    is_super = ROLE_RANK.get(actor["role"], -1) >= ROLE_RANK["superadmin"]
    target_is_admin = ROLE_RANK.get(target["role"], -1) >= ROLE_RANK["admin"]

    if body.role is not None:
        if body.role not in ROLE_RANK:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "unknown role")
        # Only a superadmin may grant admin+ or re-role an existing admin+.
        if (ROLE_RANK[body.role] >= ROLE_RANK["admin"] or target_is_admin) and not is_super:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "only a superadmin can manage admins")
        await auth.set_role(user_id, body.role)

    if body.disabled is not None:
        if target_is_admin and not is_super:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "only a superadmin can disable an admin")
        await auth.set_disabled(user_id, body.disabled)

    updated = await auth.get_user(user_id)
    assert updated is not None
    return AuthService.public(updated)

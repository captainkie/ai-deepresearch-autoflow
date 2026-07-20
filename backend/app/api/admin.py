"""Admin endpoints: encrypted provider credentials + audit log.

M3a ships these **open** (no auth) so the vault is usable end-to-end; M3b wraps
them with RBAC (``admin`` and above). Every read returns a masked hint plus
metadata only — a credential's plaintext is never returned by any route.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_vault_service
from app.security.keys import MasterKeyError, decode_master_key

if TYPE_CHECKING:
    from app.services.vault_service import VaultService

router = APIRouter(prefix="/api/admin", tags=["admin"])


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


@router.post("/credentials/rotate")
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

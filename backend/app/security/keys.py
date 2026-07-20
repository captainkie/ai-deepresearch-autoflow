"""Master-key (KEK) resolution for the credential vault.

The vault encrypts provider secrets under a 32-byte key-encryption key supplied
base64-encoded via ``AUTOFLOW_MASTER_KEY``. Production **requires** a real key
(fail-fast); development tolerates a missing one by generating a loud ephemeral
key so the app still boots (encrypted data will not survive a restart).
"""

from __future__ import annotations

import base64
import binascii
import logging
import os
import secrets

logger = logging.getLogger("autoflow.security")

KEY_BYTES = 32  # AES-256
JWT_SECRET_MIN_CHARS = 32


class MasterKeyError(RuntimeError):
    """Raised when a usable master key cannot be resolved."""


def generate_master_key() -> str:
    """Return a fresh base64-encoded 32-byte master key (for docs / setup)."""
    return base64.b64encode(os.urandom(KEY_BYTES)).decode("ascii")


def decode_master_key(raw: str) -> bytes:
    """Decode and validate a base64 master key into exactly ``KEY_BYTES`` bytes."""
    try:
        key = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise MasterKeyError("AUTOFLOW_MASTER_KEY is not valid base64") from exc
    if len(key) != KEY_BYTES:
        raise MasterKeyError(
            f"AUTOFLOW_MASTER_KEY must decode to {KEY_BYTES} bytes, got {len(key)}"
        )
    return key


def resolve_master_key(raw: str | None, app_env: str) -> bytes:
    """Resolve the KEK.

    - a value is present → decode + validate it.
    - missing + ``production`` → raise (fail-fast).
    - missing + non-production → warn loudly and return an ephemeral key.
    """
    if raw:
        return decode_master_key(raw)
    if app_env.lower() == "production":
        raise MasterKeyError("AUTOFLOW_MASTER_KEY is required when APP_ENV=production")
    logger.warning(
        "AUTOFLOW_MASTER_KEY is not set — generating an EPHEMERAL vault key. "
        "Encrypted credentials will NOT survive a restart. "
        "Set AUTOFLOW_MASTER_KEY (see `autoflow gen-key`) for real use."
    )
    return os.urandom(KEY_BYTES)


def resolve_jwt_secret(raw: str | None, app_env: str) -> str:
    """Resolve the JWT signing secret (same prod/dev policy as the master key)."""
    if raw:
        if len(raw) < JWT_SECRET_MIN_CHARS:
            raise MasterKeyError(
                f"AUTOFLOW_JWT_SECRET must be at least {JWT_SECRET_MIN_CHARS} characters"
            )
        return raw
    if app_env.lower() == "production":
        raise MasterKeyError("AUTOFLOW_JWT_SECRET is required when APP_ENV=production")
    logger.warning(
        "AUTOFLOW_JWT_SECRET is not set — generating an EPHEMERAL signing secret. "
        "All sessions are invalidated on restart. Set AUTOFLOW_JWT_SECRET for real use."
    )
    return secrets.token_urlsafe(48)

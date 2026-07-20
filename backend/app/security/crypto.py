"""AES-256-GCM authenticated encryption for short provider secrets.

``Vault`` wraps a single key-encryption key. Each ``encrypt`` uses a fresh random
96-bit nonce; the returned ciphertext carries the GCM authentication tag, so any
tampering with ciphertext or nonce fails ``decrypt`` with ``InvalidTag``. The key
material and plaintext are never exposed via ``repr`` or logging.
"""

from __future__ import annotations

import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

NONCE_BYTES = 12  # 96-bit nonce (recommended for AES-GCM)


class Vault:
    """Authenticated encryption of short secrets under a fixed 32-byte KEK."""

    __slots__ = ("_aesgcm",)

    def __init__(self, key: bytes) -> None:
        if len(key) != 32:
            raise ValueError("Vault key must be 32 bytes (AES-256)")
        self._aesgcm = AESGCM(key)

    def encrypt(self, plaintext: str) -> tuple[bytes, bytes]:
        """Encrypt ``plaintext`` → ``(ciphertext_with_tag, nonce)`` (fresh nonce)."""
        nonce = os.urandom(NONCE_BYTES)
        ciphertext = self._aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        return ciphertext, nonce

    def decrypt(self, ciphertext: bytes, nonce: bytes) -> str:
        """Decrypt; raises ``cryptography.exceptions.InvalidTag`` on any tamper."""
        return self._aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")

    def __repr__(self) -> str:  # never leak key material
        return "Vault(key=***)"


def masked_hint(secret: str) -> str:
    """A safe, non-reversible display hint of a secret (e.g. ``sk-p…wxyz``)."""
    s = secret.strip()
    if len(s) <= 8:
        return "•" * len(s)
    return f"{s[:4]}…{s[-4:]}"

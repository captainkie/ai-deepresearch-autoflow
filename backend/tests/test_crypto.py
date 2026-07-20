"""Vault crypto + master-key resolution — the security centerpiece of M3a.

These exercise the exact guarantees the design leans on: authenticated
encryption (tamper → failure), unique nonces, prod fail-fast on a missing key,
and that key material / plaintext never leaks through ``repr``.
"""

from __future__ import annotations

import base64

import pytest
from cryptography.exceptions import InvalidTag

from app.security import crypto, keys


# --------------------------------------------------------------------------- #
# master-key resolution
# --------------------------------------------------------------------------- #
def test_generate_master_key_is_32_bytes_base64() -> None:
    assert len(base64.b64decode(keys.generate_master_key())) == 32


def test_decode_master_key_validates_length() -> None:
    with pytest.raises(keys.MasterKeyError):
        keys.decode_master_key(base64.b64encode(b"too-short").decode())


def test_decode_master_key_rejects_non_base64() -> None:
    with pytest.raises(keys.MasterKeyError):
        keys.decode_master_key("!!! not base64 !!!")


def test_resolve_master_key_production_requires_key() -> None:
    with pytest.raises(keys.MasterKeyError):
        keys.resolve_master_key(None, "production")


def test_resolve_master_key_dev_generates_ephemeral() -> None:
    key = keys.resolve_master_key(None, "development")
    assert isinstance(key, bytes) and len(key) == 32


def test_resolve_master_key_uses_provided_value() -> None:
    raw = keys.generate_master_key()
    assert keys.resolve_master_key(raw, "production") == base64.b64decode(raw)


# --------------------------------------------------------------------------- #
# AES-256-GCM vault
# --------------------------------------------------------------------------- #
def _vault() -> crypto.Vault:
    return crypto.Vault(base64.b64decode(keys.generate_master_key()))


def test_vault_round_trip() -> None:
    v = _vault()
    ct, nonce = v.encrypt("sk-secret-123")
    assert v.decrypt(ct, nonce) == "sk-secret-123"


def test_vault_nonce_is_unique_and_96_bit() -> None:
    v = _vault()
    nonces = [v.encrypt("x")[1] for _ in range(50)]
    assert len(set(nonces)) == 50
    assert all(len(n) == 12 for n in nonces)


def test_vault_tampered_ciphertext_raises() -> None:
    v = _vault()
    ct, nonce = v.encrypt("secret")
    tampered = bytes([ct[0] ^ 0x01]) + ct[1:]
    with pytest.raises(InvalidTag):
        v.decrypt(tampered, nonce)


def test_vault_tampered_nonce_raises() -> None:
    v = _vault()
    ct, nonce = v.encrypt("secret")
    bad_nonce = bytes([nonce[0] ^ 0x01]) + nonce[1:]
    with pytest.raises(InvalidTag):
        v.decrypt(ct, bad_nonce)


def test_vault_wrong_key_cannot_decrypt() -> None:
    ct, nonce = _vault().encrypt("secret")
    with pytest.raises(InvalidTag):
        _vault().decrypt(ct, nonce)


def test_vault_requires_32_byte_key() -> None:
    with pytest.raises(ValueError):
        crypto.Vault(b"too short")


def test_vault_repr_hides_key_material() -> None:
    assert "***" in repr(_vault())


def test_masked_hint_hides_the_middle() -> None:
    hint = crypto.masked_hint("sk-proj-ABCDEFGHIJKLMNOP")
    assert "EFGHIJKL" not in hint
    assert hint.endswith("MNOP")
    assert len(hint) < len("sk-proj-ABCDEFGHIJKLMNOP")


def test_masked_hint_short_secret_fully_masked() -> None:
    assert set(crypto.masked_hint("abc")) <= {"•"}

"""Argon2id password hashing."""

from __future__ import annotations

from app.security import passwords


def test_hash_is_not_plaintext_and_verifies():
    h = passwords.hash_password("hunter2")
    assert h != "hunter2"
    assert h.startswith("$argon2id$")
    assert passwords.verify_password(h, "hunter2") is True


def test_verify_rejects_wrong_password():
    h = passwords.hash_password("correct horse")
    assert passwords.verify_password(h, "battery staple") is False


def test_verify_handles_garbage_hash_gracefully():
    assert passwords.verify_password("not-a-hash", "whatever") is False


def test_needs_rehash_returns_bool():
    assert passwords.needs_rehash(passwords.hash_password("x")) is False

"""Password hashing with Argon2id (via ``argon2-cffi``).

``verify_password`` is constant-time on match/mismatch and never raises for a
wrong password — it returns ``False``. ``needs_rehash`` lets callers transparently
upgrade a stored hash when parameters change.
"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()  # Argon2id with library defaults


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)

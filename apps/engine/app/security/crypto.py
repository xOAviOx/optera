"""Symmetric encryption for broker tokens (Fernet / AES-128-CBC + HMAC).

Tokens are encrypted before they touch the database and decrypted only inside the
engine, in memory, at the moment of a broker call. The key comes from
TOKEN_ENCRYPTION_KEY and is never logged or sent to the client.

Generate a key with:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet

from app.config import get_settings


class EncryptionNotConfigured(RuntimeError):
    pass


@lru_cache
def _fernet() -> Fernet:
    key = get_settings().token_encryption_key
    if not key:
        raise EncryptionNotConfigured(
            "TOKEN_ENCRYPTION_KEY is not set — cannot encrypt/decrypt broker tokens."
        )
    return Fernet(key.encode())


def encrypt_token(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode()).decode()

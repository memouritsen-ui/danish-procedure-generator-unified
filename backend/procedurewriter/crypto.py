"""Encryption utilities for secure secret storage.

Uses Fernet symmetric encryption with a key from environment variable.
If no key exists, generates one and prints instructions to set it.
"""
from __future__ import annotations

import base64
import os
import secrets

from cryptography.fernet import Fernet, InvalidToken


def get_or_create_key() -> str:
    """Get encryption key from environment or generate a new one."""
    key = os.environ.get("PROCEDUREWRITER_SECRET_KEY")
    if key:
        return key
    new_key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
    return new_key


def _get_fernet() -> Fernet:
    """Get Fernet instance with current key."""
    key = os.environ.get("PROCEDUREWRITER_SECRET_KEY")
    if not key:
        raise ValueError(
            "PROCEDUREWRITER_SECRET_KEY environment variable not set. "
            "Generate one with: python -c \"import base64, secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())\""
        )
    return Fernet(key.encode())


def encrypt_value(plaintext: str) -> str:
    """Encrypt a string value."""
    fernet = _get_fernet()
    return fernet.encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    """Decrypt an encrypted value."""
    fernet = _get_fernet()
    return fernet.decrypt(ciphertext.encode()).decode()


def is_encrypted(value: str) -> bool:
    """Check if a value appears to be Fernet-encrypted."""
    return value.startswith("gAAAAA") and len(value) > 50

"""Encryption utilities for secure secret storage.

Uses Fernet symmetric encryption with a key from environment variable.
If no key exists, the application must fail fast.
"""
from __future__ import annotations

import os

from cryptography.fernet import Fernet, InvalidToken


def get_or_create_key() -> str:
    """Get encryption key from environment or fail fast if missing."""
    key = os.environ.get("PROCEDUREWRITER_SECRET_KEY")
    if not key:
        raise ValueError(
            "PROCEDUREWRITER_SECRET_KEY environment variable not set. "
            "Set it in your shell profile (e.g., ~/.zshrc) before starting the app."
        )
    return key


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

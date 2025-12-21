"""Tests for encryption utilities."""
from __future__ import annotations

import base64
import os
import secrets

import pytest

from procedurewriter.crypto import (
    decrypt_value,
    encrypt_value,
    get_or_create_key,
    is_encrypted,
)


@pytest.fixture
def encryption_key():
    """Generate a test encryption key."""
    key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
    old_key = os.environ.get("PROCEDUREWRITER_SECRET_KEY")
    os.environ["PROCEDUREWRITER_SECRET_KEY"] = key
    yield key
    if old_key:
        os.environ["PROCEDUREWRITER_SECRET_KEY"] = old_key
    else:
        del os.environ["PROCEDUREWRITER_SECRET_KEY"]


def test_get_or_create_key_returns_existing(encryption_key):
    """Test that get_or_create_key returns existing key from environment."""
    key = get_or_create_key()
    assert key == encryption_key


def test_get_or_create_key_requires_env():
    """Test that get_or_create_key requires an explicit environment key."""
    old_key = os.environ.get("PROCEDUREWRITER_SECRET_KEY")
    if old_key:
        del os.environ["PROCEDUREWRITER_SECRET_KEY"]

    try:
        with pytest.raises(ValueError, match="PROCEDUREWRITER_SECRET_KEY environment variable not set"):
            get_or_create_key()
    finally:
        if old_key:
            os.environ["PROCEDUREWRITER_SECRET_KEY"] = old_key


def test_encrypt_decrypt_roundtrip(encryption_key):
    """Test that encryption and decryption work correctly."""
    plaintext = "my-secret-api-key-12345"

    # Encrypt
    ciphertext = encrypt_value(plaintext)
    assert ciphertext != plaintext
    assert len(ciphertext) > len(plaintext)

    # Decrypt
    decrypted = decrypt_value(ciphertext)
    assert decrypted == plaintext


def test_encrypt_produces_different_ciphertexts(encryption_key):
    """Test that encrypting the same value twice produces different ciphertexts."""
    plaintext = "my-secret-api-key"

    ciphertext1 = encrypt_value(plaintext)
    ciphertext2 = encrypt_value(plaintext)

    # Different ciphertexts (Fernet uses random IV)
    assert ciphertext1 != ciphertext2

    # But both decrypt to same value
    assert decrypt_value(ciphertext1) == plaintext
    assert decrypt_value(ciphertext2) == plaintext


def test_encrypt_requires_key():
    """Test that encryption fails without environment key."""
    old_key = os.environ.get("PROCEDUREWRITER_SECRET_KEY")
    if old_key:
        del os.environ["PROCEDUREWRITER_SECRET_KEY"]

    try:
        with pytest.raises(ValueError, match="PROCEDUREWRITER_SECRET_KEY environment variable not set"):
            encrypt_value("test")
    finally:
        if old_key:
            os.environ["PROCEDUREWRITER_SECRET_KEY"] = old_key


def test_decrypt_requires_key():
    """Test that decryption fails without environment key."""
    old_key = os.environ.get("PROCEDUREWRITER_SECRET_KEY")
    if old_key:
        del os.environ["PROCEDUREWRITER_SECRET_KEY"]

    try:
        with pytest.raises(ValueError, match="PROCEDUREWRITER_SECRET_KEY environment variable not set"):
            decrypt_value("gAAAAABmock_encrypted_value")
    finally:
        if old_key:
            os.environ["PROCEDUREWRITER_SECRET_KEY"] = old_key


def test_is_encrypted_identifies_encrypted_values(encryption_key):
    """Test that is_encrypted correctly identifies encrypted values."""
    plaintext = "my-secret-api-key"
    ciphertext = encrypt_value(plaintext)

    assert is_encrypted(ciphertext) is True
    assert is_encrypted(plaintext) is False
    assert is_encrypted("") is False
    assert is_encrypted("short") is False


def test_decrypt_with_wrong_key_fails(encryption_key):
    """Test that decryption fails with wrong key."""
    plaintext = "my-secret-api-key"
    ciphertext = encrypt_value(plaintext)

    # Change the key
    os.environ["PROCEDUREWRITER_SECRET_KEY"] = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()

    from cryptography.fernet import InvalidToken
    with pytest.raises(InvalidToken):
        decrypt_value(ciphertext)

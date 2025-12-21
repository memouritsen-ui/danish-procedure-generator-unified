"""Tests for encrypted secret storage in db.py."""

import os
import pytest
from pathlib import Path
from procedurewriter.db import init_db, set_secret, get_secret, delete_secret
from procedurewriter.crypto import is_encrypted


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Create a temporary database for testing."""
    db = tmp_path / "test.db"
    init_db(db)
    return db


@pytest.fixture(autouse=True)
def set_secret_key(monkeypatch):
    """Set encryption key for all tests."""
    # Must be a valid base64-encoded 32-byte key (generated with Fernet.generate_key())
    monkeypatch.setenv("PROCEDUREWRITER_SECRET_KEY", "_GzFguJBCK1SAZdNSkfyofpS-5TL5aN0F0fWTdF2u-s=")


def test_set_secret_encrypts_value(db_path: Path) -> None:
    """set_secret should store an encrypted value in the database."""
    import sqlite3
    set_secret(db_path, name="test_key", value="my-secret-api-key")

    # Read raw value from database
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT value FROM secrets WHERE name = ?", ("test_key",)).fetchone()
    conn.close()

    raw_value = row["value"]
    # Should be encrypted (not the plaintext)
    assert raw_value != "my-secret-api-key"
    assert is_encrypted(raw_value)


def test_get_secret_decrypts_value(db_path: Path) -> None:
    """get_secret should return decrypted plaintext."""
    set_secret(db_path, name="api_key", value="sk-1234567890")
    result = get_secret(db_path, name="api_key")
    assert result == "sk-1234567890"


def test_get_secret_returns_none_for_missing(db_path: Path) -> None:
    """get_secret should return None for non-existent keys."""
    result = get_secret(db_path, name="nonexistent")
    assert result is None


def test_delete_secret_removes_value(db_path: Path) -> None:
    """delete_secret should remove the encrypted value."""
    set_secret(db_path, name="to_delete", value="temp-value")
    delete_secret(db_path, name="to_delete")
    result = get_secret(db_path, name="to_delete")
    assert result is None


def test_roundtrip_multiple_secrets(db_path: Path) -> None:
    """Multiple secrets should be independently encrypted and retrievable."""
    set_secret(db_path, name="key1", value="value1")
    set_secret(db_path, name="key2", value="value2")
    set_secret(db_path, name="key3", value="value3")

    assert get_secret(db_path, name="key1") == "value1"
    assert get_secret(db_path, name="key2") == "value2"
    assert get_secret(db_path, name="key3") == "value3"


def test_update_secret_reencrypts(db_path: Path) -> None:
    """Updating a secret should work correctly."""
    set_secret(db_path, name="mutable", value="original")
    assert get_secret(db_path, name="mutable") == "original"

    set_secret(db_path, name="mutable", value="updated")
    assert get_secret(db_path, name="mutable") == "updated"

"""Tests for keys router."""

import tempfile
import pytest
from fastapi.testclient import TestClient
from pathlib import Path
from unittest.mock import patch

from procedurewriter.main import app
from procedurewriter import db
from procedurewriter.settings import Settings


@pytest.fixture
def client(monkeypatch):
    """Create test client with temporary database."""
    # Set encryption key FIRST before anything else
    monkeypatch.setenv("PROCEDUREWRITER_SECRET_KEY", "_GzFguJBCK1SAZdNSkfyofpS-5TL5aN0F0fWTdF2u-s=")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        # Create the index directory for the DB
        (data_dir / "index").mkdir(parents=True, exist_ok=True)
        db_path = data_dir / "index" / "runs.sqlite3"
        db.init_db(db_path)
        
        # Create a new Settings instance with test data_dir
        test_settings = Settings(data_dir=data_dir)
        
        # Patch the global settings in both main and router
        with patch("procedurewriter.main.settings", test_settings), \
             patch("procedurewriter.routers.keys.settings", test_settings):
            with TestClient(app) as client:
                yield client


def test_get_openai_key_not_set(client):
    """GET /api/keys/openai returns not set when no key configured."""
    response = client.get("/api/keys/openai")
    assert response.status_code == 200
    data = response.json()
    assert data["present"] is False
    assert data["masked"] is None


def test_set_and_get_openai_key(client):
    """PUT then GET /api/keys/openai should work."""
    # Set the key
    response = client.put("/api/keys/openai", json={"api_key": "sk-test-1234567890"})
    assert response.status_code == 200
    
    # Get should show masked key
    response = client.get("/api/keys/openai")
    assert response.status_code == 200
    data = response.json()
    assert data["present"] is True
    assert data["masked"] is not None
    assert "sk-" in data["masked"]  # Partial masked key


def test_delete_openai_key(client):
    """DELETE /api/keys/openai should remove the key."""
    # Set, then delete
    client.put("/api/keys/openai", json={"api_key": "sk-test-key"})
    response = client.delete("/api/keys/openai")
    assert response.status_code == 200
    
    # Verify deleted
    response = client.get("/api/keys/openai")
    data = response.json()
    assert data["present"] is False


def test_openai_status_not_set(client):
    """GET /api/keys/openai/status should show not set."""
    response = client.get("/api/keys/openai/status")
    assert response.status_code == 200
    data = response.json()
    assert data["present"] is False
    assert data["ok"] is False


def test_ncbi_key_get_not_set(client):
    """GET /api/keys/ncbi returns not set when no key configured."""
    response = client.get("/api/keys/ncbi")
    assert response.status_code == 200
    data = response.json()
    assert data["present"] is False
    assert data["masked"] is None


def test_set_and_get_ncbi_key(client):
    """PUT then GET /api/keys/ncbi should work."""
    # Set the key
    response = client.put("/api/keys/ncbi", json={"api_key": "test-ncbi-key-123"})
    assert response.status_code == 200
    
    # Get should show masked key
    response = client.get("/api/keys/ncbi")
    assert response.status_code == 200
    data = response.json()
    assert data["present"] is True
    assert data["masked"] is not None


def test_delete_ncbi_key(client):
    """DELETE /api/keys/ncbi should remove the key."""
    # Set, then delete
    client.put("/api/keys/ncbi", json={"api_key": "test-key"})
    response = client.delete("/api/keys/ncbi")
    assert response.status_code == 200
    
    # Verify deleted
    response = client.get("/api/keys/ncbi")
    data = response.json()
    assert data["present"] is False


def test_anthropic_key_get_not_set(client):
    """GET /api/keys/anthropic returns not set when no key configured."""
    response = client.get("/api/keys/anthropic")
    assert response.status_code == 200
    data = response.json()
    assert data["present"] is False
    assert data["masked"] is None


def test_set_and_get_anthropic_key(client):
    """PUT then GET /api/keys/anthropic should work."""
    # Set the key
    response = client.put("/api/keys/anthropic", json={"api_key": "sk-ant-test-1234567890"})
    assert response.status_code == 200
    
    # Get should show masked key
    response = client.get("/api/keys/anthropic")
    assert response.status_code == 200
    data = response.json()
    assert data["present"] is True
    assert data["masked"] is not None


def test_delete_anthropic_key(client):
    """DELETE /api/keys/anthropic should remove the key."""
    # Set, then delete
    client.put("/api/keys/anthropic", json={"api_key": "sk-ant-test-key"})
    response = client.delete("/api/keys/anthropic")
    assert response.status_code == 200
    
    # Verify deleted
    response = client.get("/api/keys/anthropic")
    data = response.json()
    assert data["present"] is False


def test_anthropic_status_not_set(client):
    """GET /api/keys/anthropic/status should show not set."""
    response = client.get("/api/keys/anthropic/status")
    assert response.status_code == 200
    data = response.json()
    assert data["present"] is False
    assert data["ok"] is False

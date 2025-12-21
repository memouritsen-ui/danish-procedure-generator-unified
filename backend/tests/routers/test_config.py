"""Tests for config router."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from procedurewriter import db
from procedurewriter.main import app
from procedurewriter.settings import Settings


@pytest.fixture
def client(monkeypatch):
    """Create test client with temporary config files."""
    # Set encryption key FIRST
    monkeypatch.setenv("PROCEDUREWRITER_SECRET_KEY", "_GzFguJBCK1SAZdNSkfyofpS-5TL5aN0F0fWTdF2u-s=")

    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        # Create necessary directories
        (data_dir / "index").mkdir(parents=True, exist_ok=True)
        (data_dir / "config").mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        db_path = data_dir / "index" / "runs.sqlite3"
        db.init_db(db_path)

        # Create mock config files with valid YAML
        (data_dir / "config" / "author_guide.yaml").write_text("test: author_guide", encoding="utf-8")
        (data_dir / "config" / "source_allowlist.yaml").write_text("test: allowlist", encoding="utf-8")
        (data_dir / "config" / "docx_template.yaml").write_text("test: template", encoding="utf-8")

        # Create a new Settings instance with test data_dir
        test_settings = Settings(data_dir=data_dir)

        # Patch the global settings in both main and router
        with patch("procedurewriter.main.settings", test_settings), \
             patch("procedurewriter.routers.config.settings", test_settings):
            with TestClient(app) as client:
                yield client


def test_get_author_guide(client):
    """GET /api/config/author_guide returns content."""
    response = client.get("/api/config/author_guide")
    assert response.status_code == 200
    data = response.json()
    assert "text" in data
    assert len(data["text"]) > 0  # Has some content


def test_set_author_guide(client):
    """PUT /api/config/author_guide updates content."""
    new_content = "updated: author_guide_content"
    response = client.put("/api/config/author_guide", json={"text": new_content})
    assert response.status_code == 200

    # Verify it was updated
    response = client.get("/api/config/author_guide")
    assert response.json()["text"] == new_content


def test_get_source_allowlist(client):
    """GET /api/config/source_allowlist returns content."""
    response = client.get("/api/config/source_allowlist")
    assert response.status_code == 200
    data = response.json()
    assert "text" in data
    assert len(data["text"]) > 0  # Has some content


def test_set_source_allowlist(client):
    """PUT /api/config/source_allowlist updates content."""
    new_content = "updated: allowlist_content"
    response = client.put("/api/config/source_allowlist", json={"text": new_content})
    assert response.status_code == 200

    # Verify it was updated
    response = client.get("/api/config/source_allowlist")
    assert response.json()["text"] == new_content


def test_get_docx_template(client):
    """GET /api/config/docx_template returns content."""
    response = client.get("/api/config/docx_template")
    assert response.status_code == 200
    data = response.json()
    assert "text" in data
    assert len(data["text"]) > 0  # Has some content


def test_set_docx_template(client):
    """PUT /api/config/docx_template updates content."""
    new_content = "updated: template_content"
    response = client.put("/api/config/docx_template", json={"text": new_content})
    assert response.status_code == 200

    # Verify it was updated
    response = client.get("/api/config/docx_template")
    assert response.json()["text"] == new_content

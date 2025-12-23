"""Tests for style profile API endpoints."""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from procedurewriter.main import app
from procedurewriter.db import init_db
from procedurewriter.settings import Settings


@pytest.fixture
def test_client():
    from procedurewriter.settings import settings
    original_data_dir = settings.data_dir

    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        # Create the index directory for the DB
        (data_dir / "index").mkdir(parents=True, exist_ok=True)
        db_path = data_dir / "index" / "runs.sqlite3"
        init_db(db_path)

        # Directly modify the singleton's data_dir
        settings.data_dir = data_dir

        try:
            with TestClient(app) as client:
                yield client
        finally:
            # Restore original data_dir
            settings.data_dir = original_data_dir


def test_list_styles_empty(test_client) -> None:
    """List styles when none exist."""
    response = test_client.get("/api/styles")
    assert response.status_code == 200
    assert response.json() == []


def test_create_style(test_client) -> None:
    """Create a new style profile."""
    response = test_client.post(
        "/api/styles",
        json={
            "name": "Test Style",
            "tone_description": "Formal",
            "target_audience": "Doctors",
            "detail_level": "comprehensive",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Style"
    assert "id" in data


def test_get_style(test_client) -> None:
    """Get a specific style profile."""
    # Create first
    create_response = test_client.post(
        "/api/styles",
        json={"name": "Get Test", "tone_description": "Test"},
    )
    style_id = create_response.json()["id"]

    # Get it
    response = test_client.get(f"/api/styles/{style_id}")
    assert response.status_code == 200
    assert response.json()["name"] == "Get Test"


def test_set_default_style(test_client) -> None:
    """Set a style as default."""
    # Create a style
    create_response = test_client.post(
        "/api/styles",
        json={"name": "Default Test", "tone_description": "Test"},
    )
    style_id = create_response.json()["id"]

    # Set as default
    response = test_client.post(f"/api/styles/{style_id}/set-default")
    assert response.status_code == 200

    # Verify it's default
    get_response = test_client.get(f"/api/styles/{style_id}")
    assert get_response.json()["is_default"] is True


def test_delete_style(test_client) -> None:
    """Delete a style profile."""
    # Create first
    create_response = test_client.post(
        "/api/styles",
        json={"name": "Delete Test", "tone_description": "Test"},
    )
    style_id = create_response.json()["id"]

    # Delete it - returns 204 No Content (R5-007)
    response = test_client.delete(f"/api/styles/{style_id}")
    assert response.status_code == 204

    # Verify it's gone
    get_response = test_client.get(f"/api/styles/{style_id}")
    assert get_response.status_code == 404

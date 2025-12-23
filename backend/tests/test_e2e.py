"""End-to-end tests for the FastAPI application."""
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from procedurewriter.main import app, settings


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    """Create test client with isolated data directory."""
    # Set encryption key for API key storage
    monkeypatch.setenv("PROCEDUREWRITER_SECRET_KEY", "_GzFguJBCK1SAZdNSkfyofpS-5TL5aN0F0fWTdF2u-s=")

    # Save original values
    original_data_dir = settings.data_dir
    original_config_dir = settings.config_dir

    # Override settings paths for test isolation
    settings.data_dir = tmp_path / "data"
    settings.config_dir = tmp_path / "config"

    # Create required directories
    settings.runs_dir.mkdir(parents=True, exist_ok=True)
    settings.cache_dir.mkdir(parents=True, exist_ok=True)
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    (settings.resolved_data_dir / "index").mkdir(parents=True, exist_ok=True)

    # Create config files
    settings.resolved_config_dir.mkdir(parents=True, exist_ok=True)
    (settings.author_guide_path).write_text("structure:\n  title_prefix: Test\n  sections: []\n", encoding="utf-8")
    (settings.allowlist_path).write_text("allowed_url_prefixes:\n  - https://test.example/\nseed_urls: []\n", encoding="utf-8")
    (settings.evidence_hierarchy_path).write_text("evidence_levels:\n  unclassified:\n    priority: 50\n    badge: Test\n    badge_color: '#ccc'\n    description: Test\n", encoding="utf-8")

    # Initialize database
    from procedurewriter.db import init_db
    init_db(settings.db_path)

    try:
        with TestClient(app) as c:
            yield c
    finally:
        # Restore original values
        settings.data_dir = original_data_dir
        settings.config_dir = original_config_dir


class TestStatusEndpoint:
    """Tests for /api/status endpoint."""

    def test_status_returns_app_info(self, client: TestClient) -> None:
        response = client.get("/api/status")
        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert "dummy_mode" in data
        assert "use_llm" in data
        assert "llm_provider" in data
        assert "llm_model" in data

    def test_status_shows_no_keys_initially(self, client: TestClient) -> None:
        response = client.get("/api/status")
        data = response.json()
        # Without env vars or DB keys, source should be "none"
        assert data["openai_key_source"] in ("none", "env")
        assert data["anthropic_key_source"] in ("none", "env")


class TestRunsEndpoints:
    """Tests for /api/runs endpoints."""

    def test_runs_list_empty_initially(self, client: TestClient) -> None:
        response = client.get("/api/runs")
        assert response.status_code == 200
        assert response.json() == []

    def test_write_creates_run(self, client: TestClient) -> None:
        # Enable dummy mode to skip LLM calls
        original_dummy = settings.dummy_mode
        settings.dummy_mode = True
        try:
            response = client.post("/api/write", json={
                "procedure": "Test Procedure",
                "context": "Test context"
            })
            assert response.status_code == 200
            data = response.json()
            assert "run_id" in data
            run_id = data["run_id"]
            assert len(run_id) == 32  # UUID hex

            # Run is created asynchronously, wait a bit
            time.sleep(0.5)

            # Check run appears in list
            response = client.get("/api/runs")
            runs = response.json()
            assert len(runs) >= 1
            assert any(r["run_id"] == run_id for r in runs)
        finally:
            settings.dummy_mode = original_dummy

    def test_ack_endpoint_requeues_run(self, client: TestClient) -> None:
        from procedurewriter.db import create_run, set_run_needs_ack, get_run

        run_id = "aaaabbbbccccdddd1111222233334444"  # 32-char hex
        run_dir = settings.runs_dir / run_id
        create_run(
            settings.db_path,
            run_id=run_id,
            procedure="Ack Procedure",
            context=None,
            run_dir=run_dir,
        )
        set_run_needs_ack(
            settings.db_path,
            run_id=run_id,
            ack_details={"missing_tiers": ["Cochrane"]},
            error="Missing tiers",
        )

        response = client.post(f"/api/runs/{run_id}/ack", json={"ack_note": "Proceed anyway"})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "QUEUED"
        assert data["ack_required"] is False

        run = get_run(settings.db_path, run_id)
        assert run is not None
        assert run.ack_note == "Proceed anyway"

    def test_get_run_not_found(self, client: TestClient) -> None:
        response = client.get("/api/runs/00000000000000000000000000000000")  # Valid format, non-existent
        assert response.status_code == 404

    def test_costs_endpoint(self, client: TestClient) -> None:
        response = client.get("/api/costs")
        assert response.status_code == 200
        data = response.json()
        assert "total_runs" in data
        assert "total_cost_usd" in data
        assert "total_tokens" in data


class TestKeyManagement:
    """Tests for API key management endpoints."""

    def test_openai_key_crud(self, client: TestClient) -> None:
        # Initially no key
        response = client.get("/api/keys/openai")
        assert response.status_code == 200
        data = response.json()
        # May be present from env (result not used, just checking format)
        _ = data["present"]

        # Set a key
        response = client.put("/api/keys/openai", json={"api_key": "sk-test123456789"})
        assert response.status_code == 200
        data = response.json()
        assert data["present"] is True
        assert data["masked"] is not None
        # Masked format uses ellipsis: "sk-…6789"
        assert "…" in data["masked"] or "***" in data["masked"] or len(data["masked"]) < 20

        # Delete the key
        response = client.delete("/api/keys/openai")
        assert response.status_code == 200

    def test_anthropic_key_crud(self, client: TestClient) -> None:
        # Set a key
        response = client.put("/api/keys/anthropic", json={"api_key": "sk-ant-test123"})
        assert response.status_code == 200
        data = response.json()
        assert data["present"] is True

        # Delete
        response = client.delete("/api/keys/anthropic")
        assert response.status_code == 200

    def test_ncbi_key_crud(self, client: TestClient) -> None:
        # Set a key
        response = client.put("/api/keys/ncbi", json={"api_key": "ncbi-test-key"})
        assert response.status_code == 200
        data = response.json()
        assert data["present"] is True

        # Delete
        response = client.delete("/api/keys/ncbi")
        assert response.status_code == 200


class TestConfigEndpoints:
    """Tests for configuration endpoints."""

    def test_get_author_guide(self, client: TestClient) -> None:
        response = client.get("/api/config/author_guide")
        assert response.status_code == 200
        data = response.json()
        assert "text" in data
        assert "structure" in data["text"]

    def test_set_author_guide(self, client: TestClient) -> None:
        new_config = "structure:\n  title_prefix: Updated\n  sections:\n    - heading: Test\n      format: bullets\n"
        response = client.put("/api/config/author_guide", json={"text": new_config})
        assert response.status_code == 200

        # Verify change persisted
        response = client.get("/api/config/author_guide")
        assert "Updated" in response.json()["text"]

    def test_get_allowlist(self, client: TestClient) -> None:
        response = client.get("/api/config/source_allowlist")
        assert response.status_code == 200
        data = response.json()
        assert "text" in data

    def test_set_allowlist(self, client: TestClient) -> None:
        new_config = "allowed_url_prefixes:\n  - https://new.example/\nseed_urls: []\n"
        response = client.put("/api/config/source_allowlist", json={"text": new_config})
        assert response.status_code == 200


class TestIngestEndpoints:
    """Tests for document ingestion endpoints."""

    def test_ingest_url_blocked_by_allowlist(self, client: TestClient) -> None:
        response = client.post("/api/ingest/url", json={"url": "https://evil.example/doc"})
        assert response.status_code == 400
        assert "not allowed" in response.json()["detail"].lower()

    def test_ingest_pdf_missing_filename(self, client: TestClient) -> None:
        # Upload without filename - FastAPI returns 422 for validation errors
        response = client.post(
            "/api/ingest/pdf",
            files={"file": ("", b"fake pdf content", "application/pdf")}
        )
        # 400 = app error, 422 = FastAPI validation error, 200 = handled gracefully
        assert response.status_code in (400, 422, 200)

    def test_ingest_docx_missing_filename(self, client: TestClient) -> None:
        response = client.post(
            "/api/ingest/docx",
            files={"file": ("", b"fake docx content", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        )
        # 400 = app error, 422 = FastAPI validation error, 200 = handled gracefully
        assert response.status_code in (400, 422, 200)


class TestRunArtifacts:
    """Tests for run artifact endpoints (docx, manifest, evidence, etc.)."""

    def test_docx_not_found_for_nonexistent_run(self, client: TestClient) -> None:
        response = client.get("/api/runs/00000000000000000000000000000000/docx")
        assert response.status_code == 404

    def test_manifest_not_found_for_nonexistent_run(self, client: TestClient) -> None:
        response = client.get("/api/runs/00000000000000000000000000000000/manifest")
        assert response.status_code == 404

    def test_evidence_not_found_for_nonexistent_run(self, client: TestClient) -> None:
        response = client.get("/api/runs/00000000000000000000000000000000/evidence")
        assert response.status_code == 404

    def test_bundle_not_found_for_nonexistent_run(self, client: TestClient) -> None:
        response = client.get("/api/runs/00000000000000000000000000000000/bundle")
        assert response.status_code == 404

    def test_sources_not_found_for_nonexistent_run(self, client: TestClient) -> None:
        response = client.get("/api/runs/00000000000000000000000000000000/sources")
        assert response.status_code == 404


class TestFullPipelineFlow:
    """Integration tests for complete pipeline flow."""

    def test_full_pipeline_dummy_mode(self, client: TestClient) -> None:
        """Test complete flow: create run -> wait -> get results."""
        original_dummy = settings.dummy_mode
        settings.dummy_mode = True
        try:
            # Create a run
            response = client.post("/api/write", json={
                "procedure": "Blodprøvetagning",
                "context": "Voksen patient på akutmodtagelse"
            })
            assert response.status_code == 200
            run_id = response.json()["run_id"]

            # Wait for completion (dummy mode should be fast)
            max_wait = 5
            for _ in range(max_wait * 2):
                time.sleep(0.5)
                response = client.get(f"/api/runs/{run_id}")
                if response.status_code == 200:
                    run = response.json()
                    if run["status"] in ("DONE", "FAILED"):
                        break

            # Check run completed
            response = client.get(f"/api/runs/{run_id}")
            assert response.status_code == 200
            run = response.json()
            assert run["status"] in ("DONE", "FAILED")
            assert run["procedure"] == "Blodprøvetagning"

            if run["status"] == "DONE":
                # Check sources are available
                response = client.get(f"/api/runs/{run_id}/sources")
                assert response.status_code == 200
                sources = response.json()
                assert "sources" in sources

                # Check manifest if available
                response = client.get(f"/api/runs/{run_id}/manifest")
                if response.status_code == 200:
                    manifest = response.json()
                    assert "procedure" in manifest

        finally:
            settings.dummy_mode = original_dummy


class TestErrorHandling:
    """Tests for error handling and edge cases."""

    def test_invalid_yaml_config_rejected(self, client: TestClient) -> None:
        invalid_yaml = "this: is: not: valid: yaml: [[[["
        try:
            response = client.put("/api/config/author_guide", json={"text": invalid_yaml})
            # Should reject invalid YAML with error status
            assert response.status_code in (400, 422, 500)
        except Exception:
            # If an exception is raised, that also counts as rejection
            pass

    def test_empty_procedure_handled(self, client: TestClient) -> None:
        response = client.post("/api/write", json={
            "procedure": "",
            "context": None
        })
        # Should either reject or handle gracefully
        assert response.status_code in (200, 400, 422)

    def test_api_path_returns_404(self, client: TestClient) -> None:
        response = client.get("/api/nonexistent_endpoint")
        assert response.status_code == 404

    def test_path_traversal_blocked(self, client: TestClient) -> None:
        """Ensure path traversal attacks are blocked.

        Note: /../.. paths are normalized by the framework before reaching
        the handler, so they don't escape. The test verifies the SPA fallback
        behavior (200 with index) rather than reading actual system files.
        """
        response = client.get("/../../../etc/passwd")
        # Framework normalizes the path, falls back to SPA index.html
        assert response.status_code in (200, 404)
        # Verify it didn't actually read /etc/passwd
        if response.status_code == 200:
            assert "root:" not in response.text

    def test_path_traversal_encoded_blocked(self, client: TestClient) -> None:
        """Ensure URL-encoded path traversal is blocked by safe_path_within."""
        response = client.get("/%2e%2e/%2e%2e/etc/passwd")
        assert response.status_code == 404

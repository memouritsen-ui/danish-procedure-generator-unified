"""Tests for meta-analysis FastAPI endpoints.

Following TDD: Tests written before implementation.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


class TestMetaAnalysisEndpointExists:
    """Tests verifying meta-analysis API endpoints exist."""

    def test_meta_analysis_router_importable(self) -> None:
        """Meta-analysis router should be importable."""
        from procedurewriter.api.meta_analysis import router

        assert router is not None

    def test_router_has_post_endpoint(self) -> None:
        """Router should have POST /api/meta-analysis endpoint."""
        from procedurewriter.api.meta_analysis import router

        routes = [r.path for r in router.routes]
        assert "/meta-analysis" in routes or any("/meta-analysis" in r for r in routes)

    def test_router_has_stream_endpoint(self) -> None:
        """Router should have GET /api/meta-analysis/{run_id}/stream SSE endpoint."""
        from procedurewriter.api.meta_analysis import router

        routes = [r.path for r in router.routes]
        assert any("stream" in str(r) for r in routes)


class TestPostMetaAnalysisEndpoint:
    """Tests for POST /api/meta-analysis endpoint."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client."""
        from procedurewriter.main import app

        return TestClient(app)

    def test_post_meta_analysis_returns_202(self, client: TestClient) -> None:
        """POST /api/meta-analysis should return 202 Accepted."""
        with patch("procedurewriter.api.meta_analysis.start_meta_analysis") as mock_start:
            mock_start.return_value = "test-run-id-123"

            response = client.post(
                "/api/meta-analysis",
                json={
                    "query": {
                        "population": "Adults with hypertension",
                        "intervention": "ACE inhibitors",
                        "comparison": "Placebo",
                        "outcome": "Blood pressure reduction",
                    },
                    "study_sources": [
                        {
                            "study_id": "Study1",
                            "title": "ACE Trial",
                            "abstract": "A randomized trial...",
                        }
                    ],
                    "outcome_of_interest": "Blood pressure reduction",
                },
            )

        assert response.status_code == 202

    def test_post_meta_analysis_returns_run_id(self, client: TestClient) -> None:
        """POST should return run_id for tracking."""
        with patch("procedurewriter.api.meta_analysis._run_meta_analysis_async") as mock_run:
            # Mock the async execution to prevent actual pipeline run
            mock_run.return_value = None

            response = client.post(
                "/api/meta-analysis",
                json={
                    "query": {
                        "population": "Adults",
                        "intervention": "Drug A",
                        "comparison": "Placebo",
                        "outcome": "Mortality",
                    },
                    "study_sources": [],
                    "outcome_of_interest": "Mortality",
                },
            )

        data = response.json()
        assert "run_id" in data
        assert data["run_id"].startswith("ma-")  # Our generated format

    def test_post_validates_pico_query(self, client: TestClient) -> None:
        """POST should validate PICO query is complete."""
        response = client.post(
            "/api/meta-analysis",
            json={
                "query": {
                    "population": "",  # Invalid: empty
                    "intervention": "Drug A",
                },
                "study_sources": [],
                "outcome_of_interest": "Mortality",
            },
        )

        assert response.status_code == 422  # Validation error


class TestSSEStreamEndpoint:
    """Tests for GET /api/meta-analysis/{run_id}/stream SSE endpoint."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client."""
        from procedurewriter.main import app

        return TestClient(app)

    def test_stream_endpoint_exists(self, client: TestClient) -> None:
        """SSE stream endpoint should exist."""
        response = client.get("/api/meta-analysis/test-run-id/stream")
        # Should not be 404
        assert response.status_code != 404

    def test_stream_returns_event_stream(self, client: TestClient) -> None:
        """SSE endpoint should return text/event-stream content type."""
        with patch("procedurewriter.api.meta_analysis.get_meta_analysis_events") as mock_events:
            # Mock generator that yields one event
            async def mock_gen():
                yield {"event": "PICO_EXTRACTED", "data": {"study_id": "S1"}}

            mock_events.return_value = mock_gen()

            response = client.get("/api/meta-analysis/test-run-id/stream")

        assert "text/event-stream" in response.headers.get("content-type", "")


class TestMetaAnalysisInputValidation:
    """Tests for request body validation."""

    def test_meta_analysis_request_model(self) -> None:
        """MetaAnalysisRequest model should exist and validate."""
        from procedurewriter.api.meta_analysis import MetaAnalysisRequest

        request = MetaAnalysisRequest(
            query={
                "population": "Adults",
                "intervention": "Drug",
                "comparison": "Placebo",
                "outcome": "Outcome",
            },
            study_sources=[],
            outcome_of_interest="Outcome",
        )

        assert request.query["population"] == "Adults"

    def test_study_source_validation(self) -> None:
        """StudySource should require study_id, title, abstract."""
        from procedurewriter.api.meta_analysis import StudySourceRequest

        source = StudySourceRequest(
            study_id="S1",
            title="Test Study",
            abstract="Study abstract...",
        )

        assert source.study_id == "S1"


class TestMetaAnalysisResultPersistence:
    """Tests for SQLite persistence of meta-analysis results."""

    def test_meta_analysis_runs_table_exists(self, tmp_path) -> None:
        """meta_analysis_runs table should be created by init_db."""
        from procedurewriter.db import init_db

        db_path = tmp_path / "test.db"
        init_db(db_path)

        import sqlite3

        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='meta_analysis_runs'"
        )
        tables = cursor.fetchall()
        conn.close()

        assert len(tables) == 1

    def test_create_meta_analysis_run(self, tmp_path) -> None:
        """Should be able to create meta-analysis run record."""
        from procedurewriter.db import init_db, create_meta_analysis_run, get_meta_analysis_run

        db_path = tmp_path / "test.db"
        init_db(db_path)

        create_meta_analysis_run(
            db_path,
            run_id="ma-run-123",
            pico_query={
                "population": "Adults",
                "intervention": "Drug",
                "comparison": "Placebo",
                "outcome": "Mortality",
            },
            outcome_of_interest="Mortality",
            study_count=5,
        )

        run = get_meta_analysis_run(db_path, "ma-run-123")
        assert run is not None
        assert run.run_id == "ma-run-123"
        assert run.study_count == 5

    def test_update_meta_analysis_results(self, tmp_path) -> None:
        """Should be able to update run with synthesis results."""
        from procedurewriter.db import (
            init_db,
            create_meta_analysis_run,
            update_meta_analysis_results,
            get_meta_analysis_run,
        )

        db_path = tmp_path / "test.db"
        init_db(db_path)

        create_meta_analysis_run(
            db_path,
            run_id="ma-run-456",
            pico_query={"population": "Adults"},
            outcome_of_interest="Outcome",
            study_count=3,
        )

        update_meta_analysis_results(
            db_path,
            run_id="ma-run-456",
            pooled_effect=0.75,
            ci_lower=0.55,
            ci_upper=0.95,
            i_squared=45.2,
            included_studies=2,
            excluded_studies=1,
            status="DONE",
        )

        run = get_meta_analysis_run(db_path, "ma-run-456")
        assert run.pooled_effect == 0.75
        assert run.i_squared == 45.2
        assert run.status == "DONE"

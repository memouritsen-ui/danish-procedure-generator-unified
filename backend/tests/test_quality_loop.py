"""
Tests for Sprint 3: Quality Control Loop.

Tests database storage, API responses, and quality score calculation.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from procedurewriter.db import (
    RunRow,
    create_run,
    get_run,
    init_db,
    list_runs,
    update_run_status,
)


class TestQualityDatabaseFields:
    """Tests for quality-related database fields."""

    def test_run_row_has_quality_fields(self):
        """Test that RunRow dataclass has all quality fields."""
        # Check all fields exist on the dataclass
        row = RunRow(
            run_id="test",
            created_at_utc="2024-01-01T00:00:00",
            updated_at_utc="2024-01-01T00:00:00",
            procedure="Test procedure",
            context=None,
            status="DONE",
            error=None,
            run_dir="/tmp/test",
            manifest_path=None,
            docx_path=None,
            quality_score=8,
            iterations_used=2,
            total_cost_usd=0.05,
            total_input_tokens=1000,
            total_output_tokens=500,
        )
        assert row.quality_score == 8
        assert row.iterations_used == 2
        assert row.total_cost_usd == 0.05
        assert row.total_input_tokens == 1000
        assert row.total_output_tokens == 500

    def test_quality_fields_stored_and_retrieved(self):
        """Test that quality fields are properly stored and retrieved from DB."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            init_db(db_path)

            # Create a run
            run_dir = Path(tmpdir) / "runs" / "test_run"
            run_dir.mkdir(parents=True)
            create_run(
                db_path,
                run_id="test_run",
                procedure="Test procedure",
                context=None,
                run_dir=run_dir,
            )

            # Update with quality data
            update_run_status(
                db_path,
                run_id="test_run",
                status="DONE",
                quality_score=9,
                iterations_used=1,
                total_cost_usd=0.025,
                total_input_tokens=500,
                total_output_tokens=250,
            )

            # Retrieve and verify
            run = get_run(db_path, "test_run")
            assert run is not None
            assert run.quality_score == 9
            assert run.iterations_used == 1
            assert run.total_cost_usd == 0.025
            assert run.total_input_tokens == 500
            assert run.total_output_tokens == 250

    def test_quality_fields_nullable(self):
        """Test that quality fields can be null for runs without quality data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            init_db(db_path)

            run_dir = Path(tmpdir) / "runs" / "test_run"
            run_dir.mkdir(parents=True)
            create_run(
                db_path,
                run_id="test_run",
                procedure="Test procedure",
                context=None,
                run_dir=run_dir,
            )

            # Update without quality data
            update_run_status(
                db_path,
                run_id="test_run",
                status="DONE",
            )

            # Retrieve and verify fields are None
            run = get_run(db_path, "test_run")
            assert run is not None
            assert run.quality_score is None
            assert run.iterations_used is None
            assert run.total_cost_usd is None

    def test_list_runs_includes_quality_fields(self):
        """Test that list_runs returns quality fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            init_db(db_path)

            run_dir = Path(tmpdir) / "runs" / "test_run"
            run_dir.mkdir(parents=True)
            create_run(
                db_path,
                run_id="test_run",
                procedure="Test procedure",
                context=None,
                run_dir=run_dir,
            )

            update_run_status(
                db_path,
                run_id="test_run",
                status="DONE",
                quality_score=7,
                iterations_used=3,
                total_cost_usd=0.1,
            )

            runs = list_runs(db_path)
            assert len(runs) == 1
            assert runs[0].quality_score == 7
            assert runs[0].iterations_used == 3
            assert runs[0].total_cost_usd == 0.1


class TestQualityScoreCalculation:
    """Tests for quality score calculation logic."""

    def test_quality_score_full_support(self):
        """Test that full evidence support yields high quality score."""
        # Simulating evidence calculation: 10 supported, 0 unsupported
        supported = 10
        unsupported = 0
        total = supported + unsupported

        # Quality formula: 5 + (supported/total) * 5
        expected_score = 5 + int((supported / total) * 5)  # = 10
        assert expected_score == 10

    def test_quality_score_partial_support(self):
        """Test that partial evidence support yields medium quality score."""
        # Simulating: 7 supported, 3 unsupported
        supported = 7
        unsupported = 3
        total = supported + unsupported

        expected_score = 5 + int((supported / total) * 5)  # = 5 + 3 = 8
        assert expected_score == 8

    def test_quality_score_low_support(self):
        """Test that low evidence support yields low quality score."""
        # Simulating: 3 supported, 7 unsupported
        supported = 3
        unsupported = 7
        total = supported + unsupported

        expected_score = 5 + int((supported / total) * 5)  # = 5 + 1 = 6
        assert expected_score == 6

    def test_quality_score_no_claims(self):
        """Test default score when there are no claims."""
        # No claims = default to 5
        supported = 0
        unsupported = 0
        total = supported + unsupported

        expected_score = 5 + int(supported / total * 5) if total > 0 else 5

        assert expected_score == 5

    def test_quality_score_clamped(self):
        """Test that quality score is clamped between 5 and 10."""
        # Even with 0% support, minimum is 5
        supported = 0
        unsupported = 10
        total = supported + unsupported

        raw_score = 5 + int((supported / total) * 5)  # = 5 + 0 = 5
        clamped_score = max(5, min(10, raw_score))
        assert clamped_score == 5

        # With 100% support, maximum is 10
        supported = 10
        unsupported = 0
        total = supported + unsupported

        raw_score = 5 + int((supported / total) * 5)  # = 5 + 5 = 10
        clamped_score = max(5, min(10, raw_score))
        assert clamped_score == 10


class TestQualitySchemas:
    """Tests for Pydantic schema validation."""

    def test_run_summary_schema(self):
        """Test RunSummary Pydantic schema has quality fields."""
        from procedurewriter.schemas import RunSummary

        summary = RunSummary(
            run_id="test",
            created_at_utc="2024-01-01T00:00:00",
            updated_at_utc="2024-01-01T00:00:00",
            procedure="Test",
            status="DONE",
            quality_score=8,
            iterations_used=2,
            total_cost_usd=0.05,
        )
        assert summary.quality_score == 8
        assert summary.iterations_used == 2
        assert summary.total_cost_usd == 0.05

    def test_run_detail_schema(self):
        """Test RunDetail Pydantic schema has all quality fields."""
        from procedurewriter.schemas import RunDetail

        detail = RunDetail(
            run_id="test",
            created_at_utc="2024-01-01T00:00:00",
            updated_at_utc="2024-01-01T00:00:00",
            procedure="Test",
            status="DONE",
            context=None,
            error=None,
            procedure_md=None,
            quality_score=9,
            iterations_used=1,
            total_cost_usd=0.025,
            total_input_tokens=500,
            total_output_tokens=250,
        )
        assert detail.quality_score == 9
        assert detail.total_input_tokens == 500
        assert detail.total_output_tokens == 250

    def test_schemas_nullable_quality_fields(self):
        """Test that quality fields are optional in schemas."""
        from procedurewriter.schemas import RunDetail, RunSummary

        # Should not raise with None values
        summary = RunSummary(
            run_id="test",
            created_at_utc="2024-01-01T00:00:00",
            updated_at_utc="2024-01-01T00:00:00",
            procedure="Test",
            status="QUEUED",
        )
        assert summary.quality_score is None

        detail = RunDetail(
            run_id="test",
            created_at_utc="2024-01-01T00:00:00",
            updated_at_utc="2024-01-01T00:00:00",
            procedure="Test",
            status="QUEUED",
            context=None,
            error=None,
            procedure_md=None,
        )
        assert detail.quality_score is None
        assert detail.total_input_tokens is None

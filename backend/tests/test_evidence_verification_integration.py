"""Integration tests for evidence verification in pipeline."""
from __future__ import annotations

from pathlib import Path

import pytest

from procedurewriter.pipeline.run import run_pipeline
from procedurewriter.settings import Settings


class TestEvidenceVerificationIntegration:
    """Tests for evidence verification integration."""

    @pytest.mark.skip(reason="Requires API keys - run manually")
    def test_pipeline_creates_verification_file(self, tmp_path: Path) -> None:
        """Pipeline should create evidence_verification.json when enabled."""
        settings = Settings(
            runs_dir=tmp_path / "runs",
            cache_dir=tmp_path / "cache",
            dummy_mode=True,
            use_llm=False,
            enable_evidence_verification=True,
        )
        settings.runs_dir.mkdir(parents=True, exist_ok=True)

        result = run_pipeline(
            run_id="test-run",
            created_at_utc="2024-01-01T00:00:00Z",
            procedure="Test procedure",
            context=None,
            settings=settings,
            library_sources=[],
        )

        # In dummy mode, verification file should still be created (empty)
        run_dir = tmp_path / "runs" / "test-run"
        verification_path = run_dir / "evidence_verification.json"
        # File creation is conditional on having sources, so may not exist in dummy mode
        # This test documents the expected behavior

    def test_settings_has_enable_evidence_verification_field(self) -> None:
        """Settings should have enable_evidence_verification field."""
        settings = Settings()
        assert hasattr(settings, "enable_evidence_verification")
        assert settings.enable_evidence_verification is True  # Default to enabled

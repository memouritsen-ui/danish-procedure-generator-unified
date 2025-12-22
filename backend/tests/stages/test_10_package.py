"""Tests for Stage 10: PackageRelease.

The PackageRelease stage handles final bundle creation:
1. Receives all artifacts from previous stages
2. Creates a ZIP bundle with all files
3. Generates a manifest with checksums
4. Writes metadata for audit trail
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from procedurewriter.models.gates import Gate, GateStatus, GateType
from procedurewriter.models.issues import Issue, IssueCode, IssueSeverity


def make_issue(
    run_id: str = "test-run",
    code: IssueCode = IssueCode.DOSE_WITHOUT_EVIDENCE,
    severity: IssueSeverity = IssueSeverity.S0,
    message: str = "Test issue",
) -> Issue:
    """Factory function to create test Issue objects."""
    return Issue(
        run_id=run_id,
        code=code,
        severity=severity,
        message=message,
    )


def make_gate(
    run_id: str = "test-run",
    gate_type: GateType = GateType.S0_SAFETY,
    status: GateStatus = GateStatus.PASS,
) -> Gate:
    """Factory function to create test Gate objects."""
    return Gate(
        run_id=run_id,
        gate_type=gate_type,
        status=status,
    )


def create_test_run_files(run_dir: Path) -> None:
    """Create minimal test files in run directory."""
    run_dir.mkdir(parents=True, exist_ok=True)

    # Create a procedure DOCX file (just a placeholder)
    (run_dir / "procedure.docx").write_bytes(b"PK\x03\x04test")

    # Create evidence notes
    (run_dir / "evidence_notes.json").write_text('{"notes": []}')

    # Create claims file
    (run_dir / "claims.json").write_text('{"claims": []}')


class TestPackageReleaseStage:
    """Tests for Stage 10: PackageRelease."""

    def test_package_stage_name_is_package(self) -> None:
        """PackageRelease stage should identify itself as 'package'."""
        from procedurewriter.pipeline.stages.s10_package import PackageReleaseStage

        stage = PackageReleaseStage()
        assert stage.name == "package"

    def test_package_input_requires_run_dir_and_artifacts(self) -> None:
        """PackageRelease input must have run_dir and artifact references."""
        from procedurewriter.pipeline.stages.s10_package import PackageReleaseInput

        gate = make_gate()

        input_data = PackageReleaseInput(
            run_id="test-run",
            run_dir=Path("/tmp/test"),
            procedure_title="Test Procedure",
            issues=[],
            gates=[gate],
            iteration=1,
        )
        assert input_data.run_id == "test-run"
        assert input_data.procedure_title == "Test Procedure"

    def test_package_output_has_all_required_fields(self, tmp_path: Path) -> None:
        """PackageRelease output should contain bundle path and manifest."""
        from procedurewriter.pipeline.stages.s10_package import (
            PackageReleaseInput,
            PackageReleaseStage,
        )

        stage = PackageReleaseStage()
        run_dir = tmp_path / "runs" / "test-run"
        create_test_run_files(run_dir)

        input_data = PackageReleaseInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            issues=[],
            gates=[make_gate(status=GateStatus.PASS)],
            iteration=1,
        )

        result = stage.execute(input_data)

        assert hasattr(result, "run_id")
        assert hasattr(result, "run_dir")
        assert hasattr(result, "procedure_title")
        assert hasattr(result, "bundle_path")
        assert hasattr(result, "manifest")
        assert hasattr(result, "success")
        assert result.run_id == "test-run"

    def test_package_creates_zip_bundle(self, tmp_path: Path) -> None:
        """PackageRelease should create a ZIP file in run directory."""
        from procedurewriter.pipeline.stages.s10_package import (
            PackageReleaseInput,
            PackageReleaseStage,
        )

        stage = PackageReleaseStage()
        run_dir = tmp_path / "runs" / "test-run"
        create_test_run_files(run_dir)

        input_data = PackageReleaseInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test",
            issues=[],
            gates=[make_gate(status=GateStatus.PASS)],
            iteration=1,
        )

        result = stage.execute(input_data)

        assert result.bundle_path is not None
        assert result.bundle_path.exists()
        assert result.bundle_path.suffix == ".zip"

    def test_package_zip_contains_procedure_docx(self, tmp_path: Path) -> None:
        """PackageRelease ZIP should contain the procedure DOCX."""
        from procedurewriter.pipeline.stages.s10_package import (
            PackageReleaseInput,
            PackageReleaseStage,
        )

        stage = PackageReleaseStage()
        run_dir = tmp_path / "runs" / "test-run"
        create_test_run_files(run_dir)

        input_data = PackageReleaseInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test",
            issues=[],
            gates=[make_gate(status=GateStatus.PASS)],
            iteration=1,
        )

        result = stage.execute(input_data)

        with zipfile.ZipFile(result.bundle_path, "r") as zf:
            names = zf.namelist()
            assert any("procedure.docx" in name for name in names)

    def test_package_generates_manifest(self, tmp_path: Path) -> None:
        """PackageRelease should generate a manifest with checksums."""
        from procedurewriter.pipeline.stages.s10_package import (
            PackageReleaseInput,
            PackageReleaseStage,
        )

        stage = PackageReleaseStage()
        run_dir = tmp_path / "runs" / "test-run"
        create_test_run_files(run_dir)

        input_data = PackageReleaseInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test",
            issues=[],
            gates=[make_gate(status=GateStatus.PASS)],
            iteration=1,
        )

        result = stage.execute(input_data)

        assert result.manifest is not None
        assert "files" in result.manifest
        assert len(result.manifest["files"]) > 0

    def test_package_manifest_has_checksums(self, tmp_path: Path) -> None:
        """PackageRelease manifest should have SHA-256 checksums."""
        from procedurewriter.pipeline.stages.s10_package import (
            PackageReleaseInput,
            PackageReleaseStage,
        )

        stage = PackageReleaseStage()
        run_dir = tmp_path / "runs" / "test-run"
        create_test_run_files(run_dir)

        input_data = PackageReleaseInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test",
            issues=[],
            gates=[make_gate(status=GateStatus.PASS)],
            iteration=1,
        )

        result = stage.execute(input_data)

        for file_info in result.manifest["files"]:
            assert "sha256" in file_info
            assert len(file_info["sha256"]) == 64  # SHA-256 hex length

    def test_package_manifest_has_metadata(self, tmp_path: Path) -> None:
        """PackageRelease manifest should include metadata."""
        from procedurewriter.pipeline.stages.s10_package import (
            PackageReleaseInput,
            PackageReleaseStage,
        )

        stage = PackageReleaseStage()
        run_dir = tmp_path / "runs" / "test-run"
        create_test_run_files(run_dir)

        input_data = PackageReleaseInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test Procedure",
            issues=[],
            gates=[make_gate(status=GateStatus.PASS)],
            iteration=1,
        )

        result = stage.execute(input_data)

        assert "run_id" in result.manifest
        assert "procedure_title" in result.manifest
        assert "created_at" in result.manifest
        assert result.manifest["run_id"] == "test-run"
        assert result.manifest["procedure_title"] == "Test Procedure"

    def test_package_emits_progress_event(self, tmp_path: Path) -> None:
        """PackageRelease should emit a progress event when starting."""
        from procedurewriter.pipeline.stages.s10_package import (
            PackageReleaseInput,
            PackageReleaseStage,
        )

        mock_emitter = MagicMock()
        stage = PackageReleaseStage()
        run_dir = tmp_path / "runs" / "test-run"
        create_test_run_files(run_dir)

        input_data = PackageReleaseInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            issues=[],
            gates=[make_gate(status=GateStatus.PASS)],
            iteration=1,
            emitter=mock_emitter,
        )

        stage.execute(input_data)

        mock_emitter.emit.assert_called()

    def test_package_reports_success_on_completion(self, tmp_path: Path) -> None:
        """PackageRelease should report success=True on successful bundle."""
        from procedurewriter.pipeline.stages.s10_package import (
            PackageReleaseInput,
            PackageReleaseStage,
        )

        stage = PackageReleaseStage()
        run_dir = tmp_path / "runs" / "test-run"
        create_test_run_files(run_dir)

        input_data = PackageReleaseInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test",
            issues=[],
            gates=[make_gate(status=GateStatus.PASS)],
            iteration=1,
        )

        result = stage.execute(input_data)

        assert result.success is True

    def test_package_includes_issues_in_output(self, tmp_path: Path) -> None:
        """PackageRelease should include any issues in output for reporting."""
        from procedurewriter.pipeline.stages.s10_package import (
            PackageReleaseInput,
            PackageReleaseStage,
        )

        issue = make_issue()
        stage = PackageReleaseStage()
        run_dir = tmp_path / "runs" / "test-run"
        create_test_run_files(run_dir)

        input_data = PackageReleaseInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test",
            issues=[issue],
            gates=[make_gate(status=GateStatus.PASS)],
            iteration=3,  # Max iterations reached
        )

        result = stage.execute(input_data)

        assert result.issues == [issue]

    def test_package_includes_gates_in_output(self, tmp_path: Path) -> None:
        """PackageRelease should include gates in output for reporting."""
        from procedurewriter.pipeline.stages.s10_package import (
            PackageReleaseInput,
            PackageReleaseStage,
        )

        gate = make_gate(status=GateStatus.PASS)
        stage = PackageReleaseStage()
        run_dir = tmp_path / "runs" / "test-run"
        create_test_run_files(run_dir)

        input_data = PackageReleaseInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test",
            issues=[],
            gates=[gate],
            iteration=1,
        )

        result = stage.execute(input_data)

        assert result.gates == [gate]

    def test_package_zip_is_valid_zipfile(self, tmp_path: Path) -> None:
        """PackageRelease should create a valid ZIP file."""
        from procedurewriter.pipeline.stages.s10_package import (
            PackageReleaseInput,
            PackageReleaseStage,
        )

        stage = PackageReleaseStage()
        run_dir = tmp_path / "runs" / "test-run"
        create_test_run_files(run_dir)

        input_data = PackageReleaseInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test",
            issues=[],
            gates=[make_gate(status=GateStatus.PASS)],
            iteration=1,
        )

        result = stage.execute(input_data)

        assert zipfile.is_zipfile(result.bundle_path)

    def test_package_manifest_included_in_zip(self, tmp_path: Path) -> None:
        """PackageRelease should include manifest.json in the ZIP."""
        from procedurewriter.pipeline.stages.s10_package import (
            PackageReleaseInput,
            PackageReleaseStage,
        )

        stage = PackageReleaseStage()
        run_dir = tmp_path / "runs" / "test-run"
        create_test_run_files(run_dir)

        input_data = PackageReleaseInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test",
            issues=[],
            gates=[make_gate(status=GateStatus.PASS)],
            iteration=1,
        )

        result = stage.execute(input_data)

        with zipfile.ZipFile(result.bundle_path, "r") as zf:
            names = zf.namelist()
            assert any("manifest.json" in name for name in names)

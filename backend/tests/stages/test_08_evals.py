"""Tests for Stage 08: Evals.

The Evals stage runs lints and evaluates gates:
1. Receives bound claims and links from Stage 07 (Bind)
2. Runs lint checks to detect issues (S0/S1/S2)
3. Creates Issue objects for detected problems
4. Evaluates gates (S0_SAFETY, S1_QUALITY, FINAL)
5. Outputs issues and gate statuses for ReviseLoop
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from procedurewriter.models.claims import Claim, ClaimType
from procedurewriter.models.evidence import (
    BindingType,
    ClaimEvidenceLink,
    EvidenceChunk,
)
from procedurewriter.models.gates import Gate, GateStatus, GateType
from procedurewriter.models.issues import Issue, IssueCode, IssueSeverity

if TYPE_CHECKING:
    pass


def make_claim(
    run_id: str = "test-run",
    claim_type: ClaimType = ClaimType.DOSE,
    text: str = "amoxicillin 50 mg/kg/d",
    source_refs: list[str] | None = None,
) -> Claim:
    """Factory function to create test Claim objects."""
    return Claim(
        run_id=run_id,
        claim_type=claim_type,
        text=text,
        source_refs=source_refs or [],
        line_number=1,
        confidence=0.9,
    )


def make_chunk(
    run_id: str = "test-run",
    source_id: str = "SRC001",
    text: str = "First-line treatment is amoxicillin 50 mg/kg/d",
) -> EvidenceChunk:
    """Factory function to create test EvidenceChunk objects."""
    return EvidenceChunk(
        run_id=run_id,
        source_id=source_id,
        text=text,
        chunk_index=0,
    )


def make_link(
    claim: Claim,
    chunk: EvidenceChunk,
    binding_score: float = 0.8,
) -> ClaimEvidenceLink:
    """Factory function to create test ClaimEvidenceLink objects."""
    return ClaimEvidenceLink(
        claim_id=claim.id,
        evidence_chunk_id=chunk.id,
        binding_type=BindingType.KEYWORD,
        binding_score=binding_score,
    )


class TestEvalsStage:
    """Tests for Stage 08: Evals."""

    def test_evals_stage_name_is_evals(self) -> None:
        """Evals stage should identify itself as 'evals'."""
        from procedurewriter.pipeline.stages.s08_evals import EvalsStage

        stage = EvalsStage()
        assert stage.name == "evals"

    def test_evals_input_requires_claims_links_and_unbound(self) -> None:
        """Evals input must have claims, links, and unbound_claims fields."""
        from procedurewriter.pipeline.stages.s08_evals import EvalsInput

        claim = make_claim()
        chunk = make_chunk()
        link = make_link(claim, chunk)

        input_data = EvalsInput(
            run_id="test-run",
            run_dir=Path("/tmp/test"),
            procedure_title="Test Procedure",
            claims=[claim],
            links=[link],
            unbound_claims=[],
        )
        assert len(input_data.claims) == 1
        assert len(input_data.links) == 1

    def test_evals_output_has_issues_list(self, tmp_path: Path) -> None:
        """Evals output should contain a list of Issue objects."""
        from procedurewriter.pipeline.stages.s08_evals import (
            EvalsInput,
            EvalsStage,
        )

        stage = EvalsStage()
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = EvalsInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            claims=[],
            links=[],
            unbound_claims=[],
        )

        result = stage.execute(input_data)

        assert hasattr(result, "issues")
        assert isinstance(result.issues, list)

    def test_evals_output_has_gates_list(self, tmp_path: Path) -> None:
        """Evals output should contain a list of Gate objects."""
        from procedurewriter.pipeline.stages.s08_evals import (
            EvalsInput,
            EvalsStage,
        )

        stage = EvalsStage()
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = EvalsInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            claims=[],
            links=[],
            unbound_claims=[],
        )

        result = stage.execute(input_data)

        assert hasattr(result, "gates")
        assert isinstance(result.gates, list)

    def test_evals_output_has_all_required_fields(self, tmp_path: Path) -> None:
        """Evals output should contain all fields needed by ReviseLoop stage."""
        from procedurewriter.pipeline.stages.s08_evals import (
            EvalsInput,
            EvalsStage,
        )

        stage = EvalsStage()
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = EvalsInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            claims=[],
            links=[],
            unbound_claims=[],
        )

        result = stage.execute(input_data)

        assert hasattr(result, "run_id")
        assert hasattr(result, "run_dir")
        assert hasattr(result, "procedure_title")
        assert hasattr(result, "issues")
        assert hasattr(result, "gates")
        assert hasattr(result, "s0_count")
        assert hasattr(result, "s1_count")
        assert hasattr(result, "s2_count")
        assert hasattr(result, "all_gates_passed")
        assert result.run_id == "test-run"

    def test_evals_creates_issue_for_unbound_dose_claim(self, tmp_path: Path) -> None:
        """Evals should create S0 issue for DOSE claim without evidence."""
        from procedurewriter.pipeline.stages.s08_evals import (
            EvalsInput,
            EvalsStage,
        )

        # Unbound DOSE claim - this is S0 (safety critical)
        dose_claim = make_claim(
            claim_type=ClaimType.DOSE,
            text="amoxicillin 50 mg/kg/d",
            source_refs=[],
        )

        stage = EvalsStage()
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = EvalsInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test",
            claims=[dose_claim],
            links=[],
            unbound_claims=[dose_claim],
        )

        result = stage.execute(input_data)

        # Should have S0 issue for unbound dose
        s0_issues = [i for i in result.issues if i.severity == IssueSeverity.S0]
        assert len(s0_issues) >= 1
        assert any(i.code == IssueCode.DOSE_WITHOUT_EVIDENCE for i in s0_issues)

    def test_evals_creates_issue_for_unbound_threshold_claim(self, tmp_path: Path) -> None:
        """Evals should create S0 issue for THRESHOLD claim without evidence."""
        from procedurewriter.pipeline.stages.s08_evals import (
            EvalsInput,
            EvalsStage,
        )

        threshold_claim = make_claim(
            claim_type=ClaimType.THRESHOLD,
            text="SpO2 < 92%",
            source_refs=[],
        )

        stage = EvalsStage()
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = EvalsInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test",
            claims=[threshold_claim],
            links=[],
            unbound_claims=[threshold_claim],
        )

        result = stage.execute(input_data)

        s0_issues = [i for i in result.issues if i.severity == IssueSeverity.S0]
        assert len(s0_issues) >= 1
        assert any(i.code == IssueCode.THRESHOLD_WITHOUT_EVIDENCE for i in s0_issues)

    def test_evals_creates_s1_issue_for_general_unbound_claim(self, tmp_path: Path) -> None:
        """Evals should create S1 issue for non-critical unbound claims."""
        from procedurewriter.pipeline.stages.s08_evals import (
            EvalsInput,
            EvalsStage,
        )

        # RECOMMENDATION is S1, not S0
        rec_claim = make_claim(
            claim_type=ClaimType.RECOMMENDATION,
            text="Patient should be monitored",
            source_refs=[],
        )

        stage = EvalsStage()
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = EvalsInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test",
            claims=[rec_claim],
            links=[],
            unbound_claims=[rec_claim],
        )

        result = stage.execute(input_data)

        s1_issues = [i for i in result.issues if i.severity == IssueSeverity.S1]
        assert len(s1_issues) >= 1
        assert any(i.code == IssueCode.CLAIM_BINDING_FAILED for i in s1_issues)

    def test_evals_evaluates_s0_gate(self, tmp_path: Path) -> None:
        """Evals should evaluate S0 safety gate."""
        from procedurewriter.pipeline.stages.s08_evals import (
            EvalsInput,
            EvalsStage,
        )

        stage = EvalsStage()
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = EvalsInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test",
            claims=[],
            links=[],
            unbound_claims=[],
        )

        result = stage.execute(input_data)

        s0_gates = [g for g in result.gates if g.gate_type == GateType.S0_SAFETY]
        assert len(s0_gates) == 1
        assert s0_gates[0].status in (GateStatus.PASS, GateStatus.FAIL)

    def test_evals_s0_gate_fails_with_s0_issues(self, tmp_path: Path) -> None:
        """S0 gate should fail if there are S0 issues."""
        from procedurewriter.pipeline.stages.s08_evals import (
            EvalsInput,
            EvalsStage,
        )

        # Unbound DOSE = S0 issue
        dose_claim = make_claim(claim_type=ClaimType.DOSE)

        stage = EvalsStage()
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = EvalsInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test",
            claims=[dose_claim],
            links=[],
            unbound_claims=[dose_claim],
        )

        result = stage.execute(input_data)

        s0_gate = next(g for g in result.gates if g.gate_type == GateType.S0_SAFETY)
        assert s0_gate.status == GateStatus.FAIL
        assert result.all_gates_passed is False

    def test_evals_s0_gate_passes_without_s0_issues(self, tmp_path: Path) -> None:
        """S0 gate should pass if there are no S0 issues."""
        from procedurewriter.pipeline.stages.s08_evals import (
            EvalsInput,
            EvalsStage,
        )

        # Bound claim = no issues
        claim = make_claim(source_refs=["SRC001"])
        chunk = make_chunk(source_id="SRC001")
        link = make_link(claim, chunk)

        stage = EvalsStage()
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = EvalsInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test",
            claims=[claim],
            links=[link],
            unbound_claims=[],
        )

        result = stage.execute(input_data)

        s0_gate = next(g for g in result.gates if g.gate_type == GateType.S0_SAFETY)
        assert s0_gate.status == GateStatus.PASS

    def test_evals_emits_progress_event(self, tmp_path: Path) -> None:
        """Evals should emit a progress event when starting."""
        from procedurewriter.pipeline.stages.s08_evals import (
            EvalsInput,
            EvalsStage,
        )

        mock_emitter = MagicMock()
        stage = EvalsStage()
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = EvalsInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            claims=[],
            links=[],
            unbound_claims=[],
            emitter=mock_emitter,
        )

        stage.execute(input_data)

        mock_emitter.emit.assert_called()

    def test_evals_handles_empty_inputs(self, tmp_path: Path) -> None:
        """Evals should handle empty claims/links gracefully."""
        from procedurewriter.pipeline.stages.s08_evals import (
            EvalsInput,
            EvalsStage,
        )

        stage = EvalsStage()
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = EvalsInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            claims=[],
            links=[],
            unbound_claims=[],
        )

        result = stage.execute(input_data)

        assert result.issues == []
        assert result.s0_count == 0
        assert result.s1_count == 0
        assert result.all_gates_passed is True

    def test_evals_passes_through_run_dir(self, tmp_path: Path) -> None:
        """Evals should pass through run_dir for subsequent stages."""
        from procedurewriter.pipeline.stages.s08_evals import (
            EvalsInput,
            EvalsStage,
        )

        stage = EvalsStage()
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = EvalsInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            claims=[],
            links=[],
            unbound_claims=[],
        )

        result = stage.execute(input_data)

        assert result.run_dir == run_dir

    def test_evals_counts_issues_by_severity(self, tmp_path: Path) -> None:
        """Evals should count issues by severity level."""
        from procedurewriter.pipeline.stages.s08_evals import (
            EvalsInput,
            EvalsStage,
        )

        # Create claims that will generate different severity issues
        dose_claim = make_claim(claim_type=ClaimType.DOSE)  # S0
        rec_claim = make_claim(claim_type=ClaimType.RECOMMENDATION)  # S1

        stage = EvalsStage()
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = EvalsInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test",
            claims=[dose_claim, rec_claim],
            links=[],
            unbound_claims=[dose_claim, rec_claim],
        )

        result = stage.execute(input_data)

        assert result.s0_count >= 1  # At least one S0 for dose
        assert result.s1_count >= 1  # At least one S1 for recommendation

    def test_evals_creates_final_gate(self, tmp_path: Path) -> None:
        """Evals should create a FINAL gate summarizing all gates."""
        from procedurewriter.pipeline.stages.s08_evals import (
            EvalsInput,
            EvalsStage,
        )

        stage = EvalsStage()
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = EvalsInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test",
            claims=[],
            links=[],
            unbound_claims=[],
        )

        result = stage.execute(input_data)

        final_gates = [g for g in result.gates if g.gate_type == GateType.FINAL]
        assert len(final_gates) == 1

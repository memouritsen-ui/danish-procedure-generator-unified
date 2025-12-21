"""Tests for Gate and GateStatus models.

TDD: These tests are written FIRST before implementation.
Run: pytest tests/models/test_gates.py -v

Gates are checkpoints in the pipeline that determine if procedure can proceed:
- S0 gate: Must have 0 S0 (safety-critical) issues to pass
- S1 gate: Must have 0 S1 (quality-critical) issues to pass
"""

from datetime import datetime
from uuid import UUID

import pytest


class TestGateStatus:
    """Tests for GateStatus enum."""

    def test_gate_status_has_all_values(self):
        """GateStatus enum should have PASS, FAIL, PENDING."""
        from procedurewriter.models.gates import GateStatus

        assert GateStatus.PASS.value == "pass"
        assert GateStatus.FAIL.value == "fail"
        assert GateStatus.PENDING.value == "pending"

    def test_gate_status_count(self):
        """Should have exactly 3 status values."""
        from procedurewriter.models.gates import GateStatus

        assert len(GateStatus) == 3

    def test_gate_status_from_string(self):
        """Should be able to get GateStatus from string."""
        from procedurewriter.models.gates import GateStatus

        assert GateStatus("pass") == GateStatus.PASS
        assert GateStatus("fail") == GateStatus.FAIL
        assert GateStatus("pending") == GateStatus.PENDING


class TestGateType:
    """Tests for GateType enum."""

    def test_gate_type_has_required_values(self):
        """GateType enum should have S0, S1, and FINAL gates."""
        from procedurewriter.models.gates import GateType

        assert GateType.S0_SAFETY.value == "s0_safety"
        assert GateType.S1_QUALITY.value == "s1_quality"
        assert GateType.FINAL.value == "final"

    def test_gate_type_count(self):
        """Should have exactly 3 gate types."""
        from procedurewriter.models.gates import GateType

        assert len(GateType) == 3


class TestGate:
    """Tests for Gate Pydantic model."""

    def test_gate_creation_minimal(self):
        """Should create Gate with minimal required fields."""
        from procedurewriter.models.gates import Gate, GateStatus, GateType

        gate = Gate(
            run_id="test-run-123",
            gate_type=GateType.S0_SAFETY,
            status=GateStatus.PENDING,
        )

        assert gate.run_id == "test-run-123"
        assert gate.gate_type == GateType.S0_SAFETY
        assert gate.status == GateStatus.PENDING
        assert gate.issues_checked == 0
        assert gate.issues_failed == 0
        assert gate.message is None

    def test_gate_creation_full(self):
        """Should create Gate with all fields populated."""
        from procedurewriter.models.gates import Gate, GateStatus, GateType

        gate = Gate(
            run_id="test-run-456",
            gate_type=GateType.S1_QUALITY,
            status=GateStatus.FAIL,
            issues_checked=15,
            issues_failed=2,
            message="2 quality issues must be resolved",
        )

        assert gate.run_id == "test-run-456"
        assert gate.gate_type == GateType.S1_QUALITY
        assert gate.status == GateStatus.FAIL
        assert gate.issues_checked == 15
        assert gate.issues_failed == 2
        assert gate.message == "2 quality issues must be resolved"

    def test_gate_has_auto_id(self):
        """Gate should auto-generate a UUID id."""
        from procedurewriter.models.gates import Gate, GateStatus, GateType

        gate = Gate(
            run_id="test-run",
            gate_type=GateType.S0_SAFETY,
            status=GateStatus.PENDING,
        )

        assert gate.id is not None
        UUID(str(gate.id))

    def test_gate_has_timestamps(self):
        """Gate should have created_at and evaluated_at timestamps."""
        from procedurewriter.models.gates import Gate, GateStatus, GateType

        gate = Gate(
            run_id="test-run",
            gate_type=GateType.S0_SAFETY,
            status=GateStatus.PENDING,
        )

        assert gate.created_at is not None
        assert isinstance(gate.created_at, datetime)
        assert gate.evaluated_at is None  # Not evaluated yet

    def test_gate_evaluated_at_set_on_pass_fail(self):
        """evaluated_at should be set when status is PASS or FAIL."""
        from procedurewriter.models.gates import Gate, GateStatus, GateType

        passing_gate = Gate(
            run_id="test-run",
            gate_type=GateType.S0_SAFETY,
            status=GateStatus.PASS,
            evaluated_at="2024-12-21T12:00:00Z",
        )
        assert passing_gate.evaluated_at is not None

        failing_gate = Gate(
            run_id="test-run",
            gate_type=GateType.S1_QUALITY,
            status=GateStatus.FAIL,
            evaluated_at="2024-12-21T12:30:00Z",
        )
        assert failing_gate.evaluated_at is not None

    def test_gate_serialization(self):
        """Should serialize to dict/JSON properly."""
        from procedurewriter.models.gates import Gate, GateStatus, GateType

        gate = Gate(
            run_id="test-run",
            gate_type=GateType.S0_SAFETY,
            status=GateStatus.PASS,
            issues_checked=10,
            issues_failed=0,
            message="All safety checks passed",
        )

        data = gate.model_dump()

        assert data["run_id"] == "test-run"
        assert data["gate_type"] == "s0_safety"
        assert data["status"] == "pass"
        assert data["issues_checked"] == 10
        assert data["issues_failed"] == 0
        assert data["message"] == "All safety checks passed"
        assert "id" in data
        assert "created_at" in data

    def test_gate_deserialization(self):
        """Should deserialize from dict properly."""
        from procedurewriter.models.gates import Gate, GateStatus, GateType

        data = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "run_id": "test-run",
            "gate_type": "s1_quality",
            "status": "fail",
            "issues_checked": 20,
            "issues_failed": 3,
            "message": "3 quality issues remain",
            "created_at": "2024-12-21T12:00:00Z",
            "evaluated_at": "2024-12-21T12:05:00Z",
        }

        gate = Gate.model_validate(data)

        assert gate.run_id == "test-run"
        assert gate.gate_type == GateType.S1_QUALITY
        assert gate.status == GateStatus.FAIL
        assert gate.issues_failed == 3


class TestGateHelpers:
    """Tests for helper methods on Gate model."""

    def test_is_passed_property(self):
        """Should have is_passed property."""
        from procedurewriter.models.gates import Gate, GateStatus, GateType

        passed = Gate(
            run_id="test-run",
            gate_type=GateType.S0_SAFETY,
            status=GateStatus.PASS,
        )
        assert passed.is_passed is True

        failed = Gate(
            run_id="test-run",
            gate_type=GateType.S0_SAFETY,
            status=GateStatus.FAIL,
        )
        assert failed.is_passed is False

        pending = Gate(
            run_id="test-run",
            gate_type=GateType.S0_SAFETY,
            status=GateStatus.PENDING,
        )
        assert pending.is_passed is False

    def test_is_evaluated_property(self):
        """Should have is_evaluated property."""
        from procedurewriter.models.gates import Gate, GateStatus, GateType

        passed = Gate(
            run_id="test-run",
            gate_type=GateType.S0_SAFETY,
            status=GateStatus.PASS,
        )
        assert passed.is_evaluated is True

        failed = Gate(
            run_id="test-run",
            gate_type=GateType.S1_QUALITY,
            status=GateStatus.FAIL,
        )
        assert failed.is_evaluated is True

        pending = Gate(
            run_id="test-run",
            gate_type=GateType.FINAL,
            status=GateStatus.PENDING,
        )
        assert pending.is_evaluated is False

    def test_is_safety_gate_property(self):
        """Should identify S0 safety gates."""
        from procedurewriter.models.gates import Gate, GateStatus, GateType

        s0_gate = Gate(
            run_id="test-run",
            gate_type=GateType.S0_SAFETY,
            status=GateStatus.PENDING,
        )
        assert s0_gate.is_safety_gate is True

        s1_gate = Gate(
            run_id="test-run",
            gate_type=GateType.S1_QUALITY,
            status=GateStatus.PENDING,
        )
        assert s1_gate.is_safety_gate is False

    def test_gate_label_property(self):
        """Should have human-readable gate labels."""
        from procedurewriter.models.gates import Gate, GateStatus, GateType

        s0 = Gate(
            run_id="test-run",
            gate_type=GateType.S0_SAFETY,
            status=GateStatus.PENDING,
        )
        assert s0.gate_label == "Safety Gate (S0)"

        s1 = Gate(
            run_id="test-run",
            gate_type=GateType.S1_QUALITY,
            status=GateStatus.PENDING,
        )
        assert s1.gate_label == "Quality Gate (S1)"

        final = Gate(
            run_id="test-run",
            gate_type=GateType.FINAL,
            status=GateStatus.PENDING,
        )
        assert final.gate_label == "Final Gate"


class TestGateValidation:
    """Tests for gate validation logic."""

    def test_issues_failed_cannot_exceed_checked(self):
        """issues_failed should not exceed issues_checked."""
        from pydantic import ValidationError

        from procedurewriter.models.gates import Gate, GateStatus, GateType

        # Valid: failed < checked
        gate = Gate(
            run_id="test-run",
            gate_type=GateType.S0_SAFETY,
            status=GateStatus.FAIL,
            issues_checked=10,
            issues_failed=3,
        )
        assert gate.issues_failed == 3

        # Invalid: failed > checked
        with pytest.raises(ValidationError):
            Gate(
                run_id="test-run",
                gate_type=GateType.S0_SAFETY,
                status=GateStatus.FAIL,
                issues_checked=5,
                issues_failed=10,
            )

    def test_issues_counts_non_negative(self):
        """Issue counts should be non-negative."""
        from pydantic import ValidationError

        from procedurewriter.models.gates import Gate, GateStatus, GateType

        # Invalid: negative checked
        with pytest.raises(ValidationError):
            Gate(
                run_id="test-run",
                gate_type=GateType.S0_SAFETY,
                status=GateStatus.PENDING,
                issues_checked=-1,
            )

        # Invalid: negative failed
        with pytest.raises(ValidationError):
            Gate(
                run_id="test-run",
                gate_type=GateType.S0_SAFETY,
                status=GateStatus.PENDING,
                issues_failed=-1,
            )

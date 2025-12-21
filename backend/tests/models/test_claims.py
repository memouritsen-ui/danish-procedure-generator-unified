"""Tests for Claim and ClaimType models.

TDD: These tests are written FIRST before implementation.
Run: pytest tests/models/test_claims.py -v
"""

from datetime import datetime, timezone
from uuid import UUID

import pytest


class TestClaimType:
    """Tests for ClaimType enum."""

    def test_claim_type_has_all_required_values(self):
        """ClaimType enum should have all 6 claim types from Phase 0 spec."""
        from procedurewriter.models.claims import ClaimType

        assert ClaimType.DOSE.value == "dose"
        assert ClaimType.THRESHOLD.value == "threshold"
        assert ClaimType.RECOMMENDATION.value == "recommendation"
        assert ClaimType.CONTRAINDICATION.value == "contraindication"
        assert ClaimType.RED_FLAG.value == "red_flag"
        assert ClaimType.ALGORITHM_STEP.value == "algorithm_step"

    def test_claim_type_count(self):
        """Should have exactly 6 claim types."""
        from procedurewriter.models.claims import ClaimType

        assert len(ClaimType) == 6

    def test_claim_type_from_string(self):
        """Should be able to get ClaimType from string value."""
        from procedurewriter.models.claims import ClaimType

        assert ClaimType("dose") == ClaimType.DOSE
        assert ClaimType("threshold") == ClaimType.THRESHOLD


class TestClaim:
    """Tests for Claim Pydantic model."""

    def test_claim_creation_minimal(self):
        """Should create Claim with minimal required fields."""
        from procedurewriter.models.claims import Claim, ClaimType

        claim = Claim(
            run_id="test-run-123",
            claim_type=ClaimType.DOSE,
            text="amoxicillin 50 mg/kg/d",
            line_number=1,
            confidence=0.9,
        )

        assert claim.run_id == "test-run-123"
        assert claim.claim_type == ClaimType.DOSE
        assert claim.text == "amoxicillin 50 mg/kg/d"
        assert claim.line_number == 1
        assert claim.confidence == 0.9
        assert claim.normalized_value is None
        assert claim.unit is None
        assert claim.source_refs == []

    def test_claim_creation_full(self):
        """Should create Claim with all fields populated."""
        from procedurewriter.models.claims import Claim, ClaimType

        claim = Claim(
            run_id="test-run-456",
            claim_type=ClaimType.THRESHOLD,
            text="CURB-65 score >=3",
            normalized_value="CURB-65 >= 3",
            unit=None,
            source_refs=["SRC0020", "SRC0021"],
            line_number=42,
            confidence=0.95,
        )

        assert claim.run_id == "test-run-456"
        assert claim.claim_type == ClaimType.THRESHOLD
        assert claim.text == "CURB-65 score >=3"
        assert claim.normalized_value == "CURB-65 >= 3"
        assert claim.source_refs == ["SRC0020", "SRC0021"]
        assert claim.line_number == 42
        assert claim.confidence == 0.95

    def test_claim_has_auto_id(self):
        """Claim should auto-generate a UUID id."""
        from procedurewriter.models.claims import Claim, ClaimType

        claim = Claim(
            run_id="test-run",
            claim_type=ClaimType.DOSE,
            text="test",
            line_number=1,
            confidence=0.8,
        )

        # Should have a valid UUID
        assert claim.id is not None
        UUID(str(claim.id))  # Raises if invalid

    def test_claim_has_created_at(self):
        """Claim should have auto-generated created_at timestamp."""
        from procedurewriter.models.claims import Claim, ClaimType

        claim = Claim(
            run_id="test-run",
            claim_type=ClaimType.DOSE,
            text="test",
            line_number=1,
            confidence=0.8,
        )

        assert claim.created_at is not None
        assert isinstance(claim.created_at, datetime)

    def test_claim_confidence_validation(self):
        """Confidence should be between 0 and 1."""
        from procedurewriter.models.claims import Claim, ClaimType

        # Valid confidence
        claim = Claim(
            run_id="test-run",
            claim_type=ClaimType.DOSE,
            text="test",
            line_number=1,
            confidence=0.5,
        )
        assert claim.confidence == 0.5

        # Boundary values
        claim_min = Claim(
            run_id="test-run",
            claim_type=ClaimType.DOSE,
            text="test",
            line_number=1,
            confidence=0.0,
        )
        assert claim_min.confidence == 0.0

        claim_max = Claim(
            run_id="test-run",
            claim_type=ClaimType.DOSE,
            text="test",
            line_number=1,
            confidence=1.0,
        )
        assert claim_max.confidence == 1.0

    def test_claim_confidence_invalid_raises(self):
        """Invalid confidence values should raise ValidationError."""
        from pydantic import ValidationError

        from procedurewriter.models.claims import Claim, ClaimType

        with pytest.raises(ValidationError):
            Claim(
                run_id="test-run",
                claim_type=ClaimType.DOSE,
                text="test",
                line_number=1,
                confidence=1.5,  # Invalid: > 1
            )

        with pytest.raises(ValidationError):
            Claim(
                run_id="test-run",
                claim_type=ClaimType.DOSE,
                text="test",
                line_number=1,
                confidence=-0.1,  # Invalid: < 0
            )

    def test_claim_line_number_positive(self):
        """Line number should be positive integer."""
        from pydantic import ValidationError

        from procedurewriter.models.claims import Claim, ClaimType

        with pytest.raises(ValidationError):
            Claim(
                run_id="test-run",
                claim_type=ClaimType.DOSE,
                text="test",
                line_number=0,  # Invalid: must be >= 1
                confidence=0.8,
            )

        with pytest.raises(ValidationError):
            Claim(
                run_id="test-run",
                claim_type=ClaimType.DOSE,
                text="test",
                line_number=-1,  # Invalid: negative
                confidence=0.8,
            )

    def test_claim_text_required(self):
        """Text field should be required and non-empty."""
        from pydantic import ValidationError

        from procedurewriter.models.claims import Claim, ClaimType

        with pytest.raises(ValidationError):
            Claim(
                run_id="test-run",
                claim_type=ClaimType.DOSE,
                text="",  # Invalid: empty
                line_number=1,
                confidence=0.8,
            )

    def test_claim_serialization(self):
        """Should serialize to dict/JSON properly."""
        from procedurewriter.models.claims import Claim, ClaimType

        claim = Claim(
            run_id="test-run",
            claim_type=ClaimType.DOSE,
            text="amoxicillin 50 mg/kg/d",
            normalized_value="amoxicillin 50mg/kg/day",
            unit="mg/kg/d",
            source_refs=["SRC0023"],
            line_number=5,
            confidence=0.9,
        )

        data = claim.model_dump()

        assert data["run_id"] == "test-run"
        assert data["claim_type"] == "dose"
        assert data["text"] == "amoxicillin 50 mg/kg/d"
        assert data["normalized_value"] == "amoxicillin 50mg/kg/day"
        assert data["unit"] == "mg/kg/d"
        assert data["source_refs"] == ["SRC0023"]
        assert data["line_number"] == 5
        assert data["confidence"] == 0.9
        assert "id" in data
        assert "created_at" in data

    def test_claim_deserialization(self):
        """Should deserialize from dict properly."""
        from procedurewriter.models.claims import Claim, ClaimType

        data = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "run_id": "test-run",
            "claim_type": "threshold",
            "text": "sat <92%",
            "normalized_value": "SpO2 < 92%",
            "unit": "%",
            "source_refs": ["SRC0024"],
            "line_number": 10,
            "confidence": 0.85,
            "created_at": "2024-12-21T12:00:00Z",
        }

        claim = Claim.model_validate(data)

        assert claim.run_id == "test-run"
        assert claim.claim_type == ClaimType.THRESHOLD
        assert claim.text == "sat <92%"
        assert claim.normalized_value == "SpO2 < 92%"
        assert claim.confidence == 0.85


class TestClaimWithDoseDetails:
    """Tests for dose-specific claim creation patterns."""

    def test_dose_claim_with_unit(self):
        """Should handle dose claims with unit properly."""
        from procedurewriter.models.claims import Claim, ClaimType

        claim = Claim(
            run_id="test-run",
            claim_type=ClaimType.DOSE,
            text="benzyl-penicillin 100 mg/kg/d fordelt på 3 doser",
            normalized_value="100",
            unit="mg/kg/d",
            source_refs=["SRC0023"],
            line_number=15,
            confidence=0.9,
        )

        assert claim.claim_type == ClaimType.DOSE
        assert claim.unit == "mg/kg/d"


class TestClaimWithThresholdDetails:
    """Tests for threshold-specific claim patterns."""

    def test_threshold_curb65(self):
        """Should handle CURB-65 threshold properly."""
        from procedurewriter.models.claims import Claim, ClaimType

        claim = Claim(
            run_id="test-run",
            claim_type=ClaimType.THRESHOLD,
            text="CURB-65 score 2-4",
            normalized_value="CURB-65 [2,4]",
            source_refs=["SRC0020"],
            line_number=20,
            confidence=0.85,
        )

        assert claim.claim_type == ClaimType.THRESHOLD
        assert "CURB-65" in claim.text


class TestClaimHelpers:
    """Tests for any helper methods on Claim model."""

    def test_claim_has_sources_property(self):
        """Should have has_sources property."""
        from procedurewriter.models.claims import Claim, ClaimType

        claim_with_refs = Claim(
            run_id="test-run",
            claim_type=ClaimType.DOSE,
            text="test",
            source_refs=["SRC0001"],
            line_number=1,
            confidence=0.9,
        )
        assert claim_with_refs.has_sources is True

        claim_without_refs = Claim(
            run_id="test-run",
            claim_type=ClaimType.DOSE,
            text="test",
            source_refs=[],
            line_number=1,
            confidence=0.6,
        )
        assert claim_without_refs.has_sources is False

    def test_claim_is_high_confidence_property(self):
        """Should have is_high_confidence property (>= 0.8)."""
        from procedurewriter.models.claims import Claim, ClaimType

        high_conf = Claim(
            run_id="test-run",
            claim_type=ClaimType.DOSE,
            text="test",
            line_number=1,
            confidence=0.9,
        )
        assert high_conf.is_high_confidence is True

        low_conf = Claim(
            run_id="test-run",
            claim_type=ClaimType.DOSE,
            text="test",
            line_number=1,
            confidence=0.5,
        )
        assert low_conf.is_high_confidence is False

        boundary = Claim(
            run_id="test-run",
            claim_type=ClaimType.DOSE,
            text="test",
            line_number=1,
            confidence=0.8,
        )
        assert boundary.is_high_confidence is True

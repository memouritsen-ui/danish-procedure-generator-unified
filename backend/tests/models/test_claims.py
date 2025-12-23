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


class TestClaimDbConversion:
    """Tests for database conversion methods."""

    def test_to_db_row_returns_correct_tuple(self):
        """to_db_row() should return tuple matching DB column order."""
        import json
        from datetime import datetime, timezone
        from uuid import UUID

        from procedurewriter.models.claims import Claim, ClaimType

        fixed_id = UUID("550e8400-e29b-41d4-a716-446655440000")
        fixed_time = datetime(2024, 12, 21, 12, 0, 0, tzinfo=timezone.utc)

        claim = Claim(
            id=fixed_id,
            run_id="test-run-123",
            claim_type=ClaimType.DOSE,
            text="amoxicillin 50 mg/kg/d",
            normalized_value="50",
            unit="mg/kg/d",
            source_refs=["SRC0023", "SRC0024"],
            line_number=15,
            confidence=0.9,
            created_at=fixed_time,
        )

        row = claim.to_db_row()

        # Verify tuple structure matches DB schema
        assert isinstance(row, tuple)
        assert len(row) == 10

        # Verify each field
        assert row[0] == "550e8400-e29b-41d4-a716-446655440000"  # id (str)
        assert row[1] == "test-run-123"  # run_id
        assert row[2] == "dose"  # claim_type (enum value)
        assert row[3] == "amoxicillin 50 mg/kg/d"  # text
        assert row[4] == "50"  # normalized_value
        assert row[5] == "mg/kg/d"  # unit
        assert row[6] == '["SRC0023", "SRC0024"]'  # source_refs_json
        assert row[7] == 15  # line_number
        assert row[8] == 0.9  # confidence
        assert row[9] == "2024-12-21T12:00:00+00:00"  # created_at_utc

    def test_to_db_row_with_null_optional_fields(self):
        """to_db_row() should handle None values for optional fields."""
        import json
        from uuid import UUID

        from procedurewriter.models.claims import Claim, ClaimType

        claim = Claim(
            run_id="test-run",
            claim_type=ClaimType.THRESHOLD,
            text="CURB-65 >= 3",
            normalized_value=None,
            unit=None,
            source_refs=[],
            line_number=10,
            confidence=0.85,
        )

        row = claim.to_db_row()

        assert row[4] is None  # normalized_value
        assert row[5] is None  # unit
        assert row[6] == "[]"  # empty source_refs_json

    def test_to_db_row_id_is_string(self):
        """to_db_row() should convert UUID id to string."""
        from procedurewriter.models.claims import Claim, ClaimType

        claim = Claim(
            run_id="test-run",
            claim_type=ClaimType.DOSE,
            text="test",
            line_number=1,
            confidence=0.9,
        )

        row = claim.to_db_row()

        # First element should be string, not UUID
        assert isinstance(row[0], str)
        assert len(row[0]) == 36  # UUID string format

    def test_from_db_row_reconstructs_claim(self):
        """from_db_row() should reconstruct Claim from DB tuple."""
        from datetime import datetime, timezone
        from uuid import UUID

        from procedurewriter.models.claims import Claim, ClaimType

        # Simulate DB row tuple in same order as to_db_row()
        db_row = (
            "550e8400-e29b-41d4-a716-446655440000",  # id
            "test-run-123",  # run_id
            "dose",  # claim_type
            "amoxicillin 50 mg/kg/d",  # text
            "50",  # normalized_value
            "mg/kg/d",  # unit
            '["SRC0023", "SRC0024"]',  # source_refs_json
            15,  # line_number
            0.9,  # confidence
            "2024-12-21T12:00:00+00:00",  # created_at_utc
        )

        claim = Claim.from_db_row(db_row)

        assert claim.id == UUID("550e8400-e29b-41d4-a716-446655440000")
        assert claim.run_id == "test-run-123"
        assert claim.claim_type == ClaimType.DOSE
        assert claim.text == "amoxicillin 50 mg/kg/d"
        assert claim.normalized_value == "50"
        assert claim.unit == "mg/kg/d"
        assert claim.source_refs == ["SRC0023", "SRC0024"]
        assert claim.line_number == 15
        assert claim.confidence == 0.9
        assert claim.created_at == datetime(2024, 12, 21, 12, 0, 0, tzinfo=timezone.utc)

    def test_from_db_row_with_null_optional_fields(self):
        """from_db_row() should handle None values for optional fields."""
        from procedurewriter.models.claims import Claim, ClaimType

        db_row = (
            "550e8400-e29b-41d4-a716-446655440000",  # id
            "test-run",  # run_id
            "threshold",  # claim_type
            "CURB-65 >= 3",  # text
            None,  # normalized_value
            None,  # unit
            "[]",  # empty source_refs_json
            10,  # line_number
            0.85,  # confidence
            "2024-12-21T12:00:00+00:00",  # created_at_utc
        )

        claim = Claim.from_db_row(db_row)

        assert claim.normalized_value is None
        assert claim.unit is None
        assert claim.source_refs == []

    def test_from_db_row_roundtrip(self):
        """to_db_row() and from_db_row() should roundtrip correctly."""
        from procedurewriter.models.claims import Claim, ClaimType

        original = Claim(
            run_id="test-run",
            claim_type=ClaimType.RED_FLAG,
            text="Temperature > 38.5C",
            normalized_value="38.5",
            unit="C",
            source_refs=["SRC0001"],
            line_number=25,
            confidence=0.95,
        )

        # Roundtrip: model -> DB row -> model
        row = original.to_db_row()
        reconstructed = Claim.from_db_row(row)

        assert reconstructed.id == original.id
        assert reconstructed.run_id == original.run_id
        assert reconstructed.claim_type == original.claim_type
        assert reconstructed.text == original.text
        assert reconstructed.normalized_value == original.normalized_value
        assert reconstructed.unit == original.unit
        assert reconstructed.source_refs == original.source_refs
        assert reconstructed.line_number == original.line_number
        assert reconstructed.confidence == original.confidence


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


# ============================================================================
# R6-007: DANISH TEXT TESTS
# ============================================================================

class TestClaimDanishText:
    """Tests for Danish medical procedure text handling.

    R6-007: Comprehensive tests using real Danish medical text patterns.
    Verifies proper handling of:
    - Danish special characters (æ, ø, å, Æ, Ø, Å)
    - Danish medical terminology
    - Danish dosage formats
    - Danish clinical warning patterns
    """

    # --- Named constants for Danish test data (R6-010) ---
    DANISH_DOSE_TEXT = "benzyl-penicillin 100 mg/kg/døgn fordelt på 3 doser"
    DANISH_WARNING_TEXT = "OBS: Høj risiko for anafylaksi ved penicillinallergi"
    DANISH_CONTRAINDICATION_TEXT = "Kontraindiceret ved overfølsomhed over for penicillin"
    DANISH_THRESHOLD_TEXT = "Behandles ved CRP > 100 mg/L eller temperatur ≥ 38,5°C"
    DANISH_RECOMMENDATION_TEXT = "Anbefales ved mistænkt bakteriel infektion"
    DANISH_ALGORITHM_TEXT = "Ved respirationssvigt: 1) Fri luftvej 2) Ilt 15L/min 3) Tilkald anæstesi"

    def test_dose_claim_with_danish_characters(self):
        """Should handle Danish dose text with special characters (æ, ø, å)."""
        from procedurewriter.models.claims import Claim, ClaimType

        claim = Claim(
            run_id="test-run-danish",
            claim_type=ClaimType.DOSE,
            text=self.DANISH_DOSE_TEXT,
            normalized_value="100",
            unit="mg/kg/døgn",
            line_number=1,
            confidence=0.9,
        )

        assert claim.text == self.DANISH_DOSE_TEXT, (
            "Danish dose text should be preserved exactly"
        )
        assert "døgn" in claim.text, "Danish 'ø' character should be preserved"
        assert claim.unit == "mg/kg/døgn", "Danish unit should be preserved"

    def test_redflag_claim_with_danish_warning(self):
        """Should handle Danish warning text with 'OBS' pattern."""
        from procedurewriter.models.claims import Claim, ClaimType

        claim = Claim(
            run_id="test-run-danish",
            claim_type=ClaimType.RED_FLAG,
            text=self.DANISH_WARNING_TEXT,
            line_number=5,
            confidence=0.95,
        )

        assert "OBS" in claim.text, "Danish warning marker should be preserved"
        assert "Høj" in claim.text, "Danish 'ø' character should be preserved"
        assert claim.claim_type == ClaimType.RED_FLAG

    def test_contraindication_claim_danish(self):
        """Should handle Danish contraindication text."""
        from procedurewriter.models.claims import Claim, ClaimType

        claim = Claim(
            run_id="test-run-danish",
            claim_type=ClaimType.CONTRAINDICATION,
            text=self.DANISH_CONTRAINDICATION_TEXT,
            line_number=10,
            confidence=0.88,
        )

        assert "Kontraindiceret" in claim.text, (
            "Danish contraindication term should be preserved"
        )
        assert "overfølsomhed" in claim.text, (
            "Danish 'ø' in 'overfølsomhed' should be preserved"
        )

    def test_threshold_claim_danish_comma_decimal(self):
        """Should handle Danish decimal format (comma instead of period)."""
        from procedurewriter.models.claims import Claim, ClaimType

        claim = Claim(
            run_id="test-run-danish",
            claim_type=ClaimType.THRESHOLD,
            text=self.DANISH_THRESHOLD_TEXT,
            normalized_value="CRP > 100 OR temp >= 38.5",
            line_number=15,
            confidence=0.85,
        )

        assert "38,5°C" in claim.text, (
            "Danish comma decimal format should be preserved in original text"
        )
        assert "temperatur" in claim.text.lower(), (
            "Danish 'temperatur' should be preserved"
        )

    def test_recommendation_claim_danish(self):
        """Should handle Danish recommendation text with 'anbefales'."""
        from procedurewriter.models.claims import Claim, ClaimType

        claim = Claim(
            run_id="test-run-danish",
            claim_type=ClaimType.RECOMMENDATION,
            text=self.DANISH_RECOMMENDATION_TEXT,
            line_number=20,
            confidence=0.82,
        )

        assert "Anbefales" in claim.text, (
            "Danish recommendation pattern should be preserved"
        )
        assert "mistænkt" in claim.text, (
            "Danish 'æ' character should be preserved"
        )

    def test_algorithm_step_claim_danish(self):
        """Should handle Danish algorithm text with numbered steps."""
        from procedurewriter.models.claims import Claim, ClaimType

        claim = Claim(
            run_id="test-run-danish",
            claim_type=ClaimType.ALGORITHM_STEP,
            text=self.DANISH_ALGORITHM_TEXT,
            line_number=25,
            confidence=0.9,
        )

        assert "respirationssvigt" in claim.text, (
            "Danish compound medical term should be preserved"
        )
        assert "anæstesi" in claim.text, (
            "Danish 'æ' in 'anæstesi' should be preserved"
        )

    @pytest.mark.parametrize(
        "danish_text,expected_char",
        [
            ("Lægemiddel administreres hver 8. time", "æ"),
            ("Patienten overvåges kontinuerligt", "å"),
            ("Høj dosis kræver monitorering", "ø"),
            ("ÆGTE medicinsk tekst", "Æ"),
            ("ØJEBLIKKELIG intervention", "Ø"),
            ("ÅND FRIT under behandling", "Å"),
        ],
        ids=["ae_lower", "aa_lower", "oe_lower", "AE_upper", "OE_upper", "AA_upper"],
    )
    def test_danish_special_characters_parametrized(
        self,
        danish_text: str,
        expected_char: str,
    ):
        """Verify all Danish special characters are preserved (R6-012: parametrize)."""
        from procedurewriter.models.claims import Claim, ClaimType

        claim = Claim(
            run_id="test-run-danish",
            claim_type=ClaimType.DOSE,
            text=danish_text,
            line_number=1,
            confidence=0.9,
        )

        assert expected_char in claim.text, (
            f"Danish character '{expected_char}' should be preserved in claim text"
        )

    def test_danish_text_serialization_roundtrip(self):
        """Danish text should survive model_dump/model_validate roundtrip."""
        from procedurewriter.models.claims import Claim, ClaimType

        original = Claim(
            run_id="test-run-danish",
            claim_type=ClaimType.DOSE,
            text="Dosis: 50 mg/kg/døgn fordelt på 3 doser",
            normalized_value="50",
            unit="mg/kg/døgn",
            line_number=1,
            confidence=0.9,
        )

        # Roundtrip: model -> dict -> model
        data = original.model_dump()
        reconstructed = Claim.model_validate(data)

        assert reconstructed.text == original.text, (
            "Danish text should survive serialization roundtrip"
        )
        assert reconstructed.unit == original.unit, (
            "Danish unit should survive serialization roundtrip"
        )

    def test_danish_text_db_roundtrip(self):
        """Danish text should survive database roundtrip."""
        from procedurewriter.models.claims import Claim, ClaimType

        original = Claim(
            run_id="test-run-danish",
            claim_type=ClaimType.RED_FLAG,
            text="Særlig opmærksomhed ved ældre patienter med nedsat nyrefunktion",
            line_number=1,
            confidence=0.88,
        )

        # Roundtrip: model -> DB row -> model
        row = original.to_db_row()
        reconstructed = Claim.from_db_row(row)

        assert reconstructed.text == original.text, (
            "Danish text should survive database roundtrip"
        )
        assert "ældre" in reconstructed.text, (
            "Danish 'æ' should survive database roundtrip"
        )
        assert "opmærksomhed" in reconstructed.text, (
            "Danish 'ø' should survive database roundtrip"
        )

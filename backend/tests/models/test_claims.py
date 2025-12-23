"""Tests for Claim and ClaimType models.

TDD: These tests are written FIRST before implementation.
Run: pytest tests/models/test_claims.py -v
"""

from datetime import datetime, timezone
from uuid import UUID

import pytest


# --- Test Constants (R6-010: Named constants instead of magic numbers) ---
CLAIM_TYPE_COUNT = 6
RUN_ID_BASIC = "test-run"
RUN_ID_MINIMAL = "test-run-123"
RUN_ID_FULL = "test-run-456"
RUN_ID_DANISH = "test-run-danish"

LINE_NUMBER_ONE = 1
LINE_NUMBER_FIVE = 5
LINE_NUMBER_TEN = 10
LINE_NUMBER_FIFTEEN = 15
LINE_NUMBER_TWENTY = 20
LINE_NUMBER_TWENTY_FIVE = 25
LINE_NUMBER_FORTY_TWO = 42
LINE_NUMBER_ZERO = 0
LINE_NUMBER_NEGATIVE_ONE = -1

CONFIDENCE_MIN = 0.0
CONFIDENCE_LOW = 0.5
CONFIDENCE_LOWISH = 0.6
CONFIDENCE_BOUNDARY = 0.8
CONFIDENCE_RECOMMENDATION = 0.82
CONFIDENCE_MEDIUM = 0.85
CONFIDENCE_ALMOST_HIGH = 0.88
CONFIDENCE_HIGH = 0.9
CONFIDENCE_VERY_HIGH = 0.95
CONFIDENCE_MAX = 1.0
CONFIDENCE_TOO_HIGH = 1.5
CONFIDENCE_TOO_LOW = -0.1

DB_ROW_LENGTH = 10
UUID_STRING_LENGTH = 36
FIXED_UUID_STR = "550e8400-e29b-41d4-a716-446655440000"
FIXED_CREATED_AT = datetime(2024, 12, 21, 12, 0, 0, tzinfo=timezone.utc)
FIXED_CREATED_AT_Z = "2024-12-21T12:00:00Z"
FIXED_CREATED_AT_OFFSET = "2024-12-21T12:00:00+00:00"

DOSE_TEXT = "amoxicillin 50 mg/kg/d"
NORMALIZED_DOSE_TEXT = "amoxicillin 50mg/kg/day"
SATURATION_TEXT = "sat <92%"
THRESHOLD_TEXT = "CURB-65 score >=3"
THRESHOLD_TEXT_SIMPLE = "CURB-65 >= 3"
TEXT_SAMPLE = "test"
UNIT_MG_PER_KG_PER_DAY = "mg/kg/d"


class TestClaimType:
    """Tests for ClaimType enum."""

    @pytest.mark.parametrize(
        "enum_name,expected_value",
        [
            ("DOSE", "dose"),
            ("THRESHOLD", "threshold"),
            ("RECOMMENDATION", "recommendation"),
            ("CONTRAINDICATION", "contraindication"),
            ("RED_FLAG", "red_flag"),
            ("ALGORITHM_STEP", "algorithm_step"),
        ],
        ids=[
            "dose",
            "threshold",
            "recommendation",
            "contraindication",
            "red_flag",
            "algorithm_step",
        ],
    )
    def test_claim_type_has_all_required_values(self, enum_name: str, expected_value: str):
        """ClaimType enum should have all 6 claim types from Phase 0 spec."""
        from procedurewriter.models.claims import ClaimType

        claim_type = getattr(ClaimType, enum_name)
        assert claim_type.value == expected_value, (
            f"{enum_name} should map to '{expected_value}', got '{claim_type.value}'"
        )

    def test_claim_type_count(self):
        """Should have exactly 6 claim types."""
        from procedurewriter.models.claims import ClaimType

        assert len(ClaimType) == CLAIM_TYPE_COUNT, (
            f"Expected {CLAIM_TYPE_COUNT} claim types, got {len(ClaimType)}"
        )

    @pytest.mark.parametrize(
        "value,enum_name",
        [
            ("dose", "DOSE"),
            ("threshold", "THRESHOLD"),
        ],
        ids=["dose", "threshold"],
    )
    def test_claim_type_from_string(self, value: str, enum_name: str):
        """Should be able to get ClaimType from string value."""
        from procedurewriter.models.claims import ClaimType

        expected = getattr(ClaimType, enum_name)
        assert ClaimType(value) == expected, (
            f"ClaimType('{value}') should map to {enum_name}"
        )


class TestClaim:
    """Tests for Claim Pydantic model."""

    def test_claim_creation_minimal(self):
        """Should create Claim with minimal required fields."""
        from procedurewriter.models.claims import Claim, ClaimType

        claim = Claim(
            run_id=RUN_ID_MINIMAL,
            claim_type=ClaimType.DOSE,
            text=DOSE_TEXT,
            line_number=LINE_NUMBER_ONE,
            confidence=CONFIDENCE_HIGH,
        )

        actual = (
            claim.run_id,
            claim.claim_type,
            claim.text,
            claim.line_number,
            claim.confidence,
            claim.normalized_value,
            claim.unit,
            claim.source_refs,
        )
        expected = (
            RUN_ID_MINIMAL,
            ClaimType.DOSE,
            DOSE_TEXT,
            LINE_NUMBER_ONE,
            CONFIDENCE_HIGH,
            None,
            None,
            [],
        )
        assert actual == expected, (
            f"Minimal claim fields mismatch: expected {expected}, got {actual}"
        )

    def test_claim_creation_full(self):
        """Should create Claim with all fields populated."""
        from procedurewriter.models.claims import Claim, ClaimType

        claim = Claim(
            run_id=RUN_ID_FULL,
            claim_type=ClaimType.THRESHOLD,
            text=THRESHOLD_TEXT,
            normalized_value=THRESHOLD_TEXT_SIMPLE,
            unit=None,
            source_refs=["SRC0020", "SRC0021"],
            line_number=LINE_NUMBER_FORTY_TWO,
            confidence=CONFIDENCE_VERY_HIGH,
        )

        actual = (
            claim.run_id,
            claim.claim_type,
            claim.text,
            claim.normalized_value,
            claim.source_refs,
            claim.line_number,
            claim.confidence,
        )
        expected = (
            RUN_ID_FULL,
            ClaimType.THRESHOLD,
            THRESHOLD_TEXT,
            THRESHOLD_TEXT_SIMPLE,
            ["SRC0020", "SRC0021"],
            LINE_NUMBER_FORTY_TWO,
            CONFIDENCE_VERY_HIGH,
        )
        assert actual == expected, (
            f"Full claim fields mismatch: expected {expected}, got {actual}"
        )

    def test_claim_has_auto_id(self):
        """Claim should auto-generate a UUID id."""
        from procedurewriter.models.claims import Claim, ClaimType

        claim = Claim(
            run_id=RUN_ID_BASIC,
            claim_type=ClaimType.DOSE,
            text=TEXT_SAMPLE,
            line_number=LINE_NUMBER_ONE,
            confidence=CONFIDENCE_BOUNDARY,
        )

        # Should have a valid UUID
        assert claim.id is not None, "Claim id should be auto-generated"
        UUID(str(claim.id))  # Raises if invalid

    def test_claim_has_created_at(self):
        """Claim should have auto-generated created_at timestamp."""
        from procedurewriter.models.claims import Claim, ClaimType

        claim = Claim(
            run_id=RUN_ID_BASIC,
            claim_type=ClaimType.DOSE,
            text=TEXT_SAMPLE,
            line_number=LINE_NUMBER_ONE,
            confidence=CONFIDENCE_BOUNDARY,
        )

        assert claim.created_at is not None, "Claim created_at should be auto-generated"
        assert isinstance(claim.created_at, datetime), (
            "Claim created_at should be a datetime instance"
        )

    @pytest.mark.parametrize(
        "confidence",
        [CONFIDENCE_LOW, CONFIDENCE_MIN, CONFIDENCE_MAX],
        ids=["mid", "min", "max"],
    )
    def test_claim_confidence_validation(self, confidence: float):
        """Confidence should be between 0 and 1."""
        from procedurewriter.models.claims import Claim, ClaimType

        claim = Claim(
            run_id=RUN_ID_BASIC,
            claim_type=ClaimType.DOSE,
            text=TEXT_SAMPLE,
            line_number=LINE_NUMBER_ONE,
            confidence=confidence,
        )
        assert claim.confidence == confidence, (
            f"Confidence should be {confidence}, got {claim.confidence}"
        )

    @pytest.mark.parametrize(
        "confidence",
        [CONFIDENCE_TOO_HIGH, CONFIDENCE_TOO_LOW],
        ids=["above_max", "below_min"],
    )
    def test_claim_confidence_invalid_raises(self, confidence: float):
        """Invalid confidence values should raise ValidationError."""
        from pydantic import ValidationError

        from procedurewriter.models.claims import Claim, ClaimType

        with pytest.raises(ValidationError):
            Claim(
                run_id=RUN_ID_BASIC,
                claim_type=ClaimType.DOSE,
                text=TEXT_SAMPLE,
                line_number=LINE_NUMBER_ONE,
                confidence=confidence,
            )

    @pytest.mark.parametrize(
        "line_number",
        [LINE_NUMBER_ZERO, LINE_NUMBER_NEGATIVE_ONE],
        ids=["zero", "negative"],
    )
    def test_claim_line_number_positive(self, line_number: int):
        """Line number should be positive integer."""
        from pydantic import ValidationError

        from procedurewriter.models.claims import Claim, ClaimType

        with pytest.raises(ValidationError):
            Claim(
                run_id=RUN_ID_BASIC,
                claim_type=ClaimType.DOSE,
                text=TEXT_SAMPLE,
                line_number=line_number,
                confidence=CONFIDENCE_BOUNDARY,
            )

    def test_claim_text_required(self):
        """Text field should be required and non-empty."""
        from pydantic import ValidationError

        from procedurewriter.models.claims import Claim, ClaimType

        with pytest.raises(ValidationError):
            Claim(
                run_id=RUN_ID_BASIC,
                claim_type=ClaimType.DOSE,
                text="",  # Invalid: empty
                line_number=LINE_NUMBER_ONE,
                confidence=CONFIDENCE_BOUNDARY,
            )

    def test_claim_serialization(self):
        """Should serialize to dict/JSON properly."""
        from procedurewriter.models.claims import Claim, ClaimType

        claim = Claim(
            run_id=RUN_ID_BASIC,
            claim_type=ClaimType.DOSE,
            text=DOSE_TEXT,
            normalized_value=NORMALIZED_DOSE_TEXT,
            unit=UNIT_MG_PER_KG_PER_DAY,
            source_refs=["SRC0023"],
            line_number=LINE_NUMBER_FIVE,
            confidence=CONFIDENCE_HIGH,
        )

        data = claim.model_dump()

        expected = {
            "run_id": RUN_ID_BASIC,
            "claim_type": "dose",
            "text": DOSE_TEXT,
            "normalized_value": NORMALIZED_DOSE_TEXT,
            "unit": UNIT_MG_PER_KG_PER_DAY,
            "source_refs": ["SRC0023"],
            "line_number": LINE_NUMBER_FIVE,
            "confidence": CONFIDENCE_HIGH,
        }
        for key, value in expected.items():
            assert data[key] == value, (
                f"{key} should be {value}, got {data[key]}"
            )
        assert "id" in data, "Serialized claim should include id"
        assert "created_at" in data, "Serialized claim should include created_at"

    def test_claim_deserialization(self):
        """Should deserialize from dict properly."""
        from procedurewriter.models.claims import Claim, ClaimType

        data = {
            "id": FIXED_UUID_STR,
            "run_id": RUN_ID_BASIC,
            "claim_type": "threshold",
            "text": SATURATION_TEXT,
            "normalized_value": "SpO2 < 92%",
            "unit": "%",
            "source_refs": ["SRC0024"],
            "line_number": LINE_NUMBER_TEN,
            "confidence": CONFIDENCE_MEDIUM,
            "created_at": FIXED_CREATED_AT_Z,
        }

        claim = Claim.model_validate(data)

        assert claim.run_id == RUN_ID_BASIC, "run_id should roundtrip correctly"
        assert claim.claim_type == ClaimType.THRESHOLD, (
            "claim_type should deserialize to ClaimType.THRESHOLD"
        )
        assert claim.text == SATURATION_TEXT, "Text should deserialize correctly"
        assert claim.normalized_value == "SpO2 < 92%", (
            "normalized_value should deserialize correctly"
        )
        assert claim.confidence == CONFIDENCE_MEDIUM, (
            "confidence should deserialize correctly"
        )


class TestClaimWithDoseDetails:
    """Tests for dose-specific claim creation patterns."""

    def test_dose_claim_with_unit(self):
        """Should handle dose claims with unit properly."""
        from procedurewriter.models.claims import Claim, ClaimType

        claim = Claim(
            run_id=RUN_ID_BASIC,
            claim_type=ClaimType.DOSE,
            text="benzyl-penicillin 100 mg/kg/d fordelt på 3 doser",
            normalized_value="100",
            unit=UNIT_MG_PER_KG_PER_DAY,
            source_refs=["SRC0023"],
            line_number=LINE_NUMBER_FIFTEEN,
            confidence=CONFIDENCE_HIGH,
        )

        assert claim.claim_type == ClaimType.DOSE, "Claim type should be DOSE"
        assert claim.unit == UNIT_MG_PER_KG_PER_DAY, "Dose unit should be preserved"


class TestClaimWithThresholdDetails:
    """Tests for threshold-specific claim patterns."""

    def test_threshold_curb65(self):
        """Should handle CURB-65 threshold properly."""
        from procedurewriter.models.claims import Claim, ClaimType

        claim = Claim(
            run_id=RUN_ID_BASIC,
            claim_type=ClaimType.THRESHOLD,
            text="CURB-65 score 2-4",
            normalized_value="CURB-65 [2,4]",
            source_refs=["SRC0020"],
            line_number=LINE_NUMBER_TWENTY,
            confidence=CONFIDENCE_MEDIUM,
        )

        assert claim.claim_type == ClaimType.THRESHOLD, "Claim type should be THRESHOLD"
        assert "CURB-65" in claim.text, "Threshold text should include CURB-65"


class TestClaimDbConversion:
    """Tests for database conversion methods."""

    def test_to_db_row_returns_correct_tuple(self):
        """to_db_row() should return tuple matching DB column order."""
        from procedurewriter.models.claims import Claim, ClaimType

        fixed_id = UUID(FIXED_UUID_STR)

        claim = Claim(
            id=fixed_id,
            run_id=RUN_ID_MINIMAL,
            claim_type=ClaimType.DOSE,
            text=DOSE_TEXT,
            normalized_value="50",
            unit=UNIT_MG_PER_KG_PER_DAY,
            source_refs=["SRC0023", "SRC0024"],
            line_number=LINE_NUMBER_FIFTEEN,
            confidence=CONFIDENCE_HIGH,
            created_at=FIXED_CREATED_AT,
        )

        row = claim.to_db_row()

        expected_row = (
            FIXED_UUID_STR,  # id (str)
            RUN_ID_MINIMAL,  # run_id
            "dose",  # claim_type (enum value)
            DOSE_TEXT,  # text
            "50",  # normalized_value
            UNIT_MG_PER_KG_PER_DAY,  # unit
            '["SRC0023", "SRC0024"]',  # source_refs_json
            LINE_NUMBER_FIFTEEN,  # line_number
            CONFIDENCE_HIGH,  # confidence
            FIXED_CREATED_AT_OFFSET,  # created_at_utc
        )

        assert isinstance(row, tuple), "to_db_row should return a tuple"
        assert len(row) == DB_ROW_LENGTH, (
            f"Expected {DB_ROW_LENGTH} columns, got {len(row)}"
        )
        assert row == expected_row, (
            f"DB row should match expected tuple, got {row}"
        )

    def test_to_db_row_with_null_optional_fields(self):
        """to_db_row() should handle None values for optional fields."""
        from procedurewriter.models.claims import Claim, ClaimType

        claim = Claim(
            run_id=RUN_ID_BASIC,
            claim_type=ClaimType.THRESHOLD,
            text=THRESHOLD_TEXT_SIMPLE,
            normalized_value=None,
            unit=None,
            source_refs=[],
            line_number=LINE_NUMBER_TEN,
            confidence=CONFIDENCE_MEDIUM,
        )

        row = claim.to_db_row()

        assert row[4] is None, "normalized_value should be None"
        assert row[5] is None, "unit should be None"
        assert row[6] == "[]", "source_refs should serialize to empty list JSON"

    def test_to_db_row_id_is_string(self):
        """to_db_row() should convert UUID id to string."""
        from procedurewriter.models.claims import Claim, ClaimType

        claim = Claim(
            run_id=RUN_ID_BASIC,
            claim_type=ClaimType.DOSE,
            text=TEXT_SAMPLE,
            line_number=LINE_NUMBER_ONE,
            confidence=CONFIDENCE_HIGH,
        )

        row = claim.to_db_row()

        # First element should be string, not UUID
        assert isinstance(row[0], str), "Row id should be a string"
        assert len(row[0]) == UUID_STRING_LENGTH, (
            f"UUID string length should be {UUID_STRING_LENGTH}"
        )

    def test_from_db_row_reconstructs_claim(self):
        """from_db_row() should reconstruct Claim from DB tuple."""
        from procedurewriter.models.claims import Claim, ClaimType

        # Simulate DB row tuple in same order as to_db_row()
        db_row = (
            FIXED_UUID_STR,  # id
            RUN_ID_MINIMAL,  # run_id
            "dose",  # claim_type
            DOSE_TEXT,  # text
            "50",  # normalized_value
            UNIT_MG_PER_KG_PER_DAY,  # unit
            '["SRC0023", "SRC0024"]',  # source_refs_json
            LINE_NUMBER_FIFTEEN,  # line_number
            CONFIDENCE_HIGH,  # confidence
            FIXED_CREATED_AT_OFFSET,  # created_at_utc
        )

        claim = Claim.from_db_row(db_row)

        actual = (
            claim.id,
            claim.run_id,
            claim.claim_type,
            claim.text,
            claim.normalized_value,
            claim.unit,
            claim.source_refs,
            claim.line_number,
            claim.confidence,
            claim.created_at,
        )
        expected = (
            UUID(FIXED_UUID_STR),
            RUN_ID_MINIMAL,
            ClaimType.DOSE,
            DOSE_TEXT,
            "50",
            UNIT_MG_PER_KG_PER_DAY,
            ["SRC0023", "SRC0024"],
            LINE_NUMBER_FIFTEEN,
            CONFIDENCE_HIGH,
            FIXED_CREATED_AT,
        )
        assert actual == expected, (
            f"Claim should reconstruct from DB row, got {actual}"
        )

    def test_from_db_row_with_null_optional_fields(self):
        """from_db_row() should handle None values for optional fields."""
        from procedurewriter.models.claims import Claim, ClaimType

        db_row = (
            FIXED_UUID_STR,  # id
            RUN_ID_BASIC,  # run_id
            "threshold",  # claim_type
            THRESHOLD_TEXT_SIMPLE,  # text
            None,  # normalized_value
            None,  # unit
            "[]",  # empty source_refs_json
            LINE_NUMBER_TEN,  # line_number
            CONFIDENCE_MEDIUM,  # confidence
            FIXED_CREATED_AT_OFFSET,  # created_at_utc
        )

        claim = Claim.from_db_row(db_row)

        actual = (claim.normalized_value, claim.unit, claim.source_refs)
        expected = (None, None, [])
        assert actual == expected, (
            "Optional fields should be None/empty when DB row has nulls"
        )

    def test_from_db_row_roundtrip(self):
        """to_db_row() and from_db_row() should roundtrip correctly."""
        from procedurewriter.models.claims import Claim, ClaimType

        original = Claim(
            run_id=RUN_ID_BASIC,
            claim_type=ClaimType.RED_FLAG,
            text="Temperature > 38.5C",
            normalized_value="38.5",
            unit="C",
            source_refs=["SRC0001"],
            line_number=LINE_NUMBER_TWENTY_FIVE,
            confidence=CONFIDENCE_VERY_HIGH,
        )

        # Roundtrip: model -> DB row -> model
        row = original.to_db_row()
        reconstructed = Claim.from_db_row(row)

        actual = (
            reconstructed.id,
            reconstructed.run_id,
            reconstructed.claim_type,
            reconstructed.text,
            reconstructed.normalized_value,
            reconstructed.unit,
            reconstructed.source_refs,
            reconstructed.line_number,
            reconstructed.confidence,
        )
        expected = (
            original.id,
            original.run_id,
            original.claim_type,
            original.text,
            original.normalized_value,
            original.unit,
            original.source_refs,
            original.line_number,
            original.confidence,
        )
        assert actual == expected, "Claim should roundtrip through DB conversion"


class TestClaimHelpers:
    """Tests for any helper methods on Claim model."""

    @pytest.mark.parametrize(
        "source_refs,expected",
        [
            (["SRC0001"], True),
            ([], False),
        ],
        ids=["with_refs", "without_refs"],
    )
    def test_claim_has_sources_property(self, source_refs: list[str], expected: bool):
        """Should have has_sources property."""
        from procedurewriter.models.claims import Claim, ClaimType

        claim = Claim(
            run_id=RUN_ID_BASIC,
            claim_type=ClaimType.DOSE,
            text=TEXT_SAMPLE,
            source_refs=source_refs,
            line_number=LINE_NUMBER_ONE,
            confidence=CONFIDENCE_HIGH,
        )
        assert claim.has_sources is expected, (
            f"has_sources should be {expected} for refs {source_refs}"
        )

    @pytest.mark.parametrize(
        "confidence,expected",
        [
            (CONFIDENCE_HIGH, True),
            (CONFIDENCE_LOW, False),
            (CONFIDENCE_BOUNDARY, True),
        ],
        ids=["high", "low", "boundary"],
    )
    def test_claim_is_high_confidence_property(self, confidence: float, expected: bool):
        """Should have is_high_confidence property (>= 0.8)."""
        from procedurewriter.models.claims import Claim, ClaimType

        claim = Claim(
            run_id=RUN_ID_BASIC,
            claim_type=ClaimType.DOSE,
            text=TEXT_SAMPLE,
            line_number=LINE_NUMBER_ONE,
            confidence=confidence,
        )
        assert claim.is_high_confidence is expected, (
            f"is_high_confidence should be {expected} for confidence {confidence}"
        )


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
            run_id=RUN_ID_DANISH,
            claim_type=ClaimType.DOSE,
            text=self.DANISH_DOSE_TEXT,
            normalized_value="100",
            unit="mg/kg/døgn",
            line_number=LINE_NUMBER_ONE,
            confidence=CONFIDENCE_HIGH,
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
            run_id=RUN_ID_DANISH,
            claim_type=ClaimType.RED_FLAG,
            text=self.DANISH_WARNING_TEXT,
            line_number=LINE_NUMBER_FIVE,
            confidence=CONFIDENCE_VERY_HIGH,
        )

        assert "OBS" in claim.text, "Danish warning marker should be preserved"
        assert "Høj" in claim.text, "Danish 'ø' character should be preserved"
        assert claim.claim_type == ClaimType.RED_FLAG, (
            "Claim type should be RED_FLAG for Danish warning text"
        )

    def test_contraindication_claim_danish(self):
        """Should handle Danish contraindication text."""
        from procedurewriter.models.claims import Claim, ClaimType

        claim = Claim(
            run_id=RUN_ID_DANISH,
            claim_type=ClaimType.CONTRAINDICATION,
            text=self.DANISH_CONTRAINDICATION_TEXT,
            line_number=LINE_NUMBER_TEN,
            confidence=CONFIDENCE_ALMOST_HIGH,
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
            run_id=RUN_ID_DANISH,
            claim_type=ClaimType.THRESHOLD,
            text=self.DANISH_THRESHOLD_TEXT,
            normalized_value="CRP > 100 OR temp >= 38.5",
            line_number=LINE_NUMBER_FIFTEEN,
            confidence=CONFIDENCE_MEDIUM,
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
            run_id=RUN_ID_DANISH,
            claim_type=ClaimType.RECOMMENDATION,
            text=self.DANISH_RECOMMENDATION_TEXT,
            line_number=LINE_NUMBER_TWENTY,
            confidence=CONFIDENCE_RECOMMENDATION,
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
            run_id=RUN_ID_DANISH,
            claim_type=ClaimType.ALGORITHM_STEP,
            text=self.DANISH_ALGORITHM_TEXT,
            line_number=LINE_NUMBER_TWENTY_FIVE,
            confidence=CONFIDENCE_HIGH,
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
            run_id=RUN_ID_DANISH,
            claim_type=ClaimType.DOSE,
            text=danish_text,
            line_number=LINE_NUMBER_ONE,
            confidence=CONFIDENCE_HIGH,
        )

        assert expected_char in claim.text, (
            f"Danish character '{expected_char}' should be preserved in claim text"
        )

    def test_danish_text_serialization_roundtrip(self):
        """Danish text should survive model_dump/model_validate roundtrip."""
        from procedurewriter.models.claims import Claim, ClaimType

        original = Claim(
            run_id=RUN_ID_DANISH,
            claim_type=ClaimType.DOSE,
            text="Dosis: 50 mg/kg/døgn fordelt på 3 doser",
            normalized_value="50",
            unit="mg/kg/døgn",
            line_number=LINE_NUMBER_ONE,
            confidence=CONFIDENCE_HIGH,
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
            run_id=RUN_ID_DANISH,
            claim_type=ClaimType.RED_FLAG,
            text="Særlig opmærksomhed ved ældre patienter med nedsat nyrefunktion",
            line_number=LINE_NUMBER_ONE,
            confidence=CONFIDENCE_ALMOST_HIGH,
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

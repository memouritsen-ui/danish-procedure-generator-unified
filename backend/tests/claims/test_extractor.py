"""Tests for ClaimExtractor - pattern-based claim extraction.

TDD: These tests define the expected interface and behavior.
"""

import pytest

from procedurewriter.claims.extractor import ClaimExtractor
from procedurewriter.models.claims import Claim, ClaimType


class TestClaimExtractorInit:
    """Tests for ClaimExtractor initialization."""

    def test_create_extractor(self) -> None:
        """ClaimExtractor can be instantiated."""
        extractor = ClaimExtractor()
        assert extractor is not None

    def test_extractor_has_extract_method(self) -> None:
        """ClaimExtractor has an extract method."""
        extractor = ClaimExtractor()
        assert hasattr(extractor, "extract")
        assert callable(extractor.extract)

    def test_extractor_has_run_id_attribute(self) -> None:
        """ClaimExtractor accepts run_id in constructor."""
        extractor = ClaimExtractor(run_id="test-run-123")
        assert extractor.run_id == "test-run-123"


class TestClaimExtractorExtract:
    """Tests for ClaimExtractor.extract() method."""

    def test_extract_returns_list(self) -> None:
        """extract() returns a list."""
        extractor = ClaimExtractor(run_id="test")
        result = extractor.extract("")
        assert isinstance(result, list)

    def test_extract_empty_text_returns_empty_list(self) -> None:
        """Empty text returns empty list."""
        extractor = ClaimExtractor(run_id="test")
        result = extractor.extract("")
        assert result == []

    def test_extract_whitespace_only_returns_empty_list(self) -> None:
        """Whitespace-only text returns empty list."""
        extractor = ClaimExtractor(run_id="test")
        result = extractor.extract("   \n\t  ")
        assert result == []

    def test_extract_returns_claim_objects(self) -> None:
        """extract() returns Claim model instances."""
        extractor = ClaimExtractor(run_id="test")
        # Text with a known dose pattern
        text = "Give amoxicillin 50 mg/kg/d for pneumonia."
        result = extractor.extract(text)
        assert len(result) > 0
        assert all(isinstance(c, Claim) for c in result)

    def test_extracted_claims_have_run_id(self) -> None:
        """Extracted claims have correct run_id."""
        extractor = ClaimExtractor(run_id="my-run-id")
        text = "Give amoxicillin 50 mg/kg/d."
        result = extractor.extract(text)
        assert len(result) > 0
        for claim in result:
            assert claim.run_id == "my-run-id"


class TestDoseExtraction:
    """Tests for DOSE claim extraction patterns."""

    @pytest.fixture
    def extractor(self) -> ClaimExtractor:
        """Create extractor for tests."""
        return ClaimExtractor(run_id="dose-test")

    def test_extracts_mg_per_kg_per_day(self, extractor: ClaimExtractor) -> None:
        """Extracts mg/kg/d dosage pattern."""
        text = "amoxicillin 50 mg/kg/d fordelt pa 2-3 doser"
        claims = extractor.extract(text)
        dose_claims = [c for c in claims if c.claim_type == ClaimType.DOSE]
        assert len(dose_claims) >= 1
        assert any("50" in c.text for c in dose_claims)

    def test_extracts_mg_fixed_dose(self, extractor: ClaimExtractor) -> None:
        """Extracts fixed mg dose pattern."""
        text = "Give clarithromycin 500 mg twice daily"
        claims = extractor.extract(text)
        dose_claims = [c for c in claims if c.claim_type == ClaimType.DOSE]
        assert len(dose_claims) >= 1
        assert any("500" in c.text for c in dose_claims)

    def test_extracts_iv_dose(self, extractor: ClaimExtractor) -> None:
        """Extracts i.v. dose pattern."""
        text = "Give benzyl-penicillin 100 mg/kg i.v."
        claims = extractor.extract(text)
        dose_claims = [c for c in claims if c.claim_type == ClaimType.DOSE]
        assert len(dose_claims) >= 1

    def test_extracts_danish_dose_pattern(self, extractor: ClaimExtractor) -> None:
        """Extracts Danish dose pattern with 'fordelt pa'."""
        text = "amoxicillin 50 mg/kg/d fordelt pa 3 doser"
        claims = extractor.extract(text)
        dose_claims = [c for c in claims if c.claim_type == ClaimType.DOSE]
        assert len(dose_claims) >= 1

    def test_dose_has_confidence(self, extractor: ClaimExtractor) -> None:
        """Dose claims have confidence score."""
        text = "amoxicillin 50 mg/kg/d"
        claims = extractor.extract(text)
        dose_claims = [c for c in claims if c.claim_type == ClaimType.DOSE]
        assert len(dose_claims) >= 1
        for claim in dose_claims:
            assert 0.0 <= claim.confidence <= 1.0

    def test_dose_has_line_number(self, extractor: ClaimExtractor) -> None:
        """Dose claims have line_number set."""
        text = "Line 1\namoxicillin 50 mg/kg/d"
        claims = extractor.extract(text)
        dose_claims = [c for c in claims if c.claim_type == ClaimType.DOSE]
        assert len(dose_claims) >= 1
        # Should be on line 2
        assert dose_claims[0].line_number == 2


class TestThresholdExtraction:
    """Tests for THRESHOLD claim extraction patterns."""

    @pytest.fixture
    def extractor(self) -> ClaimExtractor:
        """Create extractor for tests."""
        return ClaimExtractor(run_id="threshold-test")

    def test_extracts_curb65_score(self, extractor: ClaimExtractor) -> None:
        """Extracts CURB-65 score thresholds."""
        text = "Patients with CURB-65 score >= 3 should be admitted"
        claims = extractor.extract(text)
        threshold_claims = [c for c in claims if c.claim_type == ClaimType.THRESHOLD]
        assert len(threshold_claims) >= 1
        assert any("CURB" in c.text.upper() for c in threshold_claims)

    def test_extracts_oxygen_saturation(self, extractor: ClaimExtractor) -> None:
        """Extracts SpO2/saturation thresholds."""
        text = "If saturation < 92%, give oxygen"
        claims = extractor.extract(text)
        threshold_claims = [c for c in claims if c.claim_type == ClaimType.THRESHOLD]
        assert len(threshold_claims) >= 1
        assert any("92" in c.text for c in threshold_claims)

    def test_extracts_age_threshold(self, extractor: ClaimExtractor) -> None:
        """Extracts age thresholds."""
        text = "For patients alder > 65 years, consider ICU"
        claims = extractor.extract(text)
        threshold_claims = [c for c in claims if c.claim_type == ClaimType.THRESHOLD]
        assert len(threshold_claims) >= 1

    def test_extracts_temperature_threshold(self, extractor: ClaimExtractor) -> None:
        """Extracts temperature thresholds."""
        text = "Fever defined as temperatur > 38C"
        claims = extractor.extract(text)
        threshold_claims = [c for c in claims if c.claim_type == ClaimType.THRESHOLD]
        assert len(threshold_claims) >= 1
        assert any("38" in c.text for c in threshold_claims)

    def test_extracts_respiratory_rate(self, extractor: ClaimExtractor) -> None:
        """Extracts respiratory rate thresholds."""
        text = "RF > 30/min indicates severe disease"
        claims = extractor.extract(text)
        threshold_claims = [c for c in claims if c.claim_type == ClaimType.THRESHOLD]
        assert len(threshold_claims) >= 1


class TestSourceRefExtraction:
    """Tests for source reference extraction."""

    @pytest.fixture
    def extractor(self) -> ClaimExtractor:
        """Create extractor for tests."""
        return ClaimExtractor(run_id="source-test")

    def test_extracts_source_refs_from_line(self, extractor: ClaimExtractor) -> None:
        """Extracts source references [SRC001] from claims."""
        text = "Give amoxicillin 50 mg/kg/d for pneumonia. [SRC0023]"
        claims = extractor.extract(text)
        assert len(claims) >= 1
        # At least one claim should have source ref
        claims_with_refs = [c for c in claims if c.source_refs]
        assert len(claims_with_refs) >= 1
        assert "SRC0023" in claims_with_refs[0].source_refs[0]

    def test_extracts_multiple_source_refs(self, extractor: ClaimExtractor) -> None:
        """Extracts multiple source references."""
        text = "Dose guideline [SRC0001] [SRC0002]: amoxicillin 50 mg/kg/d"
        claims = extractor.extract(text)
        dose_claims = [c for c in claims if c.claim_type == ClaimType.DOSE]
        assert len(dose_claims) >= 1


class TestMultiLineExtraction:
    """Tests for multi-line text extraction."""

    @pytest.fixture
    def extractor(self) -> ClaimExtractor:
        """Create extractor for tests."""
        return ClaimExtractor(run_id="multiline-test")

    def test_extracts_from_multiple_lines(self, extractor: ClaimExtractor) -> None:
        """Extracts claims from multiple lines."""
        text = """Line 1: Introduction
Line 2: amoxicillin 50 mg/kg/d for infection
Line 3: saturation < 92% requires oxygen
Line 4: Conclusion"""
        claims = extractor.extract(text)
        assert len(claims) >= 2
        # Should have both dose and threshold
        types = {c.claim_type for c in claims}
        assert ClaimType.DOSE in types
        assert ClaimType.THRESHOLD in types

    def test_line_numbers_are_correct(self, extractor: ClaimExtractor) -> None:
        """Line numbers reflect actual line positions."""
        text = """Header
This is line 2
amoxicillin 50 mg/kg/d here on line 3
Line 4
saturation < 92% on line 5"""
        claims = extractor.extract(text)
        dose_claims = [c for c in claims if c.claim_type == ClaimType.DOSE]
        threshold_claims = [c for c in claims if c.claim_type == ClaimType.THRESHOLD]
        assert len(dose_claims) >= 1
        assert len(threshold_claims) >= 1
        # Dose on line 3, threshold on line 5
        assert dose_claims[0].line_number == 3
        assert threshold_claims[0].line_number == 5

    def test_skips_header_lines(self, extractor: ClaimExtractor) -> None:
        """Skips lines that start with # (markdown headers)."""
        text = """# Header with 50 mg dose
Normal line with amoxicillin 50 mg/kg/d"""
        claims = extractor.extract(text)
        # Should only extract from line 2, not the header
        assert all(c.line_number == 2 for c in claims)


class TestExtractorDefaults:
    """Tests for extractor default behavior."""

    def test_default_run_id_is_empty_string(self) -> None:
        """Default run_id is empty string if not provided."""
        extractor = ClaimExtractor()
        assert extractor.run_id == ""

    def test_claims_inherit_default_run_id(self) -> None:
        """Claims use the extractor's run_id."""
        extractor = ClaimExtractor()  # Default run_id
        text = "amoxicillin 50 mg/kg/d"
        claims = extractor.extract(text)
        assert len(claims) >= 1
        assert claims[0].run_id == ""

    def test_extract_all_method_alias(self) -> None:
        """extract_all() is an alias for extract()."""
        extractor = ClaimExtractor(run_id="test")
        text = "amoxicillin 50 mg/kg/d"
        # Both methods should exist and return same results
        assert hasattr(extractor, "extract_all")
        result1 = extractor.extract(text)
        result2 = extractor.extract_all(text)
        assert len(result1) == len(result2)

"""Tests for DOSE claim extraction patterns.

Comprehensive tests for all dose formats found in Danish medical procedures.
Based on Phase 0 validation work with real procedure data.
"""

import pytest

from procedurewriter.claims.extractor import ClaimExtractor
from procedurewriter.models.claims import Claim, ClaimType


@pytest.fixture
def extractor() -> ClaimExtractor:
    """Create extractor for tests."""
    return ClaimExtractor(run_id="dose-test")


class TestWeightBasedDoses:
    """Tests for weight-based dosing patterns (mg/kg)."""

    def test_mg_per_kg_per_day(self, extractor: ClaimExtractor) -> None:
        """Extracts mg/kg/d pattern."""
        text = "amoxicillin 50 mg/kg/d"
        claims = extractor.extract(text)
        dose_claims = [c for c in claims if c.claim_type == ClaimType.DOSE]
        assert len(dose_claims) >= 1
        assert any("50" in c.text and "mg/kg" in c.text for c in dose_claims)

    def test_mg_per_kg_per_dag(self, extractor: ClaimExtractor) -> None:
        """Extracts mg/kg/dag pattern (Danish spelling)."""
        text = "benzyl-penicillin 100 mg/kg/dag"
        claims = extractor.extract(text)
        dose_claims = [c for c in claims if c.claim_type == ClaimType.DOSE]
        assert len(dose_claims) >= 1
        assert any("100" in c.text for c in dose_claims)

    def test_mg_per_kg_single_dose(self, extractor: ClaimExtractor) -> None:
        """Extracts mg/kg single dose (no /d)."""
        text = "gentamicin 5 mg/kg"
        claims = extractor.extract(text)
        dose_claims = [c for c in claims if c.claim_type == ClaimType.DOSE]
        assert len(dose_claims) >= 1
        assert any("5" in c.text and "mg/kg" in c.text for c in dose_claims)

    def test_decimal_dose(self, extractor: ClaimExtractor) -> None:
        """Extracts decimal doses like 0.5 mg/kg."""
        text = "adrenalin 0.5 mg/kg i.v."
        claims = extractor.extract(text)
        dose_claims = [c for c in claims if c.claim_type == ClaimType.DOSE]
        assert len(dose_claims) >= 1
        assert any("0.5" in c.text or "0,5" in c.text for c in dose_claims)

    def test_comma_decimal_dose(self, extractor: ClaimExtractor) -> None:
        """Extracts Danish comma decimal (0,5 instead of 0.5)."""
        text = "adrenalin 0,5 mg/kg"
        claims = extractor.extract(text)
        dose_claims = [c for c in claims if c.claim_type == ClaimType.DOSE]
        assert len(dose_claims) >= 1


class TestFixedDoses:
    """Tests for fixed dose patterns (not weight-based)."""

    def test_fixed_mg_dose(self, extractor: ClaimExtractor) -> None:
        """Extracts fixed mg dose."""
        text = "clarithromycin 500 mg twice daily"
        claims = extractor.extract(text)
        dose_claims = [c for c in claims if c.claim_type == ClaimType.DOSE]
        assert len(dose_claims) >= 1
        assert any("500" in c.text for c in dose_claims)

    def test_fixed_g_dose(self, extractor: ClaimExtractor) -> None:
        """Extracts gram dose."""
        text = "ceftriaxon 2 g i.v."
        claims = extractor.extract(text)
        dose_claims = [c for c in claims if c.claim_type == ClaimType.DOSE]
        assert len(dose_claims) >= 1
        assert any("2" in c.text and "g" in c.text.lower() for c in dose_claims)

    def test_mcg_dose(self, extractor: ClaimExtractor) -> None:
        """Extracts microgram (mcg) dose."""
        text = "salbutamol 100 mcg inhalation"
        claims = extractor.extract(text)
        dose_claims = [c for c in claims if c.claim_type == ClaimType.DOSE]
        assert len(dose_claims) >= 1

    def test_ml_dose(self, extractor: ClaimExtractor) -> None:
        """Extracts ml dose for liquids."""
        text = "give 10 ml oral solution"
        claims = extractor.extract(text)
        dose_claims = [c for c in claims if c.claim_type == ClaimType.DOSE]
        assert len(dose_claims) >= 1

    def test_ie_dose(self, extractor: ClaimExtractor) -> None:
        """Extracts IE (international units) dose."""
        text = "heparin 5000 IE subcutant"
        claims = extractor.extract(text)
        dose_claims = [c for c in claims if c.claim_type == ClaimType.DOSE]
        assert len(dose_claims) >= 1


class TestDanishDosePatterns:
    """Tests for Danish-specific dose patterns."""

    def test_fordelt_pa_doser(self, extractor: ClaimExtractor) -> None:
        """Extracts 'fordelt pa X doser' pattern."""
        text = "amoxicillin 50 mg/kg/d fordelt pa 3 doser"
        claims = extractor.extract(text)
        dose_claims = [c for c in claims if c.claim_type == ClaimType.DOSE]
        assert len(dose_claims) >= 1
        # Should capture the full pattern including distribution

    def test_fordelt_pa_range(self, extractor: ClaimExtractor) -> None:
        """Extracts 'fordelt pa 2-3 doser' pattern."""
        text = "benzyl-penicillin 100 mg/kg/d fordelt pa 2-3 doser"
        claims = extractor.extract(text)
        dose_claims = [c for c in claims if c.claim_type == ClaimType.DOSE]
        assert len(dose_claims) >= 1

    def test_gange_pattern(self, extractor: ClaimExtractor) -> None:
        """Extracts 'x N gange' pattern."""
        text = "paracetamol 15 mg/kg x 4 gange dagligt"
        claims = extractor.extract(text)
        dose_claims = [c for c in claims if c.claim_type == ClaimType.DOSE]
        assert len(dose_claims) >= 1

    def test_hver_time_pattern(self, extractor: ClaimExtractor) -> None:
        """Extracts 'hver X time' pattern."""
        text = "500 mg hver 8 time"
        claims = extractor.extract(text)
        dose_claims = [c for c in claims if c.claim_type == ClaimType.DOSE]
        assert len(dose_claims) >= 1


class TestRoutePatterns:
    """Tests for administration route patterns."""

    def test_iv_route(self, extractor: ClaimExtractor) -> None:
        """Extracts i.v. administration."""
        text = "cefuroxim 750 mg i.v."
        claims = extractor.extract(text)
        dose_claims = [c for c in claims if c.claim_type == ClaimType.DOSE]
        assert len(dose_claims) >= 1

    def test_iv_without_dots(self, extractor: ClaimExtractor) -> None:
        """Extracts iv administration without dots."""
        text = "ampicillin 100 mg/kg iv"
        claims = extractor.extract(text)
        dose_claims = [c for c in claims if c.claim_type == ClaimType.DOSE]
        assert len(dose_claims) >= 1

    def test_po_route(self, extractor: ClaimExtractor) -> None:
        """Extracts p.o. (oral) administration."""
        text = "amoxicillin 750 mg p.o."
        claims = extractor.extract(text)
        dose_claims = [c for c in claims if c.claim_type == ClaimType.DOSE]
        assert len(dose_claims) >= 1


class TestRealProcedureExamples:
    """Tests with real examples from pneumoni procedure."""

    def test_amoxicillin_dose(self, extractor: ClaimExtractor) -> None:
        """Extracts amoxicillin dose from real procedure."""
        text = "Start antibiotika hos born med simpel pneumoni med oral amoxicillin 50 mg/kg/d fordelt pa 2-3 doser."
        claims = extractor.extract(text)
        dose_claims = [c for c in claims if c.claim_type == ClaimType.DOSE]
        assert len(dose_claims) >= 1
        assert any("amoxicillin" in c.text.lower() for c in dose_claims)

    def test_benzyl_penicillin_dose(self, extractor: ClaimExtractor) -> None:
        """Extracts benzyl-penicillin dose."""
        text = "Giv ved svar pneumoni i.v. benzyl-penicillin 100 mg/kg/d fordelt pa 3 doser."
        claims = extractor.extract(text)
        dose_claims = [c for c in claims if c.claim_type == ClaimType.DOSE]
        assert len(dose_claims) >= 1

    def test_clarithromycin_dose(self, extractor: ClaimExtractor) -> None:
        """Extracts clarithromycin dose."""
        text = "Suppleer med clarithromycin 15 mg/kg/d ved mistanke om atypisk pneumoni."
        claims = extractor.extract(text)
        dose_claims = [c for c in claims if c.claim_type == ClaimType.DOSE]
        assert len(dose_claims) >= 1

    def test_gentamicin_dose(self, extractor: ClaimExtractor) -> None:
        """Extracts gentamicin single dose."""
        text = "gentamicin 5 mg/kg x 1 dagligt"
        claims = extractor.extract(text)
        dose_claims = [c for c in claims if c.claim_type == ClaimType.DOSE]
        assert len(dose_claims) >= 1

    def test_metronidazol_dose(self, extractor: ClaimExtractor) -> None:
        """Extracts metronidazol dose."""
        text = "metronidazol 24 mg/kg/d fordelt pa 3 doser"
        claims = extractor.extract(text)
        dose_claims = [c for c in claims if c.claim_type == ClaimType.DOSE]
        assert len(dose_claims) >= 1


class TestDoseMetadata:
    """Tests for dose claim metadata (confidence, line_number, etc.)."""

    def test_dose_has_claim_type(self, extractor: ClaimExtractor) -> None:
        """Dose claims have correct claim_type."""
        text = "amoxicillin 50 mg/kg/d"
        claims = extractor.extract(text)
        assert all(c.claim_type == ClaimType.DOSE for c in claims)

    def test_dose_has_text(self, extractor: ClaimExtractor) -> None:
        """Dose claims have non-empty text."""
        text = "amoxicillin 50 mg/kg/d"
        claims = extractor.extract(text)
        assert all(c.text for c in claims)
        assert all(len(c.text) > 0 for c in claims)

    def test_dose_has_run_id(self, extractor: ClaimExtractor) -> None:
        """Dose claims have correct run_id."""
        text = "amoxicillin 50 mg/kg/d"
        claims = extractor.extract(text)
        assert all(c.run_id == "dose-test" for c in claims)

    def test_dose_has_line_number(self, extractor: ClaimExtractor) -> None:
        """Dose claims have valid line_number."""
        text = "line 1\namoxicillin 50 mg/kg/d on line 2"
        claims = extractor.extract(text)
        dose_claims = [c for c in claims if c.claim_type == ClaimType.DOSE]
        assert all(c.line_number >= 1 for c in dose_claims)
        assert dose_claims[0].line_number == 2

    def test_dose_has_confidence(self, extractor: ClaimExtractor) -> None:
        """Dose claims have confidence in valid range."""
        text = "amoxicillin 50 mg/kg/d"
        claims = extractor.extract(text)
        assert all(0.0 <= c.confidence <= 1.0 for c in claims)

    def test_dose_with_source_has_higher_confidence(
        self, extractor: ClaimExtractor
    ) -> None:
        """Doses with source refs have higher confidence."""
        text_with_ref = "amoxicillin 50 mg/kg/d [SRC0023]"
        text_without = "amoxicillin 50 mg/kg/d"

        claims_with = extractor.extract(text_with_ref)
        claims_without = extractor.extract(text_without)

        assert len(claims_with) >= 1
        assert len(claims_without) >= 1

        # With source should have higher confidence
        assert claims_with[0].confidence > claims_without[0].confidence


class TestNormalization:
    """Tests for dose value normalization."""

    def test_extracts_numeric_value(self, extractor: ClaimExtractor) -> None:
        """Dose claims have normalized_value extracted."""
        text = "amoxicillin 50 mg/kg/d"
        claims = extractor.extract(text)
        dose_claims = [c for c in claims if c.claim_type == ClaimType.DOSE]
        assert len(dose_claims) >= 1
        # Should have numeric value extracted
        assert dose_claims[0].normalized_value is not None

    def test_extracts_unit(self, extractor: ClaimExtractor) -> None:
        """Dose claims have unit extracted."""
        text = "amoxicillin 50 mg/kg/d"
        claims = extractor.extract(text)
        dose_claims = [c for c in claims if c.claim_type == ClaimType.DOSE]
        assert len(dose_claims) >= 1
        # Should have unit
        assert dose_claims[0].unit is not None
        assert dose_claims[0].unit.lower() == "mg"


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_no_false_positives_on_text(self, extractor: ClaimExtractor) -> None:
        """Should not extract doses from non-dose text."""
        text = "The patient was admitted for observation."
        claims = extractor.extract(text)
        dose_claims = [c for c in claims if c.claim_type == ClaimType.DOSE]
        assert len(dose_claims) == 0

    def test_multiple_doses_on_same_line(self, extractor: ClaimExtractor) -> None:
        """Extracts multiple doses from same line."""
        text = "Give amoxicillin 500 mg or clarithromycin 250 mg"
        claims = extractor.extract(text)
        dose_claims = [c for c in claims if c.claim_type == ClaimType.DOSE]
        assert len(dose_claims) >= 2

    def test_dose_in_parentheses(self, extractor: ClaimExtractor) -> None:
        """Extracts dose within parentheses."""
        text = "antibiotika (amoxicillin 50 mg/kg/d)"
        claims = extractor.extract(text)
        dose_claims = [c for c in claims if c.claim_type == ClaimType.DOSE]
        assert len(dose_claims) >= 1

    def test_very_large_dose(self, extractor: ClaimExtractor) -> None:
        """Handles large numeric doses."""
        text = "heparin 25000 IE infusion"
        claims = extractor.extract(text)
        dose_claims = [c for c in claims if c.claim_type == ClaimType.DOSE]
        assert len(dose_claims) >= 1

    def test_dose_with_special_chars_in_drug(self, extractor: ClaimExtractor) -> None:
        """Handles drug names with hyphens and special chars."""
        text = "benzyl-penicillin 100 mg/kg/d"
        claims = extractor.extract(text)
        dose_claims = [c for c in claims if c.claim_type == ClaimType.DOSE]
        assert len(dose_claims) >= 1
        assert any("benzyl-penicillin" in c.text.lower() for c in dose_claims)

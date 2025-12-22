"""Tests for ALGORITHM_STEP claim extraction patterns.

Comprehensive tests for numbered/lettered step patterns in Danish medical procedures.
These patterns identify sequential procedural steps that form clinical algorithms.
Based on Phase 0 validation work with real procedure data.

Danish step patterns include:
- Numbered: "1. Sikr luftveje", "2. Giv ilt"
- Trin prefix: "Trin 1: Kontrollér bevidsthed"
- Lettered: "A) Etablér IV-adgang", "B) Monitorér"
- Ordinal: "Første: Kald efter hjælp", "Andet: Vurdér bevidsthed"
"""

import pytest

from procedurewriter.claims.extractor import ClaimExtractor
from procedurewriter.models.claims import Claim, ClaimType


@pytest.fixture
def extractor() -> ClaimExtractor:
    """Create extractor for tests."""
    return ClaimExtractor(run_id="algorithmstep-test")


class TestNumberedStepPatterns:
    """Tests for numbered step patterns (1. 2. 3. etc)."""

    def test_simple_numbered_step(self, extractor: ClaimExtractor) -> None:
        """Extracts '1. Action' pattern."""
        text = "1. Sikr frie luftveje"
        claims = extractor.extract(text)
        step_claims = [c for c in claims if c.claim_type == ClaimType.ALGORITHM_STEP]
        assert len(step_claims) >= 1
        assert any("1." in c.text for c in step_claims)

    def test_numbered_step_with_colon(self, extractor: ClaimExtractor) -> None:
        """Extracts '1: Action' pattern."""
        text = "1: Kontrollér bevidsthed"
        claims = extractor.extract(text)
        step_claims = [c for c in claims if c.claim_type == ClaimType.ALGORITHM_STEP]
        assert len(step_claims) >= 1

    def test_numbered_step_with_parenthesis(self, extractor: ClaimExtractor) -> None:
        """Extracts '1) Action' pattern."""
        text = "1) Giv 100% ilt via maske"
        claims = extractor.extract(text)
        step_claims = [c for c in claims if c.claim_type == ClaimType.ALGORITHM_STEP]
        assert len(step_claims) >= 1

    def test_double_digit_numbered_step(self, extractor: ClaimExtractor) -> None:
        """Extracts '10. Action' pattern."""
        text = "10. Dokumentér behandlingen i journal"
        claims = extractor.extract(text)
        step_claims = [c for c in claims if c.claim_type == ClaimType.ALGORITHM_STEP]
        assert len(step_claims) >= 1

    def test_multiple_numbered_steps(self, extractor: ClaimExtractor) -> None:
        """Extracts multiple sequential numbered steps."""
        text = """1. Sikr frie luftveje
2. Giv ilt
3. Etablér IV-adgang
4. Tag blodprøver"""
        claims = extractor.extract(text)
        step_claims = [c for c in claims if c.claim_type == ClaimType.ALGORITHM_STEP]
        assert len(step_claims) >= 4


class TestTrinPrefixPatterns:
    """Tests for 'Trin X:' (Step X:) patterns."""

    def test_trin_with_number(self, extractor: ClaimExtractor) -> None:
        """Extracts 'Trin 1:' pattern."""
        text = "Trin 1: Kontrollér bevidsthed og respiration"
        claims = extractor.extract(text)
        step_claims = [c for c in claims if c.claim_type == ClaimType.ALGORITHM_STEP]
        assert len(step_claims) >= 1
        assert any("trin" in c.text.lower() for c in step_claims)

    def test_trin_without_colon(self, extractor: ClaimExtractor) -> None:
        """Extracts 'Trin 1' (without colon) pattern."""
        text = "Trin 1 Vurdér patientens tilstand"
        claims = extractor.extract(text)
        step_claims = [c for c in claims if c.claim_type == ClaimType.ALGORITHM_STEP]
        assert len(step_claims) >= 1

    def test_trin_uppercase(self, extractor: ClaimExtractor) -> None:
        """Extracts 'TRIN 1:' uppercase pattern."""
        text = "TRIN 1: Start HLR"
        claims = extractor.extract(text)
        step_claims = [c for c in claims if c.claim_type == ClaimType.ALGORITHM_STEP]
        assert len(step_claims) >= 1


class TestLetteredStepPatterns:
    """Tests for lettered step patterns (A. B. C. or a) b) c) etc)."""

    def test_uppercase_letter_period(self, extractor: ClaimExtractor) -> None:
        """Extracts 'A. Action' pattern."""
        text = "A. Etablér IV-adgang"
        claims = extractor.extract(text)
        step_claims = [c for c in claims if c.claim_type == ClaimType.ALGORITHM_STEP]
        assert len(step_claims) >= 1

    def test_uppercase_letter_parenthesis(self, extractor: ClaimExtractor) -> None:
        """Extracts 'A) Action' pattern."""
        text = "A) Giv adrenalin 1 mg IV"
        claims = extractor.extract(text)
        step_claims = [c for c in claims if c.claim_type == ClaimType.ALGORITHM_STEP]
        assert len(step_claims) >= 1

    def test_lowercase_letter_period(self, extractor: ClaimExtractor) -> None:
        """Extracts 'a. Action' pattern."""
        text = "a. Monitorering påbegyndes"
        claims = extractor.extract(text)
        step_claims = [c for c in claims if c.claim_type == ClaimType.ALGORITHM_STEP]
        assert len(step_claims) >= 1

    def test_lowercase_letter_parenthesis(self, extractor: ClaimExtractor) -> None:
        """Extracts 'a) Action' pattern."""
        text = "a) Kontrollér puls"
        claims = extractor.extract(text)
        step_claims = [c for c in claims if c.claim_type == ClaimType.ALGORITHM_STEP]
        assert len(step_claims) >= 1

    def test_multiple_lettered_steps(self, extractor: ClaimExtractor) -> None:
        """Extracts multiple sequential lettered steps."""
        text = """A. Airway - Sikr luftveje
B. Breathing - Giv ilt
C. Circulation - Etablér adgang
D. Disability - Vurdér bevidsthed"""
        claims = extractor.extract(text)
        step_claims = [c for c in claims if c.claim_type == ClaimType.ALGORITHM_STEP]
        assert len(step_claims) >= 4


class TestOrdinalPatterns:
    """Tests for Danish ordinal patterns (Første, Andet, Tredje, etc.)."""

    def test_forste(self, extractor: ClaimExtractor) -> None:
        """Extracts 'Første:' pattern."""
        text = "Første: Kald efter hjælp"
        claims = extractor.extract(text)
        step_claims = [c for c in claims if c.claim_type == ClaimType.ALGORITHM_STEP]
        assert len(step_claims) >= 1

    def test_andet(self, extractor: ClaimExtractor) -> None:
        """Extracts 'Andet:' pattern."""
        text = "Andet: Vurdér bevidsthed"
        claims = extractor.extract(text)
        step_claims = [c for c in claims if c.claim_type == ClaimType.ALGORITHM_STEP]
        assert len(step_claims) >= 1

    def test_tredje(self, extractor: ClaimExtractor) -> None:
        """Extracts 'Tredje:' pattern."""
        text = "Tredje: Påbegynd kompressioner"
        claims = extractor.extract(text)
        step_claims = [c for c in claims if c.claim_type == ClaimType.ALGORITHM_STEP]
        assert len(step_claims) >= 1

    def test_fjerde(self, extractor: ClaimExtractor) -> None:
        """Extracts 'Fjerde:' pattern."""
        text = "Fjerde: Giv adrenalin"
        claims = extractor.extract(text)
        step_claims = [c for c in claims if c.claim_type == ClaimType.ALGORITHM_STEP]
        assert len(step_claims) >= 1


class TestFasePatterns:
    """Tests for 'Fase X:' (Phase X:) patterns."""

    def test_fase_with_number(self, extractor: ClaimExtractor) -> None:
        """Extracts 'Fase 1:' pattern."""
        text = "Fase 1: Initial stabilisering"
        claims = extractor.extract(text)
        step_claims = [c for c in claims if c.claim_type == ClaimType.ALGORITHM_STEP]
        assert len(step_claims) >= 1

    def test_fase_uppercase(self, extractor: ClaimExtractor) -> None:
        """Extracts 'FASE 2:' uppercase pattern."""
        text = "FASE 2: Definitiv behandling"
        claims = extractor.extract(text)
        step_claims = [c for c in claims if c.claim_type == ClaimType.ALGORITHM_STEP]
        assert len(step_claims) >= 1


class TestDelPatterns:
    """Tests for 'Del X:' (Part X:) patterns."""

    def test_del_with_number(self, extractor: ClaimExtractor) -> None:
        """Extracts 'Del 1:' pattern."""
        text = "Del 1: Primær vurdering"
        claims = extractor.extract(text)
        step_claims = [c for c in claims if c.claim_type == ClaimType.ALGORITHM_STEP]
        assert len(step_claims) >= 1

    def test_del_uppercase(self, extractor: ClaimExtractor) -> None:
        """Extracts 'DEL 2:' uppercase pattern."""
        text = "DEL 2: Sekundær vurdering"
        claims = extractor.extract(text)
        step_claims = [c for c in claims if c.claim_type == ClaimType.ALGORITHM_STEP]
        assert len(step_claims) >= 1


class TestEdgeCases:
    """Tests for edge cases and special patterns."""

    def test_empty_text(self, extractor: ClaimExtractor) -> None:
        """Returns empty list for empty text."""
        claims = extractor.extract("")
        assert claims == []

    def test_no_steps(self, extractor: ClaimExtractor) -> None:
        """Returns no steps for text without step patterns."""
        text = "Denne patient har pneumoni og behandles med antibiotika."
        claims = extractor.extract(text)
        step_claims = [c for c in claims if c.claim_type == ClaimType.ALGORITHM_STEP]
        assert len(step_claims) == 0

    def test_with_source_reference(self, extractor: ClaimExtractor) -> None:
        """Extracts step with source reference."""
        text = "1. Giv adrenalin 0.5 mg IM [SRC001]"
        claims = extractor.extract(text)
        step_claims = [c for c in claims if c.claim_type == ClaimType.ALGORITHM_STEP]
        assert len(step_claims) >= 1
        assert any(c.source_refs for c in step_claims)

    def test_step_with_line_number(self, extractor: ClaimExtractor) -> None:
        """Correctly tracks line numbers."""
        text = "Introduktion\nBaggrund\n1. Første trin"
        claims = extractor.extract(text)
        step_claims = [c for c in claims if c.claim_type == ClaimType.ALGORITHM_STEP]
        assert len(step_claims) >= 1
        assert step_claims[0].line_number == 3

    def test_markdown_header_ignored(self, extractor: ClaimExtractor) -> None:
        """Skips markdown headers that might look like steps."""
        text = "# 1. Overskrift\n1. Første trin"
        claims = extractor.extract(text)
        step_claims = [c for c in claims if c.claim_type == ClaimType.ALGORITHM_STEP]
        # Should only find the one on line 2, not the header
        assert len(step_claims) >= 1
        assert all(c.line_number != 1 for c in step_claims)

    def test_confidence_higher_with_source(self, extractor: ClaimExtractor) -> None:
        """Confidence is higher when source reference present."""
        text_with_source = "1. Trin et [SRC001]"
        text_without_source = "1. Trin et"

        claims_with = extractor.extract(text_with_source)
        claims_without = extractor.extract(text_without_source)

        step_with = [c for c in claims_with if c.claim_type == ClaimType.ALGORITHM_STEP]
        step_without = [c for c in claims_without if c.claim_type == ClaimType.ALGORITHM_STEP]

        if step_with and step_without:
            assert step_with[0].confidence > step_without[0].confidence

    def test_step_number_not_in_middle_of_sentence(self, extractor: ClaimExtractor) -> None:
        """Avoids false positives from numbers in middle of sentence."""
        # This should NOT match as a step (number in middle of text)
        text = "Giv mellem 2 og 4 liter ilt"
        claims = extractor.extract(text)
        step_claims = [c for c in claims if c.claim_type == ClaimType.ALGORITHM_STEP]
        # May have 0 claims if pattern is properly at start-of-line
        # This tests that we don't over-match
        for claim in step_claims:
            # If we do match, it should not be "2 og 4"
            assert "2 og 4" not in claim.text


class TestRealWorldExamples:
    """Tests based on real Danish medical procedure text."""

    def test_hlr_algorithm(self, extractor: ClaimExtractor) -> None:
        """Real example from CPR algorithm."""
        text = """1. Kontrollér bevidsthed
2. Tilkald hjælp
3. Åbn luftveje
4. Kontrollér respiration
5. Start kompressioner 30:2"""
        claims = extractor.extract(text)
        step_claims = [c for c in claims if c.claim_type == ClaimType.ALGORITHM_STEP]
        assert len(step_claims) >= 5

    def test_abcde_algorithm(self, extractor: ClaimExtractor) -> None:
        """Real example from ABCDE assessment."""
        text = """A. Airway - Sikr frie luftveje med kæbeløft
B. Breathing - Giv 15L O2 via reservoirmaske
C. Circulation - Anlæg 2 grove IV-adgange
D. Disability - Vurdér GCS og pupiller
E. Exposure - Fjern tøj og mål temperatur"""
        claims = extractor.extract(text)
        step_claims = [c for c in claims if c.claim_type == ClaimType.ALGORITHM_STEP]
        assert len(step_claims) >= 5

    def test_anaphylaxis_treatment_steps(self, extractor: ClaimExtractor) -> None:
        """Real example from anaphylaxis guideline."""
        text = """Trin 1: Fjern allergenet hvis muligt
Trin 2: Kald efter hjælp (anæstesi/akutteam)
Trin 3: Giv adrenalin 0.5 mg IM (lår)
Trin 4: Etablér IV-adgang
Trin 5: Giv væske (krystalloid 500-1000 ml)"""
        claims = extractor.extract(text)
        step_claims = [c for c in claims if c.claim_type == ClaimType.ALGORITHM_STEP]
        assert len(step_claims) >= 5

    def test_sepsis_bundle(self, extractor: ClaimExtractor) -> None:
        """Real example from sepsis hour-1 bundle."""
        text = """Første: Mål laktat
Andet: Tag blodkulturer før antibiotika
Tredje: Giv bredspektret antibiotika
Fjerde: Start væskeresuscitation ved hypotension"""
        claims = extractor.extract(text)
        step_claims = [c for c in claims if c.claim_type == ClaimType.ALGORITHM_STEP]
        assert len(step_claims) >= 4

    def test_trauma_phases(self, extractor: ClaimExtractor) -> None:
        """Real example from trauma management."""
        text = """Fase 1: Primær survey med ABCDE
Fase 2: Resuscitation og stabilisering
Fase 3: Sekundær survey med fuld undersøgelse
Fase 4: Definitiv behandling"""
        claims = extractor.extract(text)
        step_claims = [c for c in claims if c.claim_type == ClaimType.ALGORITHM_STEP]
        assert len(step_claims) >= 4

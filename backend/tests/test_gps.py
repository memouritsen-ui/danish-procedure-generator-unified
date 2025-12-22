"""Tests for GPS (Good Practice Statement) classification.

Per GRADE methodology, GPS are statements that should be UNGRADED because
evidence review would be "poor use of time" - e.g., "Assess the patient's airway."

The core criterion is the "inverse test": if the opposite sounds absurd, it's a GPS.
"""
from __future__ import annotations

import pytest

from procedurewriter.pipeline.gps import (
    SentenceType,
    classify_sentence_type,
    passes_inverse_test,
    GPS_VERB_PATTERNS,
    NON_GPS_PATTERNS,
)


class TestSentenceTypeEnum:
    """P6-001: Test SentenceType enum."""

    def test_sentence_type_has_gps(self) -> None:
        assert SentenceType.GPS.value == "gps"

    def test_sentence_type_has_therapeutic(self) -> None:
        assert SentenceType.THERAPEUTIC.value == "therapeutic"

    def test_sentence_type_has_prognostic(self) -> None:
        assert SentenceType.PROGNOSTIC.value == "prognostic"

    def test_sentence_type_has_diagnostic(self) -> None:
        assert SentenceType.DIAGNOSTIC.value == "diagnostic"

    def test_sentence_type_has_procedural(self) -> None:
        assert SentenceType.PROCEDURAL.value == "procedural"

    def test_all_types_are_strings(self) -> None:
        for t in SentenceType:
            assert isinstance(t.value, str)


class TestClassifyGPS:
    """P6-002: Test GPS classifier function."""

    # GPS sentences (should be exempt from evidence)
    @pytest.mark.parametrize("sentence", [
        "Vurder patientens luftveje, vejrtrækning og cirkulation.",
        "Tjek vitale parametre hvert 5. minut.",
        "Observer patienten for tegn på forværring.",
        "Mål saturation kontinuerligt.",
        "Kontroller blodtryk og puls.",
        "Dokumenter alle observationer.",
        "Kommuniker med patienten om behandlingsplanen.",
        "Sikr frie luftveje.",
        "Overvåg patientens bevidsthedsniveau.",
        "Informer patienten om proceduren.",
        "Henvis til specialist ved behov.",
    ])
    def test_classify_gps_sentences(self, sentence: str) -> None:
        result = classify_sentence_type(sentence)
        assert result == SentenceType.GPS, f"Expected GPS for: {sentence}"

    # Therapeutic sentences (require evidence - drug dosages)
    @pytest.mark.parametrize("sentence", [
        "Giv adrenalin 0,3 mg intramuskulært ved anafylaksi.",
        "Administrer salbutamol 2,5-5 mg via forstøver.",
        "Giv prednisolon 37,5-50 mg peroralt.",
        "Indgiv hydrocortison 200 mg intravenøst.",
        "Giv morfin 2,5-5 mg intravenøst ved smerter.",
        "Administrer 500 ml NaCl 0,9% over 30 minutter.",
        "Giv magnesiumsulfat 2 g intravenøst.",
    ])
    def test_classify_therapeutic_sentences(self, sentence: str) -> None:
        result = classify_sentence_type(sentence)
        assert result == SentenceType.THERAPEUTIC, f"Expected THERAPEUTIC for: {sentence}"

    # Prognostic sentences (require evidence - outcome claims)
    @pytest.mark.parametrize("sentence", [
        "Mortaliteten reduceres med 50% ved tidlig intervention.",
        "Overlevelsen er 95% ved korrekt behandling.",
        "Risikoen for komplikationer er under 5%.",
        "Prognosen er god ved hurtig indsats.",
    ])
    def test_classify_prognostic_sentences(self, sentence: str) -> None:
        result = classify_sentence_type(sentence)
        assert result == SentenceType.PROGNOSTIC, f"Expected PROGNOSTIC for: {sentence}"

    # Diagnostic sentences (require evidence - threshold claims)
    @pytest.mark.parametrize("sentence", [
        "Diagnosen stilles ved SpO2 under 92%.",
        "Peak flow under 50% af forventet indikerer svær astma.",
        "Pulsoximetri under 90% kræver iltbehandling.",
    ])
    def test_classify_diagnostic_sentences(self, sentence: str) -> None:
        result = classify_sentence_type(sentence)
        assert result == SentenceType.DIAGNOSTIC, f"Expected DIAGNOSTIC for: {sentence}"

    def test_empty_string_returns_procedural(self) -> None:
        result = classify_sentence_type("")
        assert result == SentenceType.PROCEDURAL

    def test_whitespace_only_returns_procedural(self) -> None:
        result = classify_sentence_type("   ")
        assert result == SentenceType.PROCEDURAL


class TestInverseTest:
    """P6-006: Test the inverse test function."""

    # GPS - inverse sounds absurd
    @pytest.mark.parametrize("sentence", [
        "Vurder patientens luftveje",
        "Tjek vitale parametre",
        "Observer for tegn på forværring",
        "Dokumenter behandlingen",
        "Kommuniker med patienten",
        "Sikr frie luftveje",
    ])
    def test_gps_passes_inverse_test(self, sentence: str) -> None:
        assert passes_inverse_test(sentence) is True, f"GPS should pass inverse test: {sentence}"

    # Therapeutic - inverse is valid (could give different dose)
    @pytest.mark.parametrize("sentence", [
        "Giv adrenalin 0,3 mg",
        "Administrer salbutamol 5 mg",
        "Giv prednisolon 50 mg",
    ])
    def test_therapeutic_fails_inverse_test(self, sentence: str) -> None:
        assert passes_inverse_test(sentence) is False, f"Therapeutic should fail inverse test: {sentence}"

    def test_empty_string_fails_inverse_test(self) -> None:
        assert passes_inverse_test("") is False


class TestPatternConstants:
    """Test that pattern constants are properly defined."""

    def test_gps_verb_patterns_exist(self) -> None:
        assert len(GPS_VERB_PATTERNS) > 0
        for pattern in GPS_VERB_PATTERNS:
            assert isinstance(pattern, str)

    def test_non_gps_patterns_exist(self) -> None:
        assert len(NON_GPS_PATTERNS) > 0
        for pattern in NON_GPS_PATTERNS:
            assert isinstance(pattern, str)


class TestEdgeCases:
    """Test edge cases and mixed content."""

    def test_sentence_with_both_gps_verb_and_dosage_is_therapeutic(self) -> None:
        # If a sentence has a GPS verb but also a dosage, it's therapeutic
        sentence = "Giv adrenalin 0,3 mg og observer patienten."
        result = classify_sentence_type(sentence)
        assert result == SentenceType.THERAPEUTIC

    def test_sentence_with_citation_stripped(self) -> None:
        # Citations should be stripped before classification
        sentence = "Vurder patientens luftveje. [S:SRC0001]"
        result = classify_sentence_type(sentence)
        assert result == SentenceType.GPS

    def test_case_insensitive_classification(self) -> None:
        # Should work regardless of case
        sentence = "VURDER patientens luftveje"
        result = classify_sentence_type(sentence)
        assert result == SentenceType.GPS

    def test_sentence_with_numbers_but_no_units_may_be_gps(self) -> None:
        # Numbers without medical units might still be GPS
        sentence = "Tjek vitale parametre hvert 5 minut."
        result = classify_sentence_type(sentence)
        assert result == SentenceType.GPS


class TestMetaAnalysisSectionGPS:
    """P6-META: Test GPS classification for meta-analysis section statements.

    Meta-analysis sections contain self-referential statements about the
    evidence synthesis methodology. These describe THIS document's process,
    not external evidence, and are inherently non-citable.
    """

    @pytest.mark.parametrize("sentence", [
        # Self-referential evidence methodology statements
        "Evidensen baseres på 15 systematiske reviews og 23 randomiserede kontrollerede studier.",
        "Formel meta-analyse kunne ikke gennemføres grundet heterogenitet.",
        "Samlet inkluderer evidensgrundlaget 38 studier.",
        "Den samlede evidens vurderes som moderat til høj kvalitet.",
        # Study synthesis statements
        "Systematiske reviews fra Cochrane og NICE danner grundlag for anbefalingerne.",
        "Meta-analysen viser en samlet effekt på...",
        "Studiekvaliteten blev vurderet med GRADE-metoden.",
    ])
    def test_meta_analysis_statements_are_gps(self, sentence: str) -> None:
        """Meta-analysis methodology statements should be GPS (self-referential, non-citable)."""
        result = classify_sentence_type(sentence)
        assert result == SentenceType.GPS, f"Expected GPS for meta-analysis statement: {sentence}"

    @pytest.mark.parametrize("sentence", [
        "Evidensen baseres på 15 systematiske reviews.",
        "Formel meta-analyse kunne ikke gennemføres.",
    ])
    def test_meta_analysis_passes_inverse_test(self, sentence: str) -> None:
        """Meta-analysis statements should pass inverse test (negation is absurd)."""
        # "Evidensen baseres IKKE på systematiske reviews" - absurd for a procedure document
        assert passes_inverse_test(sentence) is True


class TestFragmentDetectionGPS:
    """P6-FRAG: Test GPS classification for sentence fragments.

    Fragments are incomplete sentences resulting from text extraction or
    sentence splitting. They cannot be evidence-supported because they're
    not complete claims.
    """

    @pytest.mark.parametrize("sentence", [
        # Very short fragments
        "B3)",
        "amb.",
        "kons.",
        "A1)",
        # Continuation fragments (start lowercase)
        "at afklare øjeblikkeligt behandlingsbehov",
        "og sikre sufficient analgesi",
        "samt forebygge komplikationer",
        # Parenthetical references only
        "(se afsnit 3)",
        "(jf. bilag A)",
    ])
    def test_fragments_are_gps(self, sentence: str) -> None:
        """Sentence fragments should be classified as GPS (cannot have evidence)."""
        result = classify_sentence_type(sentence)
        assert result == SentenceType.GPS, f"Expected GPS for fragment: {sentence}"

    def test_short_but_complete_sentence_not_fragment(self) -> None:
        """Short but complete sentences with verbs are NOT fragments."""
        # "Stands up" is short but complete - should NOT be auto-GPS
        sentence = "Vurder patienten."  # Short but has verb + object
        result = classify_sentence_type(sentence)
        assert result == SentenceType.GPS  # GPS because of verb, not fragment

    def test_fragment_with_dosage_still_fragments(self) -> None:
        """Fragments with dosage markers are still fragments if incomplete."""
        # Edge case: fragment that happens to contain a number
        sentence = "5 mg)"
        result = classify_sentence_type(sentence)
        # This should be GPS (fragment) not THERAPEUTIC
        # Because it's clearly incomplete - just a dose reference
        assert result == SentenceType.GPS, "Incomplete fragment with dose should still be GPS"


class TestMetaAnalysisFalsePositives:
    """Ensure meta-analysis patterns don't over-classify."""

    @pytest.mark.parametrize("sentence", [
        # These contain similar words but ARE actual claims needing evidence
        "Studiet viste at mortaliteten reduceres med 30%.",
        "En meta-analyse konkluderede at dosis på 5 mg er optimal.",
        "Systematiske reviews anbefaler adrenalin 0,3 mg.",
    ])
    def test_claims_with_meta_keywords_still_require_evidence(self, sentence: str) -> None:
        """Sentences with meta-analysis keywords but containing claims still need evidence."""
        result = classify_sentence_type(sentence)
        # These should NOT be GPS because they contain dosages or outcome claims
        assert result != SentenceType.GPS, f"Should NOT be GPS (has claim): {sentence}"

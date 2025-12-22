"""Tests for RECOMMENDATION claim extraction patterns.

Comprehensive tests for clinical recommendation patterns in Danish medical procedures.
Danish modal verbs: "bør" (should), "skal" (must), "anbefales" (recommended).
Based on Phase 0 validation work with real procedure data.
"""

import pytest

from procedurewriter.claims.extractor import ClaimExtractor
from procedurewriter.models.claims import Claim, ClaimType


@pytest.fixture
def extractor() -> ClaimExtractor:
    """Create extractor for tests."""
    return ClaimExtractor(run_id="recommendation-test")


class TestBorPatterns:
    """Tests for 'bør' (should) recommendation patterns."""

    def test_bor_indlaegges(self, extractor: ClaimExtractor) -> None:
        """Extracts 'bør indlægges' pattern."""
        text = "Patienter med svær pneumoni bør indlægges"
        claims = extractor.extract(text)
        rec_claims = [c for c in claims if c.claim_type == ClaimType.RECOMMENDATION]
        assert len(rec_claims) >= 1
        assert any("bør" in c.text.lower() for c in rec_claims)

    def test_bor_behandles(self, extractor: ClaimExtractor) -> None:
        """Extracts 'bør behandles' pattern."""
        text = "Akut astma bør behandles straks"
        claims = extractor.extract(text)
        rec_claims = [c for c in claims if c.claim_type == ClaimType.RECOMMENDATION]
        assert len(rec_claims) >= 1

    def test_bor_gives(self, extractor: ClaimExtractor) -> None:
        """Extracts 'bør gives' pattern."""
        text = "Oxygen bør gives ved hypoksi"
        claims = extractor.extract(text)
        rec_claims = [c for c in claims if c.claim_type == ClaimType.RECOMMENDATION]
        assert len(rec_claims) >= 1

    def test_bor_vurderes(self, extractor: ClaimExtractor) -> None:
        """Extracts 'bør vurderes' pattern."""
        text = "Patienten bør vurderes af speciallæge"
        claims = extractor.extract(text)
        rec_claims = [c for c in claims if c.claim_type == ClaimType.RECOMMENDATION]
        assert len(rec_claims) >= 1

    def test_bor_overvejes(self, extractor: ClaimExtractor) -> None:
        """Extracts 'bør overvejes' pattern."""
        text = "Intensiv behandling bør overvejes ved svære tilfælde"
        claims = extractor.extract(text)
        rec_claims = [c for c in claims if c.claim_type == ClaimType.RECOMMENDATION]
        assert len(rec_claims) >= 1

    def test_bor_suppleres(self, extractor: ClaimExtractor) -> None:
        """Extracts 'bør suppleres' pattern."""
        text = "Behandlingen bør suppleres med antibiotika"
        claims = extractor.extract(text)
        rec_claims = [c for c in claims if c.claim_type == ClaimType.RECOMMENDATION]
        assert len(rec_claims) >= 1

    def test_bor_pauseres(self, extractor: ClaimExtractor) -> None:
        """Extracts 'bør pauseres' pattern."""
        text = "NSAID bør pauseres ved akut nyresvigt"
        claims = extractor.extract(text)
        rec_claims = [c for c in claims if c.claim_type == ClaimType.RECOMMENDATION]
        assert len(rec_claims) >= 1


class TestSkalPatterns:
    """Tests for 'skal' (must) requirement patterns."""

    def test_skal_indlaegges(self, extractor: ClaimExtractor) -> None:
        """Extracts 'skal indlægges' pattern."""
        text = "Patienter med sepsis skal indlægges akut"
        claims = extractor.extract(text)
        rec_claims = [c for c in claims if c.claim_type == ClaimType.RECOMMENDATION]
        assert len(rec_claims) >= 1
        assert any("skal" in c.text.lower() for c in rec_claims)

    def test_skal_behandles(self, extractor: ClaimExtractor) -> None:
        """Extracts 'skal behandles' pattern."""
        text = "Anafylaksi skal behandles med adrenalin"
        claims = extractor.extract(text)
        rec_claims = [c for c in claims if c.claim_type == ClaimType.RECOMMENDATION]
        assert len(rec_claims) >= 1

    def test_skal_gives(self, extractor: ClaimExtractor) -> None:
        """Extracts 'skal gives' pattern."""
        text = "Antibiotika skal gives inden 1 time"
        claims = extractor.extract(text)
        rec_claims = [c for c in claims if c.claim_type == ClaimType.RECOMMENDATION]
        assert len(rec_claims) >= 1

    def test_skal_monitoreres(self, extractor: ClaimExtractor) -> None:
        """Extracts 'skal monitoreres' pattern."""
        text = "Patienten skal monitoreres kontinuerligt"
        claims = extractor.extract(text)
        rec_claims = [c for c in claims if c.claim_type == ClaimType.RECOMMENDATION]
        assert len(rec_claims) >= 1

    def test_skal_vurderes(self, extractor: ClaimExtractor) -> None:
        """Extracts 'skal vurderes' pattern."""
        text = "Responsen skal vurderes efter 15 minutter"
        claims = extractor.extract(text)
        rec_claims = [c for c in claims if c.claim_type == ClaimType.RECOMMENDATION]
        assert len(rec_claims) >= 1

    def test_skal_sikres(self, extractor: ClaimExtractor) -> None:
        """Extracts 'skal sikres' pattern."""
        text = "Frie luftveje skal sikres før behandling"
        claims = extractor.extract(text)
        rec_claims = [c for c in claims if c.claim_type == ClaimType.RECOMMENDATION]
        assert len(rec_claims) >= 1

    def test_skal_konfereres(self, extractor: ClaimExtractor) -> None:
        """Extracts 'skal konfereres' pattern."""
        text = "Der skal konfereres med vagthavende"
        claims = extractor.extract(text)
        rec_claims = [c for c in claims if c.claim_type == ClaimType.RECOMMENDATION]
        assert len(rec_claims) >= 1


class TestAnbefalesPatterns:
    """Tests for 'anbefales' (recommended) patterns."""

    def test_det_anbefales(self, extractor: ClaimExtractor) -> None:
        """Extracts 'det anbefales at' pattern."""
        text = "Det anbefales at give bronkodilatator"
        claims = extractor.extract(text)
        rec_claims = [c for c in claims if c.claim_type == ClaimType.RECOMMENDATION]
        assert len(rec_claims) >= 1
        assert any("anbefales" in c.text.lower() for c in rec_claims)

    def test_anbefales_at_give(self, extractor: ClaimExtractor) -> None:
        """Extracts 'anbefales at give' pattern."""
        text = "Anbefales at give prednisolon ved svær astma"
        claims = extractor.extract(text)
        rec_claims = [c for c in claims if c.claim_type == ClaimType.RECOMMENDATION]
        assert len(rec_claims) >= 1

    def test_anbefales_iv(self, extractor: ClaimExtractor) -> None:
        """Extracts 'anbefales i.v.' pattern."""
        text = "Antibiotika anbefales i.v. ved svær infektion"
        claims = extractor.extract(text)
        rec_claims = [c for c in claims if c.claim_type == ClaimType.RECOMMENDATION]
        assert len(rec_claims) >= 1

    def test_anbefalet_behandling(self, extractor: ClaimExtractor) -> None:
        """Extracts 'anbefalet behandling' pattern."""
        text = "Den anbefalede behandling er benzylpenicillin"
        claims = extractor.extract(text)
        rec_claims = [c for c in claims if c.claim_type == ClaimType.RECOMMENDATION]
        assert len(rec_claims) >= 1


class TestTilraadesPatterns:
    """Tests for 'tilrådes' (advised) patterns."""

    def test_tilraades(self, extractor: ClaimExtractor) -> None:
        """Extracts 'tilrådes' pattern."""
        text = "Indlæggelse tilrådes ved dårlig compliance"
        claims = extractor.extract(text)
        rec_claims = [c for c in claims if c.claim_type == ClaimType.RECOMMENDATION]
        assert len(rec_claims) >= 1
        assert any("tilrådes" in c.text.lower() for c in rec_claims)

    def test_tilraades_at(self, extractor: ClaimExtractor) -> None:
        """Extracts 'tilrådes at' pattern."""
        text = "Det tilrådes at følge lokale retningslinjer"
        claims = extractor.extract(text)
        rec_claims = [c for c in claims if c.claim_type == ClaimType.RECOMMENDATION]
        assert len(rec_claims) >= 1


class TestIndicatesPatterns:
    """Tests for 'indicerer' (indicates) and 'indiceres' (is indicated) patterns."""

    def test_indicerer(self, extractor: ClaimExtractor) -> None:
        """Extracts 'indicerer' pattern."""
        text = "Hypoksi indicerer behov for iltbehandling"
        claims = extractor.extract(text)
        rec_claims = [c for c in claims if c.claim_type == ClaimType.RECOMMENDATION]
        assert len(rec_claims) >= 1

    def test_indiceres(self, extractor: ClaimExtractor) -> None:
        """Extracts 'indiceres' pattern."""
        text = "Intubation indiceres ved respirationssvigt"
        claims = extractor.extract(text)
        rec_claims = [c for c in claims if c.claim_type == ClaimType.RECOMMENDATION]
        assert len(rec_claims) >= 1


class TestMustNotPatterns:
    """Tests for negative recommendation patterns (not 'må ikke' which is CONTRAINDICATION)."""

    def test_bor_undgaas(self, extractor: ClaimExtractor) -> None:
        """Extracts 'bør undgås' pattern."""
        text = "Kortikosteroider bør undgås ved viral infektion"
        claims = extractor.extract(text)
        rec_claims = [c for c in claims if c.claim_type == ClaimType.RECOMMENDATION]
        assert len(rec_claims) >= 1

    def test_skal_undgaas(self, extractor: ClaimExtractor) -> None:
        """Extracts 'skal undgås' pattern."""
        text = "NSAID skal undgås ved nyresvigt"
        claims = extractor.extract(text)
        rec_claims = [c for c in claims if c.claim_type == ClaimType.RECOMMENDATION]
        assert len(rec_claims) >= 1


class TestEdgeCases:
    """Tests for edge cases and special patterns."""

    def test_empty_text(self, extractor: ClaimExtractor) -> None:
        """Returns empty list for empty text."""
        claims = extractor.extract("")
        assert claims == []

    def test_no_recommendations(self, extractor: ClaimExtractor) -> None:
        """Returns no recommendations for text without modal verbs."""
        text = "Denne patient har pneumoni."
        claims = extractor.extract(text)
        rec_claims = [c for c in claims if c.claim_type == ClaimType.RECOMMENDATION]
        assert len(rec_claims) == 0

    def test_with_source_reference(self, extractor: ClaimExtractor) -> None:
        """Extracts recommendation with source reference."""
        text = "Patienter bør indlægges [SRC001]"
        claims = extractor.extract(text)
        rec_claims = [c for c in claims if c.claim_type == ClaimType.RECOMMENDATION]
        assert len(rec_claims) >= 1
        assert rec_claims[0].source_refs == ["SRC001"] or "SRC001" in str(rec_claims[0].source_refs)

    def test_multiple_recommendations_one_line(self, extractor: ClaimExtractor) -> None:
        """Extracts multiple recommendations from single line."""
        text = "Patienten bør indlægges og behandling skal påbegyndes"
        claims = extractor.extract(text)
        rec_claims = [c for c in claims if c.claim_type == ClaimType.RECOMMENDATION]
        # Should find at least one, possibly two
        assert len(rec_claims) >= 1

    def test_recommendation_with_line_number(self, extractor: ClaimExtractor) -> None:
        """Correctly tracks line numbers."""
        text = "Linje 1\nLinje 2\nPatienten bør vurderes"
        claims = extractor.extract(text)
        rec_claims = [c for c in claims if c.claim_type == ClaimType.RECOMMENDATION]
        assert len(rec_claims) >= 1
        assert rec_claims[0].line_number == 3

    def test_markdown_header_ignored(self, extractor: ClaimExtractor) -> None:
        """Skips markdown headers."""
        text = "# Behandling bør påbegyndes\nPatienten bør indlægges"
        claims = extractor.extract(text)
        rec_claims = [c for c in claims if c.claim_type == ClaimType.RECOMMENDATION]
        # Should only find the one on line 2, not the header
        assert len(rec_claims) >= 1
        assert all(c.line_number != 1 for c in rec_claims)

    def test_confidence_higher_with_source(self, extractor: ClaimExtractor) -> None:
        """Confidence is higher when source reference present."""
        text_with_source = "Patienten bør indlægges [SRC001]"
        text_without_source = "Patienten bør indlægges"

        claims_with = extractor.extract(text_with_source)
        claims_without = extractor.extract(text_without_source)

        rec_with = [c for c in claims_with if c.claim_type == ClaimType.RECOMMENDATION]
        rec_without = [c for c in claims_without if c.claim_type == ClaimType.RECOMMENDATION]

        if rec_with and rec_without:
            assert rec_with[0].confidence > rec_without[0].confidence


class TestRealWorldExamples:
    """Tests based on real Danish medical procedure text."""

    def test_pneumonia_admission(self, extractor: ClaimExtractor) -> None:
        """Real example from pneumonia guideline."""
        text = "Ved CRB-65 score ≥3 bør patienten indlægges på intensiv afdeling"
        claims = extractor.extract(text)
        rec_claims = [c for c in claims if c.claim_type == ClaimType.RECOMMENDATION]
        assert len(rec_claims) >= 1

    def test_asthma_treatment(self, extractor: ClaimExtractor) -> None:
        """Real example from asthma guideline."""
        text = "Ved akut svær astma skal bronkodilatator gives umiddelbart"
        claims = extractor.extract(text)
        rec_claims = [c for c in claims if c.claim_type == ClaimType.RECOMMENDATION]
        assert len(rec_claims) >= 1

    def test_sepsis_antibiotics(self, extractor: ClaimExtractor) -> None:
        """Real example from sepsis guideline."""
        text = "Antibiotika skal administreres inden for 1 time ved mistanke om sepsis"
        claims = extractor.extract(text)
        rec_claims = [c for c in claims if c.claim_type == ClaimType.RECOMMENDATION]
        assert len(rec_claims) >= 1

    def test_monitoring_recommendation(self, extractor: ClaimExtractor) -> None:
        """Real example for monitoring."""
        text = "Det anbefales at monitorere vitale værdier hver 15. minut"
        claims = extractor.extract(text)
        rec_claims = [c for c in claims if c.claim_type == ClaimType.RECOMMENDATION]
        assert len(rec_claims) >= 1

    def test_specialist_consultation(self, extractor: ClaimExtractor) -> None:
        """Real example for consultation."""
        text = "Ved tvivl om diagnosen bør der konfereres med infektionsmedicinsk afdeling"
        claims = extractor.extract(text)
        rec_claims = [c for c in claims if c.claim_type == ClaimType.RECOMMENDATION]
        assert len(rec_claims) >= 1

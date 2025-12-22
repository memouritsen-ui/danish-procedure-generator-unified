"""Tests for CONTRAINDICATION claim extraction patterns.

Comprehensive tests for clinical contraindication patterns in Danish medical procedures.
Danish patterns: "må ikke" (must not), "er kontraindiceret" (is contraindicated),
"kontraindikation" (contraindication), "bør ikke" (should not), "aldrig" (never).
Based on Phase 0 validation work with real procedure data.
"""

import pytest

from procedurewriter.claims.extractor import ClaimExtractor
from procedurewriter.models.claims import Claim, ClaimType


@pytest.fixture
def extractor() -> ClaimExtractor:
    """Create extractor for tests."""
    return ClaimExtractor(run_id="contraindication-test")


class TestMaaIkkePatterns:
    """Tests for 'må ikke' (must not) contraindication patterns."""

    def test_maa_ikke_gives(self, extractor: ClaimExtractor) -> None:
        """Extracts 'må ikke gives' pattern."""
        text = "Morfin må ikke gives ved respirationsdepression"
        claims = extractor.extract(text)
        contra_claims = [c for c in claims if c.claim_type == ClaimType.CONTRAINDICATION]
        assert len(contra_claims) >= 1
        assert any("må ikke" in c.text.lower() for c in contra_claims)

    def test_maa_ikke_anvendes(self, extractor: ClaimExtractor) -> None:
        """Extracts 'må ikke anvendes' pattern."""
        text = "NSAID må ikke anvendes ved nyresvigt"
        claims = extractor.extract(text)
        contra_claims = [c for c in claims if c.claim_type == ClaimType.CONTRAINDICATION]
        assert len(contra_claims) >= 1

    def test_maa_ikke_ordineres(self, extractor: ClaimExtractor) -> None:
        """Extracts 'må ikke ordineres' pattern."""
        text = "Metformin må ikke ordineres ved eGFR under 30"
        claims = extractor.extract(text)
        contra_claims = [c for c in claims if c.claim_type == ClaimType.CONTRAINDICATION]
        assert len(contra_claims) >= 1

    def test_maa_ikke_kombineres(self, extractor: ClaimExtractor) -> None:
        """Extracts 'må ikke kombineres' pattern."""
        text = "MAO-hæmmere må ikke kombineres med SSRI"
        claims = extractor.extract(text)
        contra_claims = [c for c in claims if c.claim_type == ClaimType.CONTRAINDICATION]
        assert len(contra_claims) >= 1

    def test_maa_ikke_administreres(self, extractor: ClaimExtractor) -> None:
        """Extracts 'må ikke administreres' pattern."""
        text = "Kalium må ikke administreres i.v. push"
        claims = extractor.extract(text)
        contra_claims = [c for c in claims if c.claim_type == ClaimType.CONTRAINDICATION]
        assert len(contra_claims) >= 1

    def test_maa_ikke_bruges(self, extractor: ClaimExtractor) -> None:
        """Extracts 'må ikke bruges' pattern."""
        text = "Denne behandling må ikke bruges hos gravide"
        claims = extractor.extract(text)
        contra_claims = [c for c in claims if c.claim_type == ClaimType.CONTRAINDICATION]
        assert len(contra_claims) >= 1

    def test_maa_ikke_with_intervening_word(self, extractor: ClaimExtractor) -> None:
        """Extracts 'må aldrig gives' pattern with intervening word."""
        text = "Morfin må aldrig gives uden monitorering"
        claims = extractor.extract(text)
        contra_claims = [c for c in claims if c.claim_type == ClaimType.CONTRAINDICATION]
        assert len(contra_claims) >= 1


class TestKontraindikeretPatterns:
    """Tests for 'kontraindiceret' (contraindicated) patterns."""

    def test_er_kontraindiceret(self, extractor: ClaimExtractor) -> None:
        """Extracts 'er kontraindiceret' pattern."""
        text = "Trombolyse er kontraindiceret ved aktiv blødning"
        claims = extractor.extract(text)
        contra_claims = [c for c in claims if c.claim_type == ClaimType.CONTRAINDICATION]
        assert len(contra_claims) >= 1
        assert any("kontraindiceret" in c.text.lower() for c in contra_claims)

    def test_kontraindiceret_ved(self, extractor: ClaimExtractor) -> None:
        """Extracts 'kontraindiceret ved' pattern."""
        text = "Behandlingen er kontraindiceret ved lever insufficiens"
        claims = extractor.extract(text)
        contra_claims = [c for c in claims if c.claim_type == ClaimType.CONTRAINDICATION]
        assert len(contra_claims) >= 1

    def test_kontraindiceret_hos(self, extractor: ClaimExtractor) -> None:
        """Extracts 'kontraindiceret hos' pattern."""
        text = "Warfarin er kontraindiceret hos gravide"
        claims = extractor.extract(text)
        contra_claims = [c for c in claims if c.claim_type == ClaimType.CONTRAINDICATION]
        assert len(contra_claims) >= 1

    def test_absolutt_kontraindiceret(self, extractor: ClaimExtractor) -> None:
        """Extracts 'absolut kontraindiceret' pattern."""
        text = "MR-scanning er absolut kontraindiceret ved pacemaker"
        claims = extractor.extract(text)
        contra_claims = [c for c in claims if c.claim_type == ClaimType.CONTRAINDICATION]
        assert len(contra_claims) >= 1

    def test_relativt_kontraindiceret(self, extractor: ClaimExtractor) -> None:
        """Extracts 'relativt kontraindiceret' pattern."""
        text = "Behandlingen er relativt kontraindiceret ved alder over 80"
        claims = extractor.extract(text)
        contra_claims = [c for c in claims if c.claim_type == ClaimType.CONTRAINDICATION]
        assert len(contra_claims) >= 1


class TestKontraindikationPatterns:
    """Tests for 'kontraindikation' (contraindication noun) patterns."""

    def test_kontraindikation_er(self, extractor: ClaimExtractor) -> None:
        """Extracts 'kontraindikation er' pattern."""
        text = "En kontraindikation er kendt allergi"
        claims = extractor.extract(text)
        contra_claims = [c for c in claims if c.claim_type == ClaimType.CONTRAINDICATION]
        assert len(contra_claims) >= 1
        assert any("kontraindikation" in c.text.lower() for c in contra_claims)

    def test_absolut_kontraindikation(self, extractor: ClaimExtractor) -> None:
        """Extracts 'absolut kontraindikation' pattern."""
        text = "Allergi overfor penicillin er en absolut kontraindikation"
        claims = extractor.extract(text)
        contra_claims = [c for c in claims if c.claim_type == ClaimType.CONTRAINDICATION]
        assert len(contra_claims) >= 1

    def test_relativ_kontraindikation(self, extractor: ClaimExtractor) -> None:
        """Extracts 'relativ kontraindikation' pattern."""
        text = "Høj alder er en relativ kontraindikation"
        claims = extractor.extract(text)
        contra_claims = [c for c in claims if c.claim_type == ClaimType.CONTRAINDICATION]
        assert len(contra_claims) >= 1

    def test_kontraindikationer_inkluderer(self, extractor: ClaimExtractor) -> None:
        """Extracts 'kontraindikationer inkluderer' pattern."""
        text = "Kontraindikationer inkluderer graviditet og amning"
        claims = extractor.extract(text)
        contra_claims = [c for c in claims if c.claim_type == ClaimType.CONTRAINDICATION]
        assert len(contra_claims) >= 1


class TestBorIkkePatterns:
    """Tests for 'bør ikke' (should not) weaker contraindication patterns."""

    def test_bor_ikke_gives(self, extractor: ClaimExtractor) -> None:
        """Extracts 'bør ikke gives' pattern."""
        text = "Opiater bør ikke gives til ældre uden dosisreduktion"
        claims = extractor.extract(text)
        contra_claims = [c for c in claims if c.claim_type == ClaimType.CONTRAINDICATION]
        assert len(contra_claims) >= 1
        assert any("bør ikke" in c.text.lower() for c in contra_claims)

    def test_bor_ikke_anvendes(self, extractor: ClaimExtractor) -> None:
        """Extracts 'bør ikke anvendes' pattern."""
        text = "Kortikosteroider bør ikke anvendes ved viral infektion"
        claims = extractor.extract(text)
        contra_claims = [c for c in claims if c.claim_type == ClaimType.CONTRAINDICATION]
        assert len(contra_claims) >= 1

    def test_bor_ikke_kombineres(self, extractor: ClaimExtractor) -> None:
        """Extracts 'bør ikke kombineres' pattern."""
        text = "ACE-hæmmere bør ikke kombineres med kaliumtilskud"
        claims = extractor.extract(text)
        contra_claims = [c for c in claims if c.claim_type == ClaimType.CONTRAINDICATION]
        assert len(contra_claims) >= 1


class TestSkalIkkePatterns:
    """Tests for 'skal ikke' (shall not) contraindication patterns."""

    def test_skal_ikke_gives(self, extractor: ClaimExtractor) -> None:
        """Extracts 'skal ikke gives' pattern."""
        text = "Adrenalin skal ikke gives subkutant ved anafylaksi"
        claims = extractor.extract(text)
        contra_claims = [c for c in claims if c.claim_type == ClaimType.CONTRAINDICATION]
        assert len(contra_claims) >= 1
        assert any("skal ikke" in c.text.lower() for c in contra_claims)

    def test_skal_ikke_anvendes(self, extractor: ClaimExtractor) -> None:
        """Extracts 'skal ikke anvendes' pattern."""
        text = "Denne dosis skal ikke anvendes ved børn"
        claims = extractor.extract(text)
        contra_claims = [c for c in claims if c.claim_type == ClaimType.CONTRAINDICATION]
        assert len(contra_claims) >= 1


class TestAldrigPatterns:
    """Tests for 'aldrig' (never) contraindication patterns."""

    def test_aldrig_give(self, extractor: ClaimExtractor) -> None:
        """Extracts 'aldrig give' pattern."""
        text = "Aldrig give kalium i.v. uden overvågning"
        claims = extractor.extract(text)
        contra_claims = [c for c in claims if c.claim_type == ClaimType.CONTRAINDICATION]
        assert len(contra_claims) >= 1
        assert any("aldrig" in c.text.lower() for c in contra_claims)

    def test_giv_aldrig(self, extractor: ClaimExtractor) -> None:
        """Extracts 'giv aldrig' pattern."""
        text = "Giv aldrig bikarbonat uden blodgasanalyse"
        claims = extractor.extract(text)
        contra_claims = [c for c in claims if c.claim_type == ClaimType.CONTRAINDICATION]
        assert len(contra_claims) >= 1

    def test_aldrig_anvend(self, extractor: ClaimExtractor) -> None:
        """Extracts 'aldrig anvend' pattern."""
        text = "Aldrig anvend denne behandling uden specialistvurdering"
        claims = extractor.extract(text)
        contra_claims = [c for c in claims if c.claim_type == ClaimType.CONTRAINDICATION]
        assert len(contra_claims) >= 1


class TestUndgaaPatterns:
    """Tests for 'undgå' (avoid) contraindication patterns."""

    def test_undgaa(self, extractor: ClaimExtractor) -> None:
        """Extracts 'undgå' imperative pattern."""
        text = "Undgå brug af NSAID ved nyresygdom"
        claims = extractor.extract(text)
        contra_claims = [c for c in claims if c.claim_type == ClaimType.CONTRAINDICATION]
        assert len(contra_claims) >= 1
        assert any("undgå" in c.text.lower() for c in contra_claims)

    def test_boer_undgaas(self, extractor: ClaimExtractor) -> None:
        """Extracts 'bør undgås' pattern - note: this may also be RECOMMENDATION."""
        text = "Langvarig behandling bør undgås"
        claims = extractor.extract(text)
        # Either CONTRAINDICATION or RECOMMENDATION is acceptable
        relevant = [c for c in claims if c.claim_type in (ClaimType.CONTRAINDICATION, ClaimType.RECOMMENDATION)]
        assert len(relevant) >= 1


class TestEdgeCases:
    """Tests for edge cases and special patterns."""

    def test_empty_text(self, extractor: ClaimExtractor) -> None:
        """Returns empty list for empty text."""
        claims = extractor.extract("")
        assert claims == []

    def test_no_contraindications(self, extractor: ClaimExtractor) -> None:
        """Returns no contraindications for text without patterns."""
        text = "Denne patient har pneumoni."
        claims = extractor.extract(text)
        contra_claims = [c for c in claims if c.claim_type == ClaimType.CONTRAINDICATION]
        assert len(contra_claims) == 0

    def test_with_source_reference(self, extractor: ClaimExtractor) -> None:
        """Extracts contraindication with source reference."""
        text = "Morfin må ikke gives ved respirationsdepression [SRC001]"
        claims = extractor.extract(text)
        contra_claims = [c for c in claims if c.claim_type == ClaimType.CONTRAINDICATION]
        assert len(contra_claims) >= 1
        # Source refs should be captured
        assert any(c.source_refs for c in contra_claims)

    def test_contraindication_with_line_number(self, extractor: ClaimExtractor) -> None:
        """Correctly tracks line numbers."""
        text = "Linje 1\nLinje 2\nMorfin må ikke gives"
        claims = extractor.extract(text)
        contra_claims = [c for c in claims if c.claim_type == ClaimType.CONTRAINDICATION]
        assert len(contra_claims) >= 1
        assert contra_claims[0].line_number == 3

    def test_markdown_header_ignored(self, extractor: ClaimExtractor) -> None:
        """Skips markdown headers."""
        text = "# Må ikke gives\nMedicin må ikke gives ved allergi"
        claims = extractor.extract(text)
        contra_claims = [c for c in claims if c.claim_type == ClaimType.CONTRAINDICATION]
        # Should only find the one on line 2, not the header
        assert len(contra_claims) >= 1
        assert all(c.line_number != 1 for c in contra_claims)

    def test_confidence_higher_with_source(self, extractor: ClaimExtractor) -> None:
        """Confidence is higher when source reference present."""
        text_with_source = "Morfin må ikke gives [SRC001]"
        text_without_source = "Morfin må ikke gives"

        claims_with = extractor.extract(text_with_source)
        claims_without = extractor.extract(text_without_source)

        contra_with = [c for c in claims_with if c.claim_type == ClaimType.CONTRAINDICATION]
        contra_without = [c for c in claims_without if c.claim_type == ClaimType.CONTRAINDICATION]

        if contra_with and contra_without:
            assert contra_with[0].confidence > contra_without[0].confidence


class TestRealWorldExamples:
    """Tests based on real Danish medical procedure text."""

    def test_opioid_respiratory_depression(self, extractor: ClaimExtractor) -> None:
        """Real example from pain management guideline."""
        text = "Opioider må ikke gives til patienter med svær respirationsdepression"
        claims = extractor.extract(text)
        contra_claims = [c for c in claims if c.claim_type == ClaimType.CONTRAINDICATION]
        assert len(contra_claims) >= 1

    def test_nsaid_renal_failure(self, extractor: ClaimExtractor) -> None:
        """Real example from NSAID guideline."""
        text = "NSAID er kontraindiceret ved akut nyresvigt og bør undgås ved kronisk nyresygdom"
        claims = extractor.extract(text)
        contra_claims = [c for c in claims if c.claim_type == ClaimType.CONTRAINDICATION]
        assert len(contra_claims) >= 1

    def test_thrombolysis_bleeding(self, extractor: ClaimExtractor) -> None:
        """Real example from stroke guideline."""
        text = "Trombolyse er absolut kontraindiceret ved aktiv intern blødning"
        claims = extractor.extract(text)
        contra_claims = [c for c in claims if c.claim_type == ClaimType.CONTRAINDICATION]
        assert len(contra_claims) >= 1

    def test_metformin_contrast(self, extractor: ClaimExtractor) -> None:
        """Real example from diabetes guideline."""
        text = "Metformin skal seponeres og må ikke gives 48 timer før kontrastundersøgelse"
        claims = extractor.extract(text)
        contra_claims = [c for c in claims if c.claim_type == ClaimType.CONTRAINDICATION]
        assert len(contra_claims) >= 1

    def test_penicillin_allergy(self, extractor: ClaimExtractor) -> None:
        """Real example from antibiotic guideline."""
        text = "Penicillin er kontraindiceret hos patienter med kendt penicillinallergi"
        claims = extractor.extract(text)
        contra_claims = [c for c in claims if c.claim_type == ClaimType.CONTRAINDICATION]
        assert len(contra_claims) >= 1

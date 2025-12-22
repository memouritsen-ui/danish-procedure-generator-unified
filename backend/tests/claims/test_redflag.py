"""Tests for RED_FLAG claim extraction patterns.

Comprehensive tests for clinical warning sign patterns in Danish medical procedures.
Danish patterns: "advarsel" (warning), "OBS" (attention), "kritisk" (critical),
"akut" (acute), "mistanke om" (suspicion of), "henvis straks" (refer immediately).
Based on Phase 0 validation work with real procedure data.
"""

import pytest

from procedurewriter.claims.extractor import ClaimExtractor
from procedurewriter.models.claims import Claim, ClaimType


@pytest.fixture
def extractor() -> ClaimExtractor:
    """Create extractor for tests."""
    return ClaimExtractor(run_id="redflag-test")


class TestAdvarselPatterns:
    """Tests for 'advarsel' (warning) patterns."""

    def test_advarsel(self, extractor: ClaimExtractor) -> None:
        """Extracts 'Advarsel:' pattern."""
        text = "Advarsel: Risiko for anafylaksi"
        claims = extractor.extract(text)
        redflag_claims = [c for c in claims if c.claim_type == ClaimType.RED_FLAG]
        assert len(redflag_claims) >= 1
        assert any("advarsel" in c.text.lower() for c in redflag_claims)

    def test_advarselstegn(self, extractor: ClaimExtractor) -> None:
        """Extracts 'advarselstegn' pattern."""
        text = "Advarselstegn på sepsis inkluderer feber og takykardi"
        claims = extractor.extract(text)
        redflag_claims = [c for c in claims if c.claim_type == ClaimType.RED_FLAG]
        assert len(redflag_claims) >= 1

    def test_advarselssymptomer(self, extractor: ClaimExtractor) -> None:
        """Extracts 'advarselssymptomer' pattern."""
        text = "Advarselssymptomer på meningitis"
        claims = extractor.extract(text)
        redflag_claims = [c for c in claims if c.claim_type == ClaimType.RED_FLAG]
        assert len(redflag_claims) >= 1


class TestOBSPatterns:
    """Tests for 'OBS' (attention) patterns."""

    def test_obs_colon(self, extractor: ClaimExtractor) -> None:
        """Extracts 'OBS:' pattern."""
        text = "OBS: Kan udløse bronkospasme"
        claims = extractor.extract(text)
        redflag_claims = [c for c in claims if c.claim_type == ClaimType.RED_FLAG]
        assert len(redflag_claims) >= 1
        assert any("obs" in c.text.lower() for c in redflag_claims)

    def test_obs_exclamation(self, extractor: ClaimExtractor) -> None:
        """Extracts 'OBS!' pattern."""
        text = "OBS! Høj risiko for blødning"
        claims = extractor.extract(text)
        redflag_claims = [c for c in claims if c.claim_type == ClaimType.RED_FLAG]
        assert len(redflag_claims) >= 1

    def test_nb_colon(self, extractor: ClaimExtractor) -> None:
        """Extracts 'NB:' pattern."""
        text = "NB: Særlig forsigtighed ved ældre"
        claims = extractor.extract(text)
        redflag_claims = [c for c in claims if c.claim_type == ClaimType.RED_FLAG]
        assert len(redflag_claims) >= 1


class TestVigtigtPatterns:
    """Tests for 'vigtigt' (important) patterns."""

    def test_vigtigt_colon(self, extractor: ClaimExtractor) -> None:
        """Extracts 'Vigtigt:' pattern."""
        text = "Vigtigt: Kontroller allergistatus først"
        claims = extractor.extract(text)
        redflag_claims = [c for c in claims if c.claim_type == ClaimType.RED_FLAG]
        assert len(redflag_claims) >= 1
        assert any("vigtigt" in c.text.lower() for c in redflag_claims)

    def test_vigtigt_at(self, extractor: ClaimExtractor) -> None:
        """Extracts 'vigtigt at' pattern."""
        text = "Det er vigtigt at sikre frie luftveje"
        claims = extractor.extract(text)
        redflag_claims = [c for c in claims if c.claim_type == ClaimType.RED_FLAG]
        assert len(redflag_claims) >= 1


class TestKritiskPatterns:
    """Tests for 'kritisk' (critical) patterns."""

    def test_kritisk(self, extractor: ClaimExtractor) -> None:
        """Extracts 'kritisk' pattern."""
        text = "Kritisk tilstand kræver øjeblikkelig handling"
        claims = extractor.extract(text)
        redflag_claims = [c for c in claims if c.claim_type == ClaimType.RED_FLAG]
        assert len(redflag_claims) >= 1
        assert any("kritisk" in c.text.lower() for c in redflag_claims)

    def test_livstruende(self, extractor: ClaimExtractor) -> None:
        """Extracts 'livstruende' pattern."""
        text = "Livstruende tilstand ved respirationssvigt"
        claims = extractor.extract(text)
        redflag_claims = [c for c in claims if c.claim_type == ClaimType.RED_FLAG]
        assert len(redflag_claims) >= 1


class TestAkutPatterns:
    """Tests for 'akut' (acute/urgent) patterns."""

    def test_akut_behov(self, extractor: ClaimExtractor) -> None:
        """Extracts 'akut behov' pattern."""
        text = "Akut behov for intubation"
        claims = extractor.extract(text)
        redflag_claims = [c for c in claims if c.claim_type == ClaimType.RED_FLAG]
        assert len(redflag_claims) >= 1
        assert any("akut" in c.text.lower() for c in redflag_claims)

    def test_akut_risiko(self, extractor: ClaimExtractor) -> None:
        """Extracts 'akut risiko' pattern."""
        text = "Akut risiko for hjertestop"
        claims = extractor.extract(text)
        redflag_claims = [c for c in claims if c.claim_type == ClaimType.RED_FLAG]
        assert len(redflag_claims) >= 1

    def test_akut_fare(self, extractor: ClaimExtractor) -> None:
        """Extracts 'akut fare' pattern."""
        text = "Akut fare for aspiration"
        claims = extractor.extract(text)
        redflag_claims = [c for c in claims if c.claim_type == ClaimType.RED_FLAG]
        assert len(redflag_claims) >= 1


class TestMistankePatterns:
    """Tests for 'mistanke om' (suspicion of) patterns."""

    def test_mistanke_om(self, extractor: ClaimExtractor) -> None:
        """Extracts 'mistanke om' pattern."""
        text = "Ved mistanke om meningitis kontaktes vagthavende"
        claims = extractor.extract(text)
        redflag_claims = [c for c in claims if c.claim_type == ClaimType.RED_FLAG]
        assert len(redflag_claims) >= 1
        assert any("mistanke" in c.text.lower() for c in redflag_claims)

    def test_mistaenkes(self, extractor: ClaimExtractor) -> None:
        """Extracts 'mistænkes' pattern."""
        text = "Hvis sepsis mistænkes påbegyndes behandling straks"
        claims = extractor.extract(text)
        redflag_claims = [c for c in claims if c.claim_type == ClaimType.RED_FLAG]
        assert len(redflag_claims) >= 1


class TestRisikoPatterns:
    """Tests for 'risiko for' (risk of) patterns."""

    def test_risiko_for(self, extractor: ClaimExtractor) -> None:
        """Extracts 'risiko for' pattern."""
        text = "Høj risiko for respirationssvigt"
        claims = extractor.extract(text)
        redflag_claims = [c for c in claims if c.claim_type == ClaimType.RED_FLAG]
        assert len(redflag_claims) >= 1
        assert any("risiko" in c.text.lower() for c in redflag_claims)

    def test_oget_risiko(self, extractor: ClaimExtractor) -> None:
        """Extracts 'øget risiko' pattern."""
        text = "Øget risiko for blødning ved antikoagulation"
        claims = extractor.extract(text)
        redflag_claims = [c for c in claims if c.claim_type == ClaimType.RED_FLAG]
        assert len(redflag_claims) >= 1

    def test_fare_for(self, extractor: ClaimExtractor) -> None:
        """Extracts 'fare for' pattern."""
        text = "Fare for aspiration hos bevidstløse"
        claims = extractor.extract(text)
        redflag_claims = [c for c in claims if c.claim_type == ClaimType.RED_FLAG]
        assert len(redflag_claims) >= 1


class TestHenvisPatterns:
    """Tests for 'henvis straks' (refer immediately) patterns."""

    def test_henvis_straks(self, extractor: ClaimExtractor) -> None:
        """Extracts 'henvis straks' pattern."""
        text = "Henvis straks til kardiolog ved STEMI"
        claims = extractor.extract(text)
        redflag_claims = [c for c in claims if c.claim_type == ClaimType.RED_FLAG]
        assert len(redflag_claims) >= 1
        assert any("henvis" in c.text.lower() for c in redflag_claims)

    def test_henvis_akut(self, extractor: ClaimExtractor) -> None:
        """Extracts 'henvis akut' pattern."""
        text = "Henvis akut til intensiv afdeling"
        claims = extractor.extract(text)
        redflag_claims = [c for c in claims if c.claim_type == ClaimType.RED_FLAG]
        assert len(redflag_claims) >= 1

    def test_akut_henvisning(self, extractor: ClaimExtractor) -> None:
        """Extracts 'akut henvisning' pattern."""
        text = "Akut henvisning til neurokirurg"
        claims = extractor.extract(text)
        redflag_claims = [c for c in claims if c.claim_type == ClaimType.RED_FLAG]
        assert len(redflag_claims) >= 1


class TestTilkaldPatterns:
    """Tests for 'tilkald' (call for help) patterns."""

    def test_tilkald(self, extractor: ClaimExtractor) -> None:
        """Extracts 'tilkald' pattern."""
        text = "Tilkald anæstesiolog ved luftvejsproblemer"
        claims = extractor.extract(text)
        redflag_claims = [c for c in claims if c.claim_type == ClaimType.RED_FLAG]
        assert len(redflag_claims) >= 1
        assert any("tilkald" in c.text.lower() for c in redflag_claims)

    def test_tilkald_hjaelp(self, extractor: ClaimExtractor) -> None:
        """Extracts 'tilkald hjælp' pattern."""
        text = "Tilkald hjælp ved hjertestop"
        claims = extractor.extract(text)
        redflag_claims = [c for c in claims if c.claim_type == ClaimType.RED_FLAG]
        assert len(redflag_claims) >= 1

    def test_kontakt_straks(self, extractor: ClaimExtractor) -> None:
        """Extracts 'kontakt straks' pattern."""
        text = "Kontakt straks vagthavende ved forværring"
        claims = extractor.extract(text)
        redflag_claims = [c for c in claims if c.claim_type == ClaimType.RED_FLAG]
        assert len(redflag_claims) >= 1


class TestOjeblikkeligPatterns:
    """Tests for 'øjeblikkeligt' (immediately) patterns."""

    def test_ojeblikkelig(self, extractor: ClaimExtractor) -> None:
        """Extracts 'øjeblikkelig' pattern."""
        text = "Kræver øjeblikkelig intervention"
        claims = extractor.extract(text)
        redflag_claims = [c for c in claims if c.claim_type == ClaimType.RED_FLAG]
        assert len(redflag_claims) >= 1
        assert any("øjeblikkelig" in c.text.lower() for c in redflag_claims)

    def test_straks(self, extractor: ClaimExtractor) -> None:
        """Extracts 'straks' in urgent context."""
        text = "Behandling straks ved anafylaksi"
        claims = extractor.extract(text)
        redflag_claims = [c for c in claims if c.claim_type == ClaimType.RED_FLAG]
        assert len(redflag_claims) >= 1


class TestEdgeCases:
    """Tests for edge cases and special patterns."""

    def test_empty_text(self, extractor: ClaimExtractor) -> None:
        """Returns empty list for empty text."""
        claims = extractor.extract("")
        assert claims == []

    def test_no_redflags(self, extractor: ClaimExtractor) -> None:
        """Returns no red flags for text without warning patterns."""
        text = "Denne patient har pneumoni og behandles med antibiotika."
        claims = extractor.extract(text)
        redflag_claims = [c for c in claims if c.claim_type == ClaimType.RED_FLAG]
        assert len(redflag_claims) == 0

    def test_with_source_reference(self, extractor: ClaimExtractor) -> None:
        """Extracts red flag with source reference."""
        text = "OBS: Risiko for anafylaksi [SRC001]"
        claims = extractor.extract(text)
        redflag_claims = [c for c in claims if c.claim_type == ClaimType.RED_FLAG]
        assert len(redflag_claims) >= 1
        assert any(c.source_refs for c in redflag_claims)

    def test_redflag_with_line_number(self, extractor: ClaimExtractor) -> None:
        """Correctly tracks line numbers."""
        text = "Linje 1\nLinje 2\nOBS: Fare for blødning"
        claims = extractor.extract(text)
        redflag_claims = [c for c in claims if c.claim_type == ClaimType.RED_FLAG]
        assert len(redflag_claims) >= 1
        assert redflag_claims[0].line_number == 3

    def test_markdown_header_ignored(self, extractor: ClaimExtractor) -> None:
        """Skips markdown headers."""
        text = "# OBS: Vigtig information\nOBS: Risiko for komplikationer"
        claims = extractor.extract(text)
        redflag_claims = [c for c in claims if c.claim_type == ClaimType.RED_FLAG]
        # Should only find the one on line 2, not the header
        assert len(redflag_claims) >= 1
        assert all(c.line_number != 1 for c in redflag_claims)

    def test_confidence_higher_with_source(self, extractor: ClaimExtractor) -> None:
        """Confidence is higher when source reference present."""
        text_with_source = "OBS: Fare [SRC001]"
        text_without_source = "OBS: Fare"

        claims_with = extractor.extract(text_with_source)
        claims_without = extractor.extract(text_without_source)

        redflag_with = [c for c in claims_with if c.claim_type == ClaimType.RED_FLAG]
        redflag_without = [c for c in claims_without if c.claim_type == ClaimType.RED_FLAG]

        if redflag_with and redflag_without:
            assert redflag_with[0].confidence > redflag_without[0].confidence


class TestRealWorldExamples:
    """Tests based on real Danish medical procedure text."""

    def test_sepsis_warning(self, extractor: ClaimExtractor) -> None:
        """Real example from sepsis guideline."""
        text = "OBS: Ved mistanke om sepsis skal antibiotika gives inden 1 time"
        claims = extractor.extract(text)
        redflag_claims = [c for c in claims if c.claim_type == ClaimType.RED_FLAG]
        assert len(redflag_claims) >= 1

    def test_anaphylaxis_alert(self, extractor: ClaimExtractor) -> None:
        """Real example from anaphylaxis guideline."""
        text = "Advarsel: Anafylaksi er en livstruende tilstand"
        claims = extractor.extract(text)
        redflag_claims = [c for c in claims if c.claim_type == ClaimType.RED_FLAG]
        assert len(redflag_claims) >= 1

    def test_stroke_referral(self, extractor: ClaimExtractor) -> None:
        """Real example from stroke guideline."""
        text = "Ved mistanke om apopleksi henvis straks til trombolyse-vurdering"
        claims = extractor.extract(text)
        redflag_claims = [c for c in claims if c.claim_type == ClaimType.RED_FLAG]
        assert len(redflag_claims) >= 1

    def test_cardiac_arrest_call(self, extractor: ClaimExtractor) -> None:
        """Real example from resuscitation guideline."""
        text = "Tilkald hjertestophold ved pulsløs patient"
        claims = extractor.extract(text)
        redflag_claims = [c for c in claims if c.claim_type == ClaimType.RED_FLAG]
        assert len(redflag_claims) >= 1

    def test_meningitis_warning(self, extractor: ClaimExtractor) -> None:
        """Real example from meningitis guideline."""
        text = "Vigtigt: Ved mistanke om bakteriel meningitis påbegyndes behandling straks"
        claims = extractor.extract(text)
        redflag_claims = [c for c in claims if c.claim_type == ClaimType.RED_FLAG]
        assert len(redflag_claims) >= 1

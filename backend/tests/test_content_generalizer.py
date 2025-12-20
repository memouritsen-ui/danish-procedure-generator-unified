"""Tests for ContentGeneralizer - department-specific content removal."""

from __future__ import annotations

import pytest

from procedurewriter.pipeline.content_generalizer import (
    ContentGeneralizer,
    GeneralizationStats,
    generalize_procedure_content,
)


class TestPhoneNumberGeneralization:
    """Tests for phone number pattern detection and replacement."""

    def test_tlf_with_dot(self) -> None:
        """'tlf. 5804' should be generalized."""
        generalizer = ContentGeneralizer()
        content = "Kontakt anæstesiologisk forvagt (tlf. 5804) mhp. tilsyn."
        result, stats = generalizer.generalize(content)

        assert "5804" not in result
        assert "[LOKAL]" in result
        assert stats.phone_numbers >= 1

    def test_tlf_without_dot(self) -> None:
        """'tlf 5804' should be generalized."""
        generalizer = ContentGeneralizer()
        content = "Ring til tlf 5803 eller tlf 5804."
        result, stats = generalizer.generalize(content)

        assert "5803" not in result
        assert "5804" not in result
        assert stats.phone_numbers >= 2

    def test_telefon_full_word(self) -> None:
        """'telefon 12345678' should be generalized."""
        generalizer = ContentGeneralizer()
        content = "Kontakt vagten på telefon 12345678."
        result, stats = generalizer.generalize(content)

        assert "12345678" not in result
        assert stats.phone_numbers >= 1

    def test_preserves_clinical_numbers(self) -> None:
        """Clinical numbers like 'CH20' and dosages should be preserved."""
        generalizer = ContentGeneralizer()
        content = "Anvend CH20 eller CH28 dræn. Fentanyl 50-100 mikrog."
        result, stats = generalizer.generalize(content)

        assert "CH20" in result
        assert "CH28" in result
        assert "50-100" in result
        assert stats.phone_numbers == 0


class TestRoomReferenceGeneralization:
    """Tests for room reference pattern detection and replacement."""

    def test_stue_number(self) -> None:
        """'stue 99' should be generalized."""
        generalizer = ContentGeneralizer()
        content = "Hent udstyr fra stue 99."
        result, stats = generalizer.generalize(content)

        assert "stue 99" not in result
        assert stats.room_references >= 1

    def test_overfor_stue(self) -> None:
        """'overfor stue 99' should be removed."""
        generalizer = ContentGeneralizer()
        content = "Ved medicinsk base (overfor stue 99) findes udstyr."
        result, stats = generalizer.generalize(content)

        assert "overfor stue 99" not in result
        assert "stue 99" not in result

    def test_paa_stue(self) -> None:
        """'på stue 12' should be generalized."""
        generalizer = ContentGeneralizer()
        content = "Patienten ligger på stue 12."
        result, stats = generalizer.generalize(content)

        assert "stue 12" not in result


class TestLocationReferenceGeneralization:
    """Tests for location reference pattern detection and replacement."""

    def test_medicinsk_base_with_parentheses(self) -> None:
        """'ved medicinsk base (overfor stue 99)' should be generalized."""
        generalizer = ContentGeneralizer()
        content = "Hent fra pleura-procedurevogn ved medicinsk base (overfor stue 99)."
        result, stats = generalizer.generalize(content)

        assert "medicinsk base" not in result
        assert "stue 99" not in result
        assert "udstyrsdepot" in result or "procedurevogn" in result

    def test_medicinsk_base_simple(self) -> None:
        """'ved medicinsk base' should be generalized."""
        generalizer = ContentGeneralizer()
        content = "Udstyr hentes ved medicinsk base."
        result, stats = generalizer.generalize(content)

        assert "medicinsk base" not in result
        assert "udstyrsdepot" in result


class TestHospitalReferenceGeneralization:
    """Tests for hospital reference pattern detection and replacement."""

    def test_i_skejby(self) -> None:
        """'i Skejby' should be removed."""
        generalizer = ContentGeneralizer()
        content = "Henvis til thoraxkirurgisk afdeling i Skejby."
        result, stats = generalizer.generalize(content)

        assert "Skejby" not in result
        assert "thoraxkirurgisk afdeling" in result

    def test_hospital_abbreviations(self) -> None:
        """Hospital abbreviations like 'HEH' should be removed."""
        generalizer = ContentGeneralizer()
        content = "Ifølge retningslinje for HEH skal patienten..."
        result, stats = generalizer.generalize(content)

        assert "HEH" not in result

    def test_paa_hospital(self) -> None:
        """'på Herlev Hospital' should be generalized."""
        generalizer = ContentGeneralizer()
        content = "Proceduren udføres på Herlev Hospital."
        result, stats = generalizer.generalize(content)

        assert "Herlev" not in result


class TestSystemReferenceGeneralization:
    """Tests for IT system reference pattern detection and replacement."""

    def test_case_bestilling(self) -> None:
        """'CASE-bestilling' should be generalized."""
        generalizer = ContentGeneralizer()
        content = "Angiv i CASE-bestilling om anæstesiologisk personale er påkrævet."
        result, stats = generalizer.generalize(content)

        assert "CASE-bestilling" not in result
        assert "elektronisk bestilling" in result

    def test_epic(self) -> None:
        """'i EPIC' should be generalized."""
        generalizer = ContentGeneralizer()
        content = "Dokumentér i EPIC under procedurenotat."
        result, stats = generalizer.generalize(content)

        assert "EPIC" not in result
        assert "journalsystemet" in result


class TestLokalMarkers:
    """Tests for [LOKAL] marker functionality."""

    def test_lokal_marker_added(self) -> None:
        """[LOKAL] marker should be added by default."""
        generalizer = ContentGeneralizer(use_lokal_markers=True)
        content = "Ring til tlf. 5804."
        result, _ = generalizer.generalize(content)

        assert "[LOKAL]" in result

    def test_lokal_marker_disabled(self) -> None:
        """[LOKAL] markers can be disabled."""
        generalizer = ContentGeneralizer(use_lokal_markers=False)
        content = "Ring til tlf. 5804."
        result, _ = generalizer.generalize(content)

        assert "[LOKAL]" not in result

    def test_deduplicate_lokal_markers(self) -> None:
        """Multiple [LOKAL] markers on same line should be deduplicated."""
        generalizer = ContentGeneralizer(use_lokal_markers=True)
        content = "Ring til tlf. 5804 eller tlf. 5803."
        result, _ = generalizer.generalize(content)

        # Should only have one [LOKAL] marker per line
        assert result.count("[LOKAL]") == 1


class TestStatistics:
    """Tests for generalization statistics tracking."""

    def test_stats_phone_numbers(self) -> None:
        """Phone number replacements should be counted."""
        generalizer = ContentGeneralizer()
        content = "tlf. 5804 og tlf. 5803"
        _, stats = generalizer.generalize(content)

        assert stats.phone_numbers == 2

    def test_stats_total(self) -> None:
        """Total replacements should be summed correctly."""
        generalizer = ContentGeneralizer()
        content = "Ring tlf. 5804 på stue 99 i Skejby."
        _, stats = generalizer.generalize(content)

        assert stats.total_replacements >= 3

    def test_stats_to_dict(self) -> None:
        """Stats should convert to dict correctly."""
        stats = GeneralizationStats(phone_numbers=2, room_references=1)
        d = stats.to_dict()

        assert d["phone_numbers"] == 2
        assert d["room_references"] == 1
        assert "total" in d


class TestConvenienceFunction:
    """Tests for the convenience function."""

    def test_generalize_procedure_content(self) -> None:
        """Convenience function should work correctly."""
        content = "Ring til tlf. 5804."
        result, stats = generalize_procedure_content(content)

        assert "5804" not in result
        assert isinstance(stats, dict)
        assert "total" in stats


class TestPreserveClinicalContent:
    """Tests to ensure clinical content is preserved."""

    def test_preserves_drug_dosages(self) -> None:
        """Drug dosages should not be altered."""
        generalizer = ContentGeneralizer()
        content = "Administrér fentanyl 50-100 mikrog i.v."
        result, _ = generalizer.generalize(content)

        assert "fentanyl 50-100 mikrog" in result

    def test_preserves_clinical_criteria(self) -> None:
        """Clinical criteria with numbers should be preserved."""
        generalizer = ContentGeneralizer()
        content = "Ved pneumothorax >2 cm lateralt i hilushøjde."
        result, _ = generalizer.generalize(content)

        assert ">2 cm" in result
        assert "hilushøjde" in result

    def test_preserves_equipment_specs(self) -> None:
        """Equipment specifications should be preserved."""
        generalizer = ContentGeneralizer()
        content = "Anvend pleuradræn i str. 21CH, 24CH, 30CH, 32CH."
        result, _ = generalizer.generalize(content)

        assert "21CH" in result
        assert "24CH" in result
        assert "30CH" in result
        assert "32CH" in result

    def test_preserves_fev1_values(self) -> None:
        """FEV1 and other clinical values should be preserved."""
        generalizer = ContentGeneralizer()
        content = "Ved FEV1 <1 l eller <40% er der øget risiko."
        result, _ = generalizer.generalize(content)

        assert "FEV1 <1 l" in result
        assert "<40%" in result


class TestRealWorldContent:
    """Tests using real content from generated procedures."""

    def test_pleuradraen_snippet(self) -> None:
        """Real content from Pleuradræn procedure should be generalized."""
        generalizer = ContentGeneralizer()
        content = """Klargør udstyr fra pleura-procedurevogn ved medicinsk base (overfor stue 99)
        i medicinsk regi, eller procedurebakke på Intensiv med pigtail-typer."""
        result, stats = generalizer.generalize(content)

        assert "stue 99" not in result
        assert "medicinsk base" not in result
        assert stats.total_replacements >= 1

    def test_anaestesi_contact_snippet(self) -> None:
        """Anesthesia contact info should be generalized."""
        generalizer = ContentGeneralizer()
        content = """Hvis anæstesiologisk tilstedeværelse er påkrævet, kontakt
        anæstesiologisk forvagt (tlf. 5804) mhp. tilsyn på operationsafsnittet."""
        result, stats = generalizer.generalize(content)

        assert "5804" not in result
        assert "anæstesiologisk forvagt" in result  # Role preserved
        assert stats.phone_numbers >= 1

    def test_thoraxkirurgi_skejby_snippet(self) -> None:
        """Skejby reference should be removed."""
        generalizer = ContentGeneralizer()
        content = "Ved behandlingssvigt efter 3-5 dage: kontakt thoraxkirurgisk afdeling i Skejby."
        result, stats = generalizer.generalize(content)

        assert "Skejby" not in result
        assert "thoraxkirurgisk afdeling" in result  # Department type preserved

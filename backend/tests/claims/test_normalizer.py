"""Tests for unit normalization in medical claims.

Comprehensive tests for standardizing medical units to canonical forms.
This ensures consistent representation for comparison and validation.

Normalizations:
- mcg → μg (microgram to Greek mu)
- IE → IU (Danish to international units)
- ml/mL → ml (standardize milliliter)
- Spacing normalization (e.g., "50mg" → "50 mg")
- Case normalization where applicable
"""

import pytest

from procedurewriter.claims.normalizer import UnitNormalizer


@pytest.fixture
def normalizer() -> UnitNormalizer:
    """Create normalizer for tests."""
    return UnitNormalizer()


class TestMicrogramNormalization:
    """Tests for microgram (mcg/μg) normalization."""

    def test_mcg_to_microgram(self, normalizer: UnitNormalizer) -> None:
        """Converts 'mcg' to 'μg'."""
        result = normalizer.normalize_unit("mcg")
        assert result == "μg"

    def test_mcg_uppercase(self, normalizer: UnitNormalizer) -> None:
        """Converts 'MCG' to 'μg'."""
        result = normalizer.normalize_unit("MCG")
        assert result == "μg"

    def test_ug_to_microgram(self, normalizer: UnitNormalizer) -> None:
        """Converts 'ug' to 'μg'."""
        result = normalizer.normalize_unit("ug")
        assert result == "μg"

    def test_microgram_already_normalized(self, normalizer: UnitNormalizer) -> None:
        """Keeps 'μg' as 'μg'."""
        result = normalizer.normalize_unit("μg")
        assert result == "μg"

    def test_mikrogram_danish(self, normalizer: UnitNormalizer) -> None:
        """Converts Danish 'mikrogram' to 'μg'."""
        result = normalizer.normalize_unit("mikrogram")
        assert result == "μg"


class TestMilligramNormalization:
    """Tests for milligram (mg) normalization."""

    def test_mg_lowercase(self, normalizer: UnitNormalizer) -> None:
        """Keeps 'mg' as 'mg'."""
        result = normalizer.normalize_unit("mg")
        assert result == "mg"

    def test_mg_uppercase(self, normalizer: UnitNormalizer) -> None:
        """Converts 'MG' to 'mg'."""
        result = normalizer.normalize_unit("MG")
        assert result == "mg"

    def test_milligram_full(self, normalizer: UnitNormalizer) -> None:
        """Converts 'milligram' to 'mg'."""
        result = normalizer.normalize_unit("milligram")
        assert result == "mg"


class TestGramNormalization:
    """Tests for gram (g) normalization."""

    def test_g_lowercase(self, normalizer: UnitNormalizer) -> None:
        """Keeps 'g' as 'g'."""
        result = normalizer.normalize_unit("g")
        assert result == "g"

    def test_g_uppercase(self, normalizer: UnitNormalizer) -> None:
        """Converts 'G' to 'g'."""
        result = normalizer.normalize_unit("G")
        assert result == "g"

    def test_gram_full(self, normalizer: UnitNormalizer) -> None:
        """Converts 'gram' to 'g'."""
        result = normalizer.normalize_unit("gram")
        assert result == "g"


class TestMilliliterNormalization:
    """Tests for milliliter (ml) normalization."""

    def test_ml_lowercase(self, normalizer: UnitNormalizer) -> None:
        """Keeps 'ml' as 'ml'."""
        result = normalizer.normalize_unit("ml")
        assert result == "ml"

    def test_mL_mixed_case(self, normalizer: UnitNormalizer) -> None:
        """Converts 'mL' to 'ml'."""
        result = normalizer.normalize_unit("mL")
        assert result == "ml"

    def test_ML_uppercase(self, normalizer: UnitNormalizer) -> None:
        """Converts 'ML' to 'ml'."""
        result = normalizer.normalize_unit("ML")
        assert result == "ml"

    def test_milliliter_full(self, normalizer: UnitNormalizer) -> None:
        """Converts 'milliliter' to 'ml'."""
        result = normalizer.normalize_unit("milliliter")
        assert result == "ml"


class TestInternationalUnitsNormalization:
    """Tests for international units (IE/IU) normalization."""

    def test_ie_to_iu(self, normalizer: UnitNormalizer) -> None:
        """Converts Danish 'IE' to 'IU'."""
        result = normalizer.normalize_unit("IE")
        assert result == "IU"

    def test_ie_lowercase(self, normalizer: UnitNormalizer) -> None:
        """Converts 'ie' to 'IU'."""
        result = normalizer.normalize_unit("ie")
        assert result == "IU"

    def test_iu_already_normalized(self, normalizer: UnitNormalizer) -> None:
        """Keeps 'IU' as 'IU'."""
        result = normalizer.normalize_unit("IU")
        assert result == "IU"

    def test_iu_lowercase(self, normalizer: UnitNormalizer) -> None:
        """Converts 'iu' to 'IU'."""
        result = normalizer.normalize_unit("iu")
        assert result == "IU"


class TestUnitsNormalization:
    """Tests for generic units (U) normalization."""

    def test_u_uppercase(self, normalizer: UnitNormalizer) -> None:
        """Keeps 'U' as 'U'."""
        result = normalizer.normalize_unit("U")
        assert result == "U"

    def test_u_lowercase(self, normalizer: UnitNormalizer) -> None:
        """Converts 'u' to 'U'."""
        result = normalizer.normalize_unit("u")
        assert result == "U"

    def test_units_full(self, normalizer: UnitNormalizer) -> None:
        """Converts 'units' to 'U'."""
        result = normalizer.normalize_unit("units")
        assert result == "U"

    def test_enheder_danish(self, normalizer: UnitNormalizer) -> None:
        """Converts Danish 'enheder' to 'U'."""
        result = normalizer.normalize_unit("enheder")
        assert result == "U"


class TestCompoundUnitNormalization:
    """Tests for compound units (mg/kg, mg/kg/d, etc.)."""

    def test_mg_per_kg(self, normalizer: UnitNormalizer) -> None:
        """Normalizes 'mg/kg' to 'mg/kg'."""
        result = normalizer.normalize_unit("mg/kg")
        assert result == "mg/kg"

    def test_mg_per_kg_per_day(self, normalizer: UnitNormalizer) -> None:
        """Normalizes 'mg/kg/d' to 'mg/kg/d'."""
        result = normalizer.normalize_unit("mg/kg/d")
        assert result == "mg/kg/d"

    def test_mg_per_kg_per_dag(self, normalizer: UnitNormalizer) -> None:
        """Converts Danish 'mg/kg/dag' to 'mg/kg/d'."""
        result = normalizer.normalize_unit("mg/kg/dag")
        assert result == "mg/kg/d"

    def test_mg_per_kg_per_dogn(self, normalizer: UnitNormalizer) -> None:
        """Converts Danish 'mg/kg/døgn' to 'mg/kg/d'."""
        result = normalizer.normalize_unit("mg/kg/døgn")
        assert result == "mg/kg/d"

    def test_mcg_per_kg(self, normalizer: UnitNormalizer) -> None:
        """Normalizes 'mcg/kg' to 'μg/kg'."""
        result = normalizer.normalize_unit("mcg/kg")
        assert result == "μg/kg"

    def test_mcg_per_kg_per_min(self, normalizer: UnitNormalizer) -> None:
        """Normalizes 'mcg/kg/min' to 'μg/kg/min'."""
        result = normalizer.normalize_unit("mcg/kg/min")
        assert result == "μg/kg/min"

    def test_ml_per_hour(self, normalizer: UnitNormalizer) -> None:
        """Normalizes 'ml/t' (Danish) to 'ml/h'."""
        result = normalizer.normalize_unit("ml/t")
        assert result == "ml/h"

    def test_ml_per_time(self, normalizer: UnitNormalizer) -> None:
        """Normalizes 'ml/time' (Danish) to 'ml/h'."""
        result = normalizer.normalize_unit("ml/time")
        assert result == "ml/h"


class TestPercentNormalization:
    """Tests for percentage normalization."""

    def test_percent_symbol(self, normalizer: UnitNormalizer) -> None:
        """Keeps '%' as '%'."""
        result = normalizer.normalize_unit("%")
        assert result == "%"

    def test_procent_danish(self, normalizer: UnitNormalizer) -> None:
        """Converts Danish 'procent' to '%'."""
        result = normalizer.normalize_unit("procent")
        assert result == "%"


class TestDoseTextNormalization:
    """Tests for normalizing complete dose text strings."""

    def test_dose_with_mcg(self, normalizer: UnitNormalizer) -> None:
        """Normalizes dose text with mcg."""
        result = normalizer.normalize_dose_text("fentanyl 50 mcg")
        assert "50 μg" in result

    def test_dose_with_ie(self, normalizer: UnitNormalizer) -> None:
        """Normalizes dose text with IE."""
        result = normalizer.normalize_dose_text("heparin 5000 IE")
        assert "5000 IU" in result

    def test_dose_with_mg_kg_dag(self, normalizer: UnitNormalizer) -> None:
        """Normalizes dose text with mg/kg/dag."""
        result = normalizer.normalize_dose_text("amoxicillin 50 mg/kg/dag")
        assert "mg/kg/d" in result

    def test_dose_no_unit(self, normalizer: UnitNormalizer) -> None:
        """Handles dose text without recognized unit."""
        result = normalizer.normalize_dose_text("give medication")
        assert result == "give medication"

    def test_dose_adds_spacing(self, normalizer: UnitNormalizer) -> None:
        """Adds space between number and unit."""
        result = normalizer.normalize_dose_text("500mg")
        assert "500 mg" in result


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_string(self, normalizer: UnitNormalizer) -> None:
        """Returns empty string for empty input."""
        result = normalizer.normalize_unit("")
        assert result == ""

    def test_none_input(self, normalizer: UnitNormalizer) -> None:
        """Returns None for None input."""
        result = normalizer.normalize_unit(None)
        assert result is None

    def test_unknown_unit(self, normalizer: UnitNormalizer) -> None:
        """Returns original for unknown unit."""
        result = normalizer.normalize_unit("xyz")
        assert result == "xyz"

    def test_whitespace_handling(self, normalizer: UnitNormalizer) -> None:
        """Strips whitespace from unit."""
        result = normalizer.normalize_unit("  mg  ")
        assert result == "mg"

    def test_mixed_case_compound(self, normalizer: UnitNormalizer) -> None:
        """Handles mixed case compound units."""
        result = normalizer.normalize_unit("Mg/Kg")
        assert result == "mg/kg"


class TestRealWorldExamples:
    """Tests based on real Danish medical procedure text."""

    def test_adrenalin_dose(self, normalizer: UnitNormalizer) -> None:
        """Real example from anaphylaxis guideline."""
        result = normalizer.normalize_dose_text("adrenalin 0,5 mg IM")
        assert "0,5 mg" in result or "0.5 mg" in result

    def test_noradrenalin_infusion(self, normalizer: UnitNormalizer) -> None:
        """Real example from sepsis guideline."""
        result = normalizer.normalize_dose_text("noradrenalin 0,1-0,5 mcg/kg/min")
        assert "μg/kg/min" in result

    def test_heparin_units(self, normalizer: UnitNormalizer) -> None:
        """Real example from anticoagulation guideline."""
        result = normalizer.normalize_dose_text("heparin 80 IE/kg bolus")
        assert "IU/kg" in result

    def test_morphine_iv(self, normalizer: UnitNormalizer) -> None:
        """Real example from pain management."""
        result = normalizer.normalize_dose_text("morfin 2,5-5 mg i.v.")
        assert "mg" in result

    def test_oxygen_liter(self, normalizer: UnitNormalizer) -> None:
        """Real example from respiratory care."""
        # L/min is already standard
        result = normalizer.normalize_unit("L/min")
        assert result == "L/min"

    def test_saline_ml(self, normalizer: UnitNormalizer) -> None:
        """Real example from fluid resuscitation."""
        result = normalizer.normalize_dose_text("NaCl 500 mL")
        assert "500 ml" in result

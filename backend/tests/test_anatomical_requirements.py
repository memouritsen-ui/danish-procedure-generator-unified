"""Tests for anatomical requirements validation.

TDD Phase 3: Anatomical Content Requirements
Ensures invasive procedures include required anatomical content.
"""

from __future__ import annotations

import pytest


class TestProcedureTypeEnum:
    """Test ProcedureType classification."""

    def test_procedure_type_has_invasive(self):
        """ProcedureType should have INVASIVE category."""
        from procedurewriter.pipeline.anatomical_requirements import ProcedureType

        assert ProcedureType.INVASIVE.value == "invasive"

    def test_procedure_type_has_non_invasive(self):
        """ProcedureType should have NON_INVASIVE category."""
        from procedurewriter.pipeline.anatomical_requirements import ProcedureType

        assert ProcedureType.NON_INVASIVE.value == "non_invasive"


class TestAnatomicalLandmark:
    """Test AnatomicalLandmark dataclass."""

    def test_landmark_has_required_fields(self):
        """AnatomicalLandmark should have name and aliases."""
        from procedurewriter.pipeline.anatomical_requirements import AnatomicalLandmark

        landmark = AnatomicalLandmark(
            name="5. interkostalrum",
            aliases=["femte interkostalrum", "5th intercostal space"],
            category="thorax",
        )

        assert landmark.name == "5. interkostalrum"
        assert "femte interkostalrum" in landmark.aliases
        assert landmark.category == "thorax"


class TestProcedureRequirements:
    """Test ProcedureRequirements dataclass."""

    def test_requirements_has_landmarks(self):
        """ProcedureRequirements should specify required landmarks."""
        from procedurewriter.pipeline.anatomical_requirements import (
            ProcedureRequirements,
            AnatomicalLandmark,
        )

        reqs = ProcedureRequirements(
            procedure_name="pleuradræn",
            procedure_type="invasive",
            landmarks=[
                AnatomicalLandmark(
                    name="5. interkostalrum",
                    aliases=["femte interkostalrum"],
                    category="thorax",
                ),
            ],
            requires_depth_guidance=True,
            requires_surface_anatomy=True,
        )

        assert reqs.procedure_name == "pleuradræn"
        assert len(reqs.landmarks) == 1
        assert reqs.requires_depth_guidance is True

    def test_requirements_has_optional_fields(self):
        """ProcedureRequirements should have optional angle and verification."""
        from procedurewriter.pipeline.anatomical_requirements import (
            ProcedureRequirements,
        )

        reqs = ProcedureRequirements(
            procedure_name="arteriel_kanyle",
            procedure_type="invasive",
            landmarks=[],
            requires_depth_guidance=True,
            requires_surface_anatomy=True,
            requires_angle_guidance=True,
            requires_verification_step=True,
        )

        assert reqs.requires_angle_guidance is True
        assert reqs.requires_verification_step is True


class TestAnatomicalRequirementsRegistry:
    """Test AnatomicalRequirementsRegistry for loading procedure configs."""

    def test_registry_can_be_instantiated(self):
        """AnatomicalRequirementsRegistry should be instantiable."""
        from procedurewriter.pipeline.anatomical_requirements import (
            AnatomicalRequirementsRegistry,
        )

        registry = AnatomicalRequirementsRegistry()
        assert registry is not None

    def test_registry_has_get_requirements_method(self):
        """Registry should have get_requirements method."""
        from procedurewriter.pipeline.anatomical_requirements import (
            AnatomicalRequirementsRegistry,
        )

        registry = AnatomicalRequirementsRegistry()
        assert hasattr(registry, "get_requirements")
        assert callable(registry.get_requirements)

    def test_registry_returns_requirements_for_pleuradraen(self):
        """Registry should return requirements for pleuradræn."""
        from procedurewriter.pipeline.anatomical_requirements import (
            AnatomicalRequirementsRegistry,
        )

        registry = AnatomicalRequirementsRegistry()
        reqs = registry.get_requirements("pleuradræn")

        assert reqs is not None
        assert reqs.procedure_name == "pleuradræn"
        assert reqs.procedure_type == "invasive"

    def test_registry_returns_requirements_for_lumbalpunktur(self):
        """Registry should return requirements for lumbalpunktur."""
        from procedurewriter.pipeline.anatomical_requirements import (
            AnatomicalRequirementsRegistry,
        )

        registry = AnatomicalRequirementsRegistry()
        reqs = registry.get_requirements("lumbalpunktur")

        assert reqs is not None
        assert reqs.procedure_name == "lumbalpunktur"
        assert len(reqs.landmarks) >= 2  # At least L3-L4 and crista iliaca

    def test_registry_returns_none_for_unknown_procedure(self):
        """Registry should return None for unknown procedures."""
        from procedurewriter.pipeline.anatomical_requirements import (
            AnatomicalRequirementsRegistry,
        )

        registry = AnatomicalRequirementsRegistry()
        reqs = registry.get_requirements("unknown_procedure_xyz")

        assert reqs is None

    def test_registry_has_list_invasive_procedures(self):
        """Registry should list all invasive procedures."""
        from procedurewriter.pipeline.anatomical_requirements import (
            AnatomicalRequirementsRegistry,
        )

        registry = AnatomicalRequirementsRegistry()
        invasive = registry.list_invasive_procedures()

        assert isinstance(invasive, list)
        assert "pleuradræn" in invasive
        assert "lumbalpunktur" in invasive


class TestAnatomicalValidator:
    """Test AnatomicalValidator for checking content against requirements."""

    def test_validator_can_be_instantiated(self):
        """AnatomicalValidator should be instantiable."""
        from procedurewriter.pipeline.anatomical_requirements import (
            AnatomicalValidator,
        )

        validator = AnatomicalValidator()
        assert validator is not None

    def test_validator_has_validate_method(self):
        """Validator should have validate method."""
        from procedurewriter.pipeline.anatomical_requirements import (
            AnatomicalValidator,
        )

        validator = AnatomicalValidator()
        assert hasattr(validator, "validate")
        assert callable(validator.validate)

    def test_validator_returns_validation_result(self):
        """validate() should return ValidationResult."""
        from procedurewriter.pipeline.anatomical_requirements import (
            AnatomicalValidator,
            ValidationResult,
        )

        validator = AnatomicalValidator()
        content = "Identificer 5. interkostalrum i midtaksillærlinjen."
        result = validator.validate("pleuradræn", content)

        assert isinstance(result, ValidationResult)

    def test_validates_pleuradraen_with_landmarks(self):
        """Should pass validation when landmarks are present."""
        from procedurewriter.pipeline.anatomical_requirements import (
            AnatomicalValidator,
        )

        validator = AnatomicalValidator()
        content = """
        Positionér patienten i lateral decubitus.
        Identificer 5. interkostalrum i midtaksillærlinjen.
        Identificer triangle of safety.
        Indsæt nålen i en vinkel på 45 grader.
        Avancér 2-3 cm efter pleuragennembrud.
        """
        result = validator.validate("pleuradræn", content)

        assert result.is_valid is True
        assert len(result.missing_landmarks) == 0

    def test_fails_validation_when_landmarks_missing(self):
        """Should fail validation when required landmarks are missing."""
        from procedurewriter.pipeline.anatomical_requirements import (
            AnatomicalValidator,
        )

        validator = AnatomicalValidator()
        content = """
        Ring til bagvagt ved komplikationer.
        Følg lokal retningslinje for sterilteknik.
        Aftal rollefordeling med teamet.
        """
        result = validator.validate("pleuradræn", content)

        assert result.is_valid is False
        assert len(result.missing_landmarks) > 0

    def test_detects_missing_depth_guidance(self):
        """Should detect when depth guidance is missing."""
        from procedurewriter.pipeline.anatomical_requirements import (
            AnatomicalValidator,
        )

        validator = AnatomicalValidator()
        content = """
        Identificer 5. interkostalrum i midtaksillærlinjen.
        Indsæt drænet.
        """  # No depth guidance
        result = validator.validate("pleuradræn", content)

        assert result.has_depth_guidance is False

    def test_detects_present_depth_guidance(self):
        """Should detect when depth guidance is present."""
        from procedurewriter.pipeline.anatomical_requirements import (
            AnatomicalValidator,
        )

        validator = AnatomicalValidator()
        content = """
        Identificer 5. interkostalrum.
        Avancér nålen 2-3 cm efter pleuragennembrud.
        """
        result = validator.validate("pleuradræn", content)

        assert result.has_depth_guidance is True

    def test_detects_angle_guidance(self):
        """Should detect angle guidance when present."""
        from procedurewriter.pipeline.anatomical_requirements import (
            AnatomicalValidator,
        )

        validator = AnatomicalValidator()
        content = """
        Indsæt nålen i en vinkel på 45 grader til hudoverfladen.
        """
        result = validator.validate("pleuradræn", content)

        assert result.has_angle_guidance is True


class TestValidationResult:
    """Test ValidationResult dataclass."""

    def test_validation_result_has_required_fields(self):
        """ValidationResult should have is_valid and missing items."""
        from procedurewriter.pipeline.anatomical_requirements import ValidationResult

        result = ValidationResult(
            is_valid=False,
            missing_landmarks=["5. interkostalrum", "midtaksillærlinjen"],
            has_depth_guidance=False,
            has_angle_guidance=True,
            has_surface_anatomy=False,
            suggestions=["Add anatomical landmarks for pleural procedure"],
        )

        assert result.is_valid is False
        assert len(result.missing_landmarks) == 2
        assert result.has_depth_guidance is False
        assert len(result.suggestions) == 1

    def test_validation_result_has_score(self):
        """ValidationResult should have completeness score."""
        from procedurewriter.pipeline.anatomical_requirements import ValidationResult

        result = ValidationResult(
            is_valid=True,
            missing_landmarks=[],
            has_depth_guidance=True,
            has_angle_guidance=True,
            has_surface_anatomy=True,
            suggestions=[],
        )

        assert hasattr(result, "completeness_score")
        assert 0 <= result.completeness_score <= 1.0


class TestLandmarkMatching:
    """Test landmark detection in text."""

    def test_matches_exact_landmark(self):
        """Should match exact landmark name."""
        from procedurewriter.pipeline.anatomical_requirements import (
            AnatomicalValidator,
        )

        validator = AnatomicalValidator()
        content = "Identificer 5. interkostalrum."
        result = validator.validate("pleuradræn", content)

        # 5. interkostalrum should be found
        assert "5. interkostalrum" not in result.missing_landmarks

    def test_matches_landmark_alias(self):
        """Should match landmark aliases."""
        from procedurewriter.pipeline.anatomical_requirements import (
            AnatomicalValidator,
        )

        validator = AnatomicalValidator()
        content = "Identificer femte interkostalrum."  # Alias
        result = validator.validate("pleuradræn", content)

        # Should match via alias
        found_landmarks = [lm for lm in result.found_landmarks]
        assert any("interkostal" in lm.lower() for lm in found_landmarks)

    def test_case_insensitive_matching(self):
        """Should match landmarks case-insensitively."""
        from procedurewriter.pipeline.anatomical_requirements import (
            AnatomicalValidator,
        )

        validator = AnatomicalValidator()
        content = "Identificer MIDTAKSILLÆRLINJEN."
        result = validator.validate("pleuradræn", content)

        assert any("midtaksillær" in lm.lower() for lm in result.found_landmarks)


class TestLumbalpunkturValidation:
    """Test validation specific to lumbar puncture."""

    def test_validates_lumbalpunktur_landmarks(self):
        """Should validate lumbar puncture landmarks."""
        from procedurewriter.pipeline.anatomical_requirements import (
            AnatomicalValidator,
        )

        validator = AnatomicalValidator()
        content = """
        Positionér patienten i sideliggende eller siddende stilling.
        Palpér crista iliaca for at identificere L4 niveau.
        Vælg intervertebralrum L3-L4 eller L4-L5.
        Identificer processus spinosus.
        Indsæt nålen i midtlinjen med let kranial vinkel.
        Avancér til subarachnoidalrummet (typisk 4-7 cm hos voksne).
        """
        result = validator.validate("lumbalpunktur", content)

        assert result.is_valid is True
        assert result.has_depth_guidance is True

    def test_fails_lumbalpunktur_without_vertebral_level(self):
        """Should fail lumbar puncture without vertebral level."""
        from procedurewriter.pipeline.anatomical_requirements import (
            AnatomicalValidator,
        )

        validator = AnatomicalValidator()
        content = """
        Positionér patienten.
        Desinficer huden.
        Indsæt nålen.
        """
        result = validator.validate("lumbalpunktur", content)

        assert result.is_valid is False
        assert len(result.missing_landmarks) > 0


class TestNonInvasiveProcedures:
    """Test handling of non-invasive procedures."""

    def test_non_invasive_has_no_anatomical_requirements(self):
        """Non-invasive procedures should have relaxed requirements."""
        from procedurewriter.pipeline.anatomical_requirements import (
            AnatomicalRequirementsRegistry,
        )

        registry = AnatomicalRequirementsRegistry()

        # A made-up non-invasive procedure
        reqs = registry.get_requirements("blodtryksmaaling")

        # Should return None or minimal requirements
        if reqs is not None:
            assert reqs.procedure_type == "non_invasive"
            assert len(reqs.landmarks) == 0

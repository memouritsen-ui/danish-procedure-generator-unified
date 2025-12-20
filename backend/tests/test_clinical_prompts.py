"""Tests for clinical prompt engineering.

TDD Phase 4: LLM Prompt Engineering
Creates clinical-focused prompts that enforce anatomical content
and minimize workflow noise.
"""

from __future__ import annotations

import pytest


class TestClinicalPromptBuilder:
    """Test ClinicalPromptBuilder for creating clinical-focused prompts."""

    def test_builder_can_be_instantiated(self):
        """ClinicalPromptBuilder should be instantiable."""
        from procedurewriter.pipeline.clinical_prompts import ClinicalPromptBuilder

        builder = ClinicalPromptBuilder()
        assert builder is not None

    def test_has_build_system_prompt_method(self):
        """Builder should have build_system_prompt method."""
        from procedurewriter.pipeline.clinical_prompts import ClinicalPromptBuilder

        builder = ClinicalPromptBuilder()
        assert hasattr(builder, "build_system_prompt")
        assert callable(builder.build_system_prompt)

    def test_build_system_prompt_returns_string(self):
        """build_system_prompt should return a string."""
        from procedurewriter.pipeline.clinical_prompts import ClinicalPromptBuilder

        builder = ClinicalPromptBuilder()
        prompt = builder.build_system_prompt("pleuradræn")

        assert isinstance(prompt, str)
        assert len(prompt) > 100  # Should be substantial

    def test_system_prompt_is_in_danish(self):
        """System prompt should be in Danish."""
        from procedurewriter.pipeline.clinical_prompts import ClinicalPromptBuilder

        builder = ClinicalPromptBuilder()
        prompt = builder.build_system_prompt("pleuradræn")

        # Check for Danish keywords
        assert "dansk" in prompt.lower() or "medicinsk" in prompt.lower()


class TestPromptForbiddenContent:
    """Test that prompts explicitly forbid workflow content."""

    def test_forbids_phone_numbers(self):
        """Prompt should forbid phone numbers."""
        from procedurewriter.pipeline.clinical_prompts import ClinicalPromptBuilder

        builder = ClinicalPromptBuilder()
        prompt = builder.build_system_prompt("pleuradræn")

        # Should contain instruction to avoid phone numbers
        assert "telefon" in prompt.lower() or "tlf" in prompt.lower()

    def test_forbids_bagvagt_references(self):
        """Prompt should forbid bagvagt/forvagt references."""
        from procedurewriter.pipeline.clinical_prompts import ClinicalPromptBuilder

        builder = ClinicalPromptBuilder()
        prompt = builder.build_system_prompt("pleuradræn")

        assert "bagvagt" in prompt.lower()

    def test_forbids_lokal_retningslinje(self):
        """Prompt should forbid 'følg lokal retningslinje' pattern."""
        from procedurewriter.pipeline.clinical_prompts import ClinicalPromptBuilder

        builder = ClinicalPromptBuilder()
        prompt = builder.build_system_prompt("pleuradræn")

        assert "lokal retningslinje" in prompt.lower()

    def test_forbids_rollefordeling(self):
        """Prompt should forbid rollefordeling content."""
        from procedurewriter.pipeline.clinical_prompts import ClinicalPromptBuilder

        builder = ClinicalPromptBuilder()
        prompt = builder.build_system_prompt("pleuradræn")

        assert "rollefordeling" in prompt.lower() or "teamstruktur" in prompt.lower()

    def test_has_explicit_forbidden_section(self):
        """Prompt should have explicit 'DU SKRIVER IKKE' section."""
        from procedurewriter.pipeline.clinical_prompts import ClinicalPromptBuilder

        builder = ClinicalPromptBuilder()
        prompt = builder.build_system_prompt("pleuradræn")

        assert "SKRIVER IKKE" in prompt or "skriver ikke" in prompt.lower()


class TestPromptRequiredContent:
    """Test that prompts enforce required clinical content."""

    def test_requires_anatomical_landmarks(self):
        """Prompt should require anatomical landmarks."""
        from procedurewriter.pipeline.clinical_prompts import ClinicalPromptBuilder

        builder = ClinicalPromptBuilder()
        prompt = builder.build_system_prompt("pleuradræn")

        assert "anatomisk" in prompt.lower() or "landmark" in prompt.lower()

    def test_requires_depth_guidance(self):
        """Prompt should require depth guidance."""
        from procedurewriter.pipeline.clinical_prompts import ClinicalPromptBuilder

        builder = ClinicalPromptBuilder()
        prompt = builder.build_system_prompt("pleuradræn")

        assert "dybde" in prompt.lower() or "cm" in prompt.lower()

    def test_requires_angle_guidance(self):
        """Prompt should require angle guidance."""
        from procedurewriter.pipeline.clinical_prompts import ClinicalPromptBuilder

        builder = ClinicalPromptBuilder()
        prompt = builder.build_system_prompt("pleuradræn")

        assert "vinkel" in prompt.lower() or "grader" in prompt.lower()

    def test_requires_evidence_based_content(self):
        """Prompt should require evidence-based content."""
        from procedurewriter.pipeline.clinical_prompts import ClinicalPromptBuilder

        builder = ClinicalPromptBuilder()
        prompt = builder.build_system_prompt("pleuradræn")

        assert "evidens" in prompt.lower() or "kilde" in prompt.lower()

    def test_has_explicit_required_section(self):
        """Prompt should have explicit 'DU SKRIVER' section."""
        from procedurewriter.pipeline.clinical_prompts import ClinicalPromptBuilder

        builder = ClinicalPromptBuilder()
        prompt = builder.build_system_prompt("pleuradræn")

        # Should have a section about what TO write
        assert "DU SKRIVER" in prompt or "du skriver" in prompt.lower()


class TestProcedureSpecificPrompts:
    """Test procedure-specific prompt generation."""

    def test_pleuradraen_includes_specific_landmarks(self):
        """Pleuradræn prompt should mention specific landmarks."""
        from procedurewriter.pipeline.clinical_prompts import ClinicalPromptBuilder

        builder = ClinicalPromptBuilder()
        prompt = builder.build_system_prompt("pleuradræn")

        # Should mention key landmarks
        assert "interkostalrum" in prompt.lower() or "triangle" in prompt.lower()

    def test_lumbalpunktur_includes_specific_landmarks(self):
        """Lumbalpunktur prompt should mention specific landmarks."""
        from procedurewriter.pipeline.clinical_prompts import ClinicalPromptBuilder

        builder = ClinicalPromptBuilder()
        prompt = builder.build_system_prompt("lumbalpunktur")

        # Should mention vertebral levels or crista iliaca
        assert "l3" in prompt.lower() or "l4" in prompt.lower() or "crista" in prompt.lower()

    def test_unknown_procedure_gets_generic_prompt(self):
        """Unknown procedure should get generic clinical prompt."""
        from procedurewriter.pipeline.clinical_prompts import ClinicalPromptBuilder

        builder = ClinicalPromptBuilder()
        prompt = builder.build_system_prompt("unknown_procedure_xyz")

        # Should still have clinical focus
        assert "anatomisk" in prompt.lower() or "teknik" in prompt.lower()
        assert len(prompt) > 100


class TestPromptEnhancer:
    """Test PromptEnhancer for enhancing existing prompts."""

    def test_enhancer_can_be_instantiated(self):
        """PromptEnhancer should be instantiable."""
        from procedurewriter.pipeline.clinical_prompts import PromptEnhancer

        enhancer = PromptEnhancer()
        assert enhancer is not None

    def test_has_enhance_method(self):
        """PromptEnhancer should have enhance method."""
        from procedurewriter.pipeline.clinical_prompts import PromptEnhancer

        enhancer = PromptEnhancer()
        assert hasattr(enhancer, "enhance")
        assert callable(enhancer.enhance)

    def test_enhance_adds_clinical_focus(self):
        """enhance should add clinical focus to generic prompt."""
        from procedurewriter.pipeline.clinical_prompts import PromptEnhancer

        enhancer = PromptEnhancer()
        original = "Du er en medicinsk forfatter."
        enhanced = enhancer.enhance(original, "pleuradræn")

        assert len(enhanced) > len(original)
        # Should add clinical constraints
        assert "SKRIVER IKKE" in enhanced or "skriver ikke" in enhanced.lower()

    def test_enhance_preserves_original_content(self):
        """enhance should preserve the original prompt content."""
        from procedurewriter.pipeline.clinical_prompts import PromptEnhancer

        enhancer = PromptEnhancer()
        original = "Du er en medicinsk forfatter med ekspertise i akutmedicin."
        enhanced = enhancer.enhance(original, "pleuradræn")

        # Original content should still be there
        assert "medicinsk forfatter" in enhanced

    def test_enhance_adds_procedure_specific_guidance(self):
        """enhance should add procedure-specific guidance."""
        from procedurewriter.pipeline.clinical_prompts import PromptEnhancer

        enhancer = PromptEnhancer()
        original = "Skriv en procedure."
        enhanced = enhancer.enhance(original, "pleuradræn")

        # Should have procedure-specific content
        assert "interkostalrum" in enhanced.lower() or "thorax" in enhanced.lower()


class TestReplacementInstructions:
    """Test instructions for replacing workflow content."""

    def test_provides_replacement_for_lokal_retningslinje(self):
        """Prompt should provide replacement for 'følg lokal retningslinje'."""
        from procedurewriter.pipeline.clinical_prompts import ClinicalPromptBuilder

        builder = ClinicalPromptBuilder()
        prompt = builder.build_system_prompt("pleuradræn")

        # Should have instruction about what to do instead
        has_replacement = (
            "international" in prompt.lower() or
            "evidens" in prompt.lower() or
            "bedste praksis" in prompt.lower()
        )
        assert has_replacement

    def test_provides_replacement_for_ring_bagvagt(self):
        """Prompt should suggest replacement for call instructions."""
        from procedurewriter.pipeline.clinical_prompts import ClinicalPromptBuilder

        builder = ClinicalPromptBuilder()
        prompt = builder.build_system_prompt("pleuradræn")

        # Should mention complications or escalation criteria
        has_replacement = (
            "komplikation" in prompt.lower() or
            "eskalering" in prompt.lower() or
            "assistance" in prompt.lower()
        )
        assert has_replacement


class TestPromptSections:
    """Test prompt section structure."""

    def test_has_role_definition(self):
        """Prompt should define the role clearly."""
        from procedurewriter.pipeline.clinical_prompts import ClinicalPromptBuilder

        builder = ClinicalPromptBuilder()
        prompt = builder.build_system_prompt("pleuradræn")

        # Should have role definition
        assert "forfatter" in prompt.lower() or "ekspert" in prompt.lower()

    def test_has_output_format_section(self):
        """Prompt should specify output format."""
        from procedurewriter.pipeline.clinical_prompts import ClinicalPromptBuilder

        builder = ClinicalPromptBuilder()
        prompt = builder.build_system_prompt("pleuradræn")

        # Should mention formatting
        assert "format" in prompt.lower() or "struktur" in prompt.lower()


class TestClinicalPromptConstants:
    """Test clinical prompt constants and templates."""

    def test_forbidden_patterns_constant_exists(self):
        """FORBIDDEN_PATTERNS constant should exist."""
        from procedurewriter.pipeline.clinical_prompts import FORBIDDEN_PATTERNS

        assert isinstance(FORBIDDEN_PATTERNS, list)
        assert len(FORBIDDEN_PATTERNS) >= 5

    def test_required_elements_constant_exists(self):
        """REQUIRED_ELEMENTS constant should exist."""
        from procedurewriter.pipeline.clinical_prompts import REQUIRED_ELEMENTS

        assert isinstance(REQUIRED_ELEMENTS, list)
        assert len(REQUIRED_ELEMENTS) >= 3

    def test_clinical_system_prompt_constant_exists(self):
        """CLINICAL_SYSTEM_PROMPT constant should exist."""
        from procedurewriter.pipeline.clinical_prompts import CLINICAL_SYSTEM_PROMPT

        assert isinstance(CLINICAL_SYSTEM_PROMPT, str)
        assert len(CLINICAL_SYSTEM_PROMPT) > 200


class TestPromptIntegrationWithAnatomical:
    """Test integration with anatomical requirements."""

    def test_prompt_includes_anatomical_requirements(self):
        """Prompt should include procedure-specific anatomical requirements."""
        from procedurewriter.pipeline.clinical_prompts import ClinicalPromptBuilder
        from procedurewriter.pipeline.anatomical_requirements import (
            AnatomicalRequirementsRegistry,
        )

        builder = ClinicalPromptBuilder()
        prompt = builder.build_system_prompt("pleuradræn")

        registry = AnatomicalRequirementsRegistry()
        reqs = registry.get_requirements("pleuradræn")

        # Prompt should mention at least one landmark
        has_landmark = any(
            lm.name.lower() in prompt.lower() or
            any(alias.lower() in prompt.lower() for alias in lm.aliases)
            for lm in reqs.landmarks
        )
        assert has_landmark

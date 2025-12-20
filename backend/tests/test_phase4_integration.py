"""Integration tests for Phase 4: LLM Prompt Engineering.

Tests the integration of clinical prompts with Phase 2-3 components.
"""

from __future__ import annotations

import pytest


class TestPromptWithWorkflowFilter:
    """Test that prompts align with WorkflowFilter patterns."""

    def test_forbidden_patterns_match_workflow_filter(self):
        """Forbidden patterns in prompts should match WorkflowFilter patterns."""
        from procedurewriter.pipeline.workflow_filter import WorkflowFilter

        wf = WorkflowFilter()

        # Key workflow patterns that prompt forbids and filter detects
        workflow_examples = [
            "Ring til bagvagt ved komplikationer.",
            "Følg lokal retningslinje for proceduren.",
            "Aftal rollefordeling med teamet.",
            "Kontakt forvagten først.",
        ]

        for example in workflow_examples:
            clinical, workflow = wf.filter_workflow_content(example)
            assert workflow.strip(), f"WorkflowFilter should detect: {example}"

    def test_prompt_guides_away_from_filtered_content(self):
        """Prompt should instruct LLM to avoid content WorkflowFilter removes."""
        from procedurewriter.pipeline.clinical_prompts import ClinicalPromptBuilder

        builder = ClinicalPromptBuilder()
        prompt = builder.build_system_prompt("pleuradræn")

        # Key workflow patterns should be mentioned in prompt as things to avoid
        workflow_keywords = ["bagvagt", "retningslinje", "telefon", "rollefordeling"]
        mentioned = sum(1 for kw in workflow_keywords if kw in prompt.lower())

        assert mentioned >= 2, "Prompt should mention key workflow patterns to avoid"


class TestPromptWithAnatomicalValidator:
    """Test that prompts align with AnatomicalValidator requirements."""

    def test_prompt_includes_required_landmarks(self):
        """Prompt should include landmarks that validator checks for."""
        from procedurewriter.pipeline.clinical_prompts import ClinicalPromptBuilder
        from procedurewriter.pipeline.anatomical_requirements import (
            AnatomicalRequirementsRegistry,
        )

        builder = ClinicalPromptBuilder()
        registry = AnatomicalRequirementsRegistry()

        for procedure in ["pleuradræn", "lumbalpunktur"]:
            prompt = builder.build_system_prompt(procedure)
            reqs = registry.get_requirements(procedure)

            # At least one landmark should be mentioned
            landmarks_mentioned = sum(
                1 for lm in reqs.landmarks
                if lm.name.lower() in prompt.lower()
                or any(alias.lower() in prompt.lower() for alias in lm.aliases)
            )

            assert landmarks_mentioned >= 1, (
                f"Prompt for {procedure} should mention at least one required landmark"
            )

    def test_prompt_requires_depth_when_validator_does(self):
        """Prompt should require depth guidance when validator checks for it."""
        from procedurewriter.pipeline.clinical_prompts import ClinicalPromptBuilder
        from procedurewriter.pipeline.anatomical_requirements import (
            AnatomicalRequirementsRegistry,
        )

        builder = ClinicalPromptBuilder()
        registry = AnatomicalRequirementsRegistry()

        # Check procedures that require depth
        for procedure in ["pleuradræn", "lumbalpunktur"]:
            prompt = builder.build_system_prompt(procedure)
            reqs = registry.get_requirements(procedure)

            if reqs.requires_depth_guidance:
                assert "dybde" in prompt.lower() or "cm" in prompt.lower(), (
                    f"Prompt for {procedure} should mention depth guidance"
                )

    def test_prompt_requires_angle_when_validator_does(self):
        """Prompt should require angle guidance when validator checks for it."""
        from procedurewriter.pipeline.clinical_prompts import ClinicalPromptBuilder
        from procedurewriter.pipeline.anatomical_requirements import (
            AnatomicalRequirementsRegistry,
        )

        builder = ClinicalPromptBuilder()
        registry = AnatomicalRequirementsRegistry()

        for procedure in ["pleuradræn", "lumbalpunktur"]:
            prompt = builder.build_system_prompt(procedure)
            reqs = registry.get_requirements(procedure)

            if reqs.requires_angle_guidance:
                assert "vinkel" in prompt.lower() or "grader" in prompt.lower(), (
                    f"Prompt for {procedure} should mention angle guidance"
                )


class TestPromptEnhancerIntegration:
    """Test PromptEnhancer integration with existing prompts."""

    def test_enhanced_prompt_passes_validation(self):
        """Content following enhanced prompt should pass anatomical validation."""
        from procedurewriter.pipeline.clinical_prompts import PromptEnhancer

        enhancer = PromptEnhancer()

        # Simple original prompt
        original = "Du er en medicinsk forfatter."
        enhanced = enhancer.enhance(original, "pleuradræn")

        # Enhanced prompt should have clinical constraints
        assert "SKRIVER IKKE" in enhanced
        assert "bagvagt" in enhanced.lower()
        assert "interkostalrum" in enhanced.lower() or "triangle" in enhanced.lower()

    def test_enhancer_works_with_complex_prompts(self):
        """Enhancer should work with complex multi-paragraph prompts."""
        from procedurewriter.pipeline.clinical_prompts import PromptEnhancer

        enhancer = PromptEnhancer()

        complex_prompt = """
        Du er en erfaren overlæge med speciale i akutmedicin.
        Du har 20 års erfaring med invasive procedurer.
        Din opgave er at skrive præcis, reproducerbar dokumentation.

        TONE:
        - Professionel og klar
        - Undgå jargon
        - Fokuser på sikkerhed
        """

        enhanced = enhancer.enhance(complex_prompt, "lumbalpunktur")

        # Original content preserved
        assert "erfaren overlæge" in enhanced
        assert "akutmedicin" in enhanced

        # Clinical constraints added
        assert "SKRIVER IKKE" in enhanced
        assert "L3" in enhanced or "L4" in enhanced or "crista" in enhanced.lower()


class TestEndToEndPromptFlow:
    """End-to-end tests for prompt flow."""

    def test_prompt_guidance_produces_validatable_content(self):
        """Following prompt guidance should produce content that passes validation."""
        from procedurewriter.pipeline.clinical_prompts import ClinicalPromptBuilder
        from procedurewriter.pipeline.anatomical_requirements import AnatomicalValidator
        from procedurewriter.pipeline.workflow_filter import WorkflowFilter

        # Build prompt
        builder = ClinicalPromptBuilder()
        prompt = builder.build_system_prompt("pleuradræn")

        # Simulated LLM output following prompt guidance
        simulated_output = """
        Positionér patienten i lateral decubitus med syg side opad.
        Palpér thoraxvæggen og identificer 5. interkostalrum i midtaksillærlinjen.
        Marker punktursted inden for triangle of safety.
        Desinficér området og anlæg steril afdækning.
        Infiltrér med lokalbedøvelse til og med pleura parietalis.
        Indsæt nålen i en vinkel på 45 grader over øvre ribbenrand.
        Avancér nålen 2-3 cm indtil pleurahulen gennembrytes.
        Bekræft position med aspiration af luft eller væske.
        """

        # Validate with WorkflowFilter (should have minimal workflow)
        wf = WorkflowFilter()
        clinical, workflow = wf.filter_workflow_content(simulated_output)
        assert len(workflow.strip()) == 0, "Output should have no workflow content"

        # Validate with AnatomicalValidator (should pass)
        validator = AnatomicalValidator()
        result = validator.validate("pleuradræn", clinical)

        assert result.is_valid is True
        assert result.has_depth_guidance is True
        assert result.has_angle_guidance is True

    def test_poor_output_fails_validation(self):
        """Output ignoring prompt guidance should fail validation."""
        from procedurewriter.pipeline.anatomical_requirements import AnatomicalValidator
        from procedurewriter.pipeline.workflow_filter import WorkflowFilter

        # Bad output that ignores prompt guidance
        bad_output = """
        Forbered proceduren ifølge afdelingens protokol.
        Ring til bagvagt ved behov for assistance.
        Aftal rollefordeling med teamet.
        Indsæt drænet.
        Følg lokal retningslinje for efterpleje.
        Kontakt bagvagten ved komplikationer.
        """

        # WorkflowFilter should flag most of this
        wf = WorkflowFilter()
        clinical, workflow = wf.filter_workflow_content(bad_output)

        # Workflow should be substantial
        assert len(workflow) > len(clinical)

        # AnatomicalValidator should fail what remains
        validator = AnatomicalValidator()
        result = validator.validate("pleuradræn", clinical)

        assert result.is_valid is False


class TestAllPhasesIntegration:
    """Test integration across all phases."""

    def test_complete_pipeline_with_prompt_guidance(self):
        """Test complete pipeline: prompt → filter → validate."""
        from procedurewriter.pipeline.clinical_prompts import ClinicalPromptBuilder
        from procedurewriter.pipeline.workflow_filter import WorkflowFilter
        from procedurewriter.pipeline.deduplication import RepetitionDetector
        from procedurewriter.pipeline.anatomical_requirements import AnatomicalValidator

        # Phase 4: Generate prompt
        builder = ClinicalPromptBuilder()
        prompt = builder.build_system_prompt("lumbalpunktur")

        # Simulated good output following prompt
        good_output = [
            "Positionér patienten siddende med maksimal lumbalkyfose.",
            "Palpér crista iliaca for at identificere L4 niveau.",
            "Marker intervertebralrum L3-L4 i midtlinjen.",
            "Desinficér og afdæk sterilt.",
            "Infiltrér med lokalbedøvelse.",
            "Indsæt spinalnålen med let kranial vinkel i midtlinjen.",
            "Avancér langsomt 4-7 cm til subarachnoidalrummet.",
            "Bekræft position med liquorflow i mandrin.",
        ]

        # Phase 2: Filter workflow
        wf = WorkflowFilter()
        filtered = []
        for text in good_output:
            clinical, _ = wf.filter_workflow_content(text)
            if clinical.strip():
                filtered.append(clinical)

        # Phase 2: Deduplicate
        rd = RepetitionDetector()
        deduped = rd.deduplicate(filtered)

        # Should have all content (no workflow, no duplicates)
        assert len(deduped) == len(good_output)

        # Phase 3: Validate anatomical content
        validator = AnatomicalValidator()
        combined = " ".join(deduped)
        result = validator.validate("lumbalpunktur", combined)

        assert result.is_valid is True
        assert result.completeness_score >= 0.8

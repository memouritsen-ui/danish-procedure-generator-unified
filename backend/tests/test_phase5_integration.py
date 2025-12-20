"""Integration tests for Phase 5: Pipeline Integration.

Tests the integration of PipelineProcessor with all Phase 1-4 components.
"""

from __future__ import annotations

import pytest


class TestPipelineProcessorWithWorkflowFilter:
    """Test PipelineProcessor integration with WorkflowFilter."""

    def test_processor_uses_workflow_filter(self):
        """Processor should filter workflow content using WorkflowFilter patterns."""
        from procedurewriter.pipeline.processor import PipelineProcessor
        from procedurewriter.pipeline.workflow_filter import WorkflowFilter

        processor = PipelineProcessor()
        wf = WorkflowFilter()

        # Content with known workflow patterns
        content = """
        Identificer 5. interkostalrum.
        Ring til bagvagt ved komplikationer.
        Marker triangle of safety.
        Følg lokal retningslinje for efterpleje.
        """

        result = processor.process("pleuradræn", content)

        # Same workflow items should be filtered
        for pattern_text in ["Ring til bagvagt", "Følg lokal retningslinje"]:
            clinical, workflow = wf.filter_workflow_content(pattern_text)
            assert workflow.strip(), f"WorkflowFilter should detect: {pattern_text}"
            assert pattern_text.lower() not in result.filtered_content.lower()

    def test_processor_tracks_workflow_correctly(self):
        """Processor's workflow_removed should match WorkflowFilter behavior."""
        from procedurewriter.pipeline.processor import PipelineProcessor

        processor = PipelineProcessor()

        content = """
        Ring til bagvagt.
        Identificer landemærke.
        Kontakt forvagt.
        """

        result = processor.process("pleuradræn", content)

        # Should track both workflow items
        workflow_text = " ".join(result.workflow_removed).lower()
        assert "bagvagt" in workflow_text
        assert "forvagt" in workflow_text


class TestPipelineProcessorWithDeduplication:
    """Test PipelineProcessor integration with RepetitionDetector."""

    def test_processor_uses_deduplication(self):
        """Processor should deduplicate using RepetitionDetector."""
        from procedurewriter.pipeline.processor import PipelineProcessor
        from procedurewriter.pipeline.deduplication import RepetitionDetector

        processor = PipelineProcessor()
        rd = RepetitionDetector()

        # Content with exact duplicates
        content = """
        Marker punkturstedet.
        Marker punkturstedet.
        Marker punkturstedet.
        Indsæt nålen.
        """

        result = processor.process("pleuradræn", content)

        # Deduplication should reduce to unique items
        count = result.filtered_content.lower().count("marker punkturstedet")
        assert count == 1, "Exact duplicates should be removed"


class TestPipelineProcessorWithAnatomicalValidator:
    """Test PipelineProcessor integration with AnatomicalValidator."""

    def test_processor_validates_anatomical_content(self):
        """Processor should use AnatomicalValidator for validation."""
        from procedurewriter.pipeline.processor import PipelineProcessor
        from procedurewriter.pipeline.anatomical_requirements import (
            AnatomicalValidator,
        )

        processor = PipelineProcessor()
        validator = AnatomicalValidator()

        # Good content with anatomical landmarks
        good_content = """
        Identificer 5. interkostalrum i midtaksillærlinjen.
        Marker triangle of safety.
        Indsæt nålen i 45 graders vinkel.
        Avancér 2-3 cm.
        """

        result = processor.process("pleuradræn", good_content)

        # Validation should pass
        assert result.anatomical_validation.is_valid is True
        assert result.anatomical_validation.has_depth_guidance is True
        assert result.anatomical_validation.has_angle_guidance is True

    def test_processor_validation_matches_standalone_validator(self):
        """Processor validation should match standalone validator."""
        from procedurewriter.pipeline.processor import PipelineProcessor
        from procedurewriter.pipeline.anatomical_requirements import (
            AnatomicalValidator,
        )

        processor = PipelineProcessor()
        validator = AnatomicalValidator()

        content = "Identificer 5. interkostalrum."

        result = processor.process("pleuradræn", content)
        standalone = validator.validate("pleuradræn", content)

        # Both should identify same landmarks
        assert result.anatomical_validation.has_depth_guidance == standalone.has_depth_guidance


class TestPipelineProcessorWithPromptEnhancer:
    """Test PipelineProcessor integration with PromptEnhancer."""

    def test_processor_enhance_prompt_uses_prompt_enhancer(self):
        """Processor.enhance_prompt should use PromptEnhancer."""
        from procedurewriter.pipeline.processor import PipelineProcessor
        from procedurewriter.pipeline.clinical_prompts import PromptEnhancer

        processor = PipelineProcessor()
        enhancer = PromptEnhancer()

        original = "Du er en medicinsk forfatter."

        processor_enhanced = processor.enhance_prompt(original, "pleuradræn")
        standalone_enhanced = enhancer.enhance(original, "pleuradræn")

        # Should produce identical results
        assert processor_enhanced == standalone_enhanced


class TestPipelineProcessorQualityIntegration:
    """Test quality scoring integration."""

    def test_quality_score_reflects_workflow_removal(self):
        """Quality score should be lower when content is mostly workflow."""
        from procedurewriter.pipeline.processor import PipelineProcessor

        processor = PipelineProcessor()

        # Content that's mostly workflow
        workflow_heavy = """
        Ring til bagvagt.
        Kontakt forvagt.
        Følg lokal retningslinje.
        Aftal rollefordeling.
        """

        # Content that's mostly clinical
        clinical = """
        Identificer 5. interkostalrum i midtaksillærlinjen.
        Marker triangle of safety.
        Indsæt nålen i 45 graders vinkel.
        Avancér 2-3 cm til pleurahulen.
        """

        workflow_result = processor.process("pleuradræn", workflow_heavy)
        clinical_result = processor.process("pleuradræn", clinical)

        # Clinical content should score higher
        assert clinical_result.quality_score > workflow_result.quality_score

    def test_quality_score_reflects_anatomical_completeness(self):
        """Quality score should be higher with complete anatomical content."""
        from procedurewriter.pipeline.processor import PipelineProcessor

        processor = PipelineProcessor()

        # Minimal content
        minimal = "Indsæt dræn."

        # Complete content
        complete = """
        Identificer 5. interkostalrum i midtaksillærlinjen.
        Marker triangle of safety.
        Indsæt nålen i 45 graders vinkel.
        Avancér 2-3 cm til pleurahulen.
        """

        minimal_result = processor.process("pleuradræn", minimal)
        complete_result = processor.process("pleuradræn", complete)

        # Complete content should score higher
        assert complete_result.quality_score > minimal_result.quality_score


class TestPipelineProcessorSuggestionsIntegration:
    """Test suggestions generation integration."""

    def test_suggestions_reflect_missing_landmarks(self):
        """Suggestions should mention missing anatomical landmarks."""
        from procedurewriter.pipeline.processor import PipelineProcessor

        processor = PipelineProcessor()

        # Content missing landmarks
        content = "Indsæt dræn."

        result = processor.process("pleuradræn", content)

        # Should have suggestions about missing landmarks
        suggestion_text = " ".join(result.suggestions).lower()
        assert "landemærke" in suggestion_text or "landmark" in suggestion_text

    def test_suggestions_reflect_missing_depth(self):
        """Suggestions should mention missing depth guidance."""
        from procedurewriter.pipeline.processor import PipelineProcessor

        processor = PipelineProcessor()

        # Content missing depth
        content = "Identificer 5. interkostalrum."

        result = processor.process("pleuradræn", content)

        # Should have suggestions about depth
        suggestion_text = " ".join(result.suggestions).lower()
        has_depth_suggestion = "dybde" in suggestion_text or "cm" in suggestion_text
        assert has_depth_suggestion


class TestPipelineProcessorSectionsIntegration:
    """Test section processing integration."""

    def test_process_sections_filters_workflow_per_section(self):
        """process_sections should filter workflow from each section."""
        from procedurewriter.pipeline.processor import PipelineProcessor

        processor = PipelineProcessor()

        sections = {
            "Indikationer": ["Pneumothorax", "Pleuraeffusion"],
            "Fremgangsmåde": [
                "Identificer 5. interkostalrum.",
                "Ring til bagvagt ved komplikationer.",
                "Indsæt dræn.",
            ],
        }

        result = processor.process_sections("pleuradræn", sections)

        # Workflow should be removed from Fremgangsmåde
        fremgang = result.filtered_sections.get("Fremgangsmåde", [])
        assert not any("bagvagt" in item.lower() for item in fremgang)

        # Clinical content should remain
        assert any("interkostalrum" in item.lower() for item in fremgang)

    def test_process_sections_validates_combined_content(self):
        """process_sections should validate all content combined."""
        from procedurewriter.pipeline.processor import PipelineProcessor

        processor = PipelineProcessor()

        sections = {
            "Teknik": [
                "Identificer 5. interkostalrum.",
                "Marker triangle of safety.",
                "Indsæt i 45 graders vinkel.",
                "Avancér 2-3 cm.",
            ],
        }

        result = processor.process_sections("pleuradræn", sections)

        # Combined content should pass validation
        assert result.anatomical_validation.is_valid is True


class TestEndToEndPipelineIntegration:
    """End-to-end tests for complete pipeline integration."""

    def test_complete_pipeline_good_content(self):
        """Test complete pipeline with good clinical content."""
        from procedurewriter.pipeline.processor import PipelineProcessor

        processor = PipelineProcessor()

        # Realistic good procedure content
        content = """
        Positionér patienten i lateral decubitus med syg side opad.
        Palpér thoraxvæggen og identificer 5. interkostalrum.
        Marker punktursted i midtaksillærlinjen.
        Identificer triangle of safety.
        Desinficér og drapér sterilt.
        Infiltrér med lokalbedøvelse.
        Indsæt nålen i en vinkel på 45 grader over øvre ribbenrand.
        Avancér nålen 2-3 cm til pleurahulen gennembrytes.
        """

        result = processor.process("pleuradræn", content)

        # Should pass all quality checks
        assert result.anatomical_validation.is_valid is True
        assert result.quality_score >= 0.7
        assert len(result.workflow_removed) == 0

    def test_complete_pipeline_poor_content(self):
        """Test complete pipeline with poor workflow-heavy content."""
        from procedurewriter.pipeline.processor import PipelineProcessor

        processor = PipelineProcessor()

        # Realistic poor content
        content = """
        Forbered proceduren ifølge afdelingens protokol.
        Ring til bagvagt ved behov for assistance.
        Aftal rollefordeling med teamet.
        Indsæt drænet.
        Følg lokal retningslinje for efterpleje.
        Kontakt bagvagt ved komplikationer.
        """

        result = processor.process("pleuradræn", content)

        # Should fail quality checks
        assert result.anatomical_validation.is_valid is False
        assert result.quality_score < 0.5
        assert len(result.workflow_removed) >= 3
        assert len(result.suggestions) > 0

    def test_pipeline_transforms_mixed_content(self):
        """Test that pipeline correctly transforms mixed content."""
        from procedurewriter.pipeline.processor import PipelineProcessor

        processor = PipelineProcessor()

        # Mixed clinical and workflow content
        content = """
        Identificer 5. interkostalrum i midtaksillærlinjen.
        Ring til bagvagt ved komplikationer.
        Marker triangle of safety.
        Følg lokal retningslinje for sterilteknik.
        Indsæt nålen i 45 graders vinkel.
        Aftal rollefordeling med teamet.
        Avancér 2-3 cm til pleurahulen.
        """

        result = processor.process("pleuradræn", content)

        # Clinical content should be preserved
        assert "interkostalrum" in result.filtered_content.lower()
        assert "triangle" in result.filtered_content.lower()
        assert "vinkel" in result.filtered_content.lower()

        # Workflow content should be removed
        assert "bagvagt" not in result.filtered_content.lower()
        assert "lokal retningslinje" not in result.filtered_content.lower()
        assert "rollefordeling" not in result.filtered_content.lower()


class TestPhase5ModulesIntegration:
    """Test that all modules integrate correctly."""

    def test_all_phase_components_available(self):
        """All Phase 1-4 components should be accessible via processor."""
        from procedurewriter.pipeline.processor import PipelineProcessor

        processor = PipelineProcessor()

        # Processor should have all internal components
        assert hasattr(processor, "_workflow_filter")
        assert hasattr(processor, "_deduplicator")
        assert hasattr(processor, "_validator")
        assert hasattr(processor, "_prompt_enhancer")
        assert hasattr(processor, "_scorer")

    def test_processor_components_are_correct_types(self):
        """Processor components should be correct types."""
        from procedurewriter.pipeline.processor import PipelineProcessor
        from procedurewriter.pipeline.workflow_filter import WorkflowFilter
        from procedurewriter.pipeline.deduplication import RepetitionDetector
        from procedurewriter.pipeline.anatomical_requirements import AnatomicalValidator
        from procedurewriter.pipeline.clinical_prompts import PromptEnhancer

        processor = PipelineProcessor()

        assert isinstance(processor._workflow_filter, WorkflowFilter)
        assert isinstance(processor._deduplicator, RepetitionDetector)
        assert isinstance(processor._validator, AnatomicalValidator)
        assert isinstance(processor._prompt_enhancer, PromptEnhancer)

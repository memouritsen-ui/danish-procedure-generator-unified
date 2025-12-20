"""Tests for pipeline processor integration.

TDD Phase 5: Pipeline Integration
Integrates all Phase 1-4 components into a unified processing flow.
"""

from __future__ import annotations

import re

import pytest


class TestPipelineProcessor:
    """Test PipelineProcessor for integrating all phases."""

    def test_processor_can_be_instantiated(self):
        """PipelineProcessor should be instantiable."""
        from procedurewriter.pipeline.processor import PipelineProcessor

        processor = PipelineProcessor()
        assert processor is not None

    def test_has_process_method(self):
        """Processor should have process method."""
        from procedurewriter.pipeline.processor import PipelineProcessor

        processor = PipelineProcessor()
        assert hasattr(processor, "process")
        assert callable(processor.process)

    def test_process_returns_result(self):
        """process should return ProcessingResult."""
        from procedurewriter.pipeline.processor import (
            PipelineProcessor,
            ProcessingResult,
        )

        processor = PipelineProcessor()
        result = processor.process(
            procedure_name="pleuradræn",
            content="Identificer 5. interkostalrum i midtaksillærlinjen.",
        )

        assert isinstance(result, ProcessingResult)

    def test_result_has_required_fields(self):
        """ProcessingResult should have all required fields."""
        from procedurewriter.pipeline.processor import (
            PipelineProcessor,
            ProcessingResult,
        )

        processor = PipelineProcessor()
        result = processor.process(
            procedure_name="pleuradræn",
            content="Test content.",
        )

        assert hasattr(result, "filtered_content")
        assert hasattr(result, "workflow_removed")
        assert hasattr(result, "anatomical_validation")
        assert hasattr(result, "quality_score")
        assert hasattr(result, "suggestions")


class TestPipelineProcessorFiltering:
    """Test that processor applies workflow filtering."""

    def test_filters_workflow_content(self):
        """Processor should filter out workflow content."""
        from procedurewriter.pipeline.processor import PipelineProcessor

        processor = PipelineProcessor()

        content = """
        Identificer 5. interkostalrum i midtaksillærlinjen.
        Ring til bagvagt ved komplikationer.
        Indsæt dræn i triangle of safety.
        Følg lokal retningslinje for efterpleje.
        """

        result = processor.process("pleuradræn", content)

        # Workflow content should be removed
        assert "bagvagt" not in result.filtered_content.lower()
        assert "lokal retningslinje" not in result.filtered_content.lower()

        # Clinical content preserved
        assert "interkostalrum" in result.filtered_content.lower()
        assert "triangle" in result.filtered_content.lower()

    def test_tracks_removed_workflow(self):
        """Processor should track what workflow was removed."""
        from procedurewriter.pipeline.processor import PipelineProcessor

        processor = PipelineProcessor()

        content = """
        Indsæt dræn.
        Ring til bagvagt.
        Følg lokal retningslinje.
        """

        result = processor.process("pleuradræn", content)

        assert len(result.workflow_removed) >= 2
        assert any("bagvagt" in w.lower() for w in result.workflow_removed)


class TestPipelineProcessorDeduplication:
    """Test that processor removes duplicates."""

    def test_removes_duplicate_content(self):
        """Processor should remove exact duplicates."""
        from procedurewriter.pipeline.processor import PipelineProcessor

        processor = PipelineProcessor()

        # Test with exact duplicates that will definitely be deduplicated
        content = """
        Identificer 5. interkostalrum.
        Identificer 5. interkostalrum.
        Identificer 5. interkostalrum.
        Indsæt dræn.
        """

        result = processor.process("pleuradræn", content)

        # Exact duplicates should be removed
        interkostalrum_count = result.filtered_content.lower().count("interkostalrum")
        assert interkostalrum_count == 1  # Exactly 1 mention after dedup


class TestPipelineProcessorValidation:
    """Test that processor validates anatomical content."""

    def test_validates_anatomical_content(self):
        """Processor should validate anatomical requirements."""
        from procedurewriter.pipeline.processor import PipelineProcessor

        processor = PipelineProcessor()

        content = """
        Identificer 5. interkostalrum i midtaksillærlinjen.
        Marker triangle of safety.
        Indsæt nålen i 45 graders vinkel.
        Avancér 2-3 cm.
        """

        result = processor.process("pleuradræn", content)

        assert result.anatomical_validation is not None
        assert result.anatomical_validation.is_valid is True

    def test_identifies_missing_landmarks(self):
        """Processor should identify missing anatomical landmarks."""
        from procedurewriter.pipeline.processor import PipelineProcessor

        processor = PipelineProcessor()

        content = "Indsæt dræn."  # Missing landmarks

        result = processor.process("pleuradræn", content)

        assert result.anatomical_validation is not None
        assert result.anatomical_validation.is_valid is False
        assert len(result.anatomical_validation.missing_landmarks) > 0


class TestPipelineProcessorQualityScore:
    """Test quality scoring."""

    def test_calculates_quality_score(self):
        """Processor should calculate overall quality score."""
        from procedurewriter.pipeline.processor import PipelineProcessor

        processor = PipelineProcessor()

        # Good content
        good_content = """
        Identificer 5. interkostalrum i midtaksillærlinjen.
        Marker triangle of safety.
        Desinficér og afdæk sterilt.
        Infiltrér med lokalbedøvelse.
        Indsæt nålen i en vinkel på 45 grader.
        Avancér 2-3 cm til pleurahulen.
        """

        result = processor.process("pleuradræn", good_content)

        assert result.quality_score >= 0.0
        assert result.quality_score <= 1.0
        assert result.quality_score >= 0.7  # Good content should score well

    def test_low_score_for_poor_content(self):
        """Poor content should get low quality score."""
        from procedurewriter.pipeline.processor import PipelineProcessor

        processor = PipelineProcessor()

        # Poor content (workflow-heavy, no anatomy)
        poor_content = """
        Følg lokal retningslinje.
        Ring til bagvagt.
        Aftal rollefordeling.
        Kontakt forvagt.
        """

        result = processor.process("pleuradræn", poor_content)

        assert result.quality_score < 0.5

    def test_score_improves_with_content(self):
        """Quality score should improve with better content."""
        from procedurewriter.pipeline.processor import PipelineProcessor

        processor = PipelineProcessor()

        minimal = "Indsæt dræn."
        better = "Identificer 5. interkostalrum. Indsæt dræn."
        best = """
        Identificer 5. interkostalrum i midtaksillærlinjen.
        Marker triangle of safety.
        Indsæt nålen i 45 graders vinkel.
        Avancér 2-3 cm.
        """

        minimal_result = processor.process("pleuradræn", minimal)
        better_result = processor.process("pleuradræn", better)
        best_result = processor.process("pleuradræn", best)

        assert best_result.quality_score > better_result.quality_score
        assert better_result.quality_score > minimal_result.quality_score


class TestPipelineProcessorSuggestions:
    """Test improvement suggestions."""

    def test_provides_suggestions(self):
        """Processor should provide improvement suggestions."""
        from procedurewriter.pipeline.processor import PipelineProcessor

        processor = PipelineProcessor()

        content = "Indsæt dræn."  # Missing many elements

        result = processor.process("pleuradræn", content)

        assert len(result.suggestions) > 0

    def test_suggestions_are_actionable(self):
        """Suggestions should be specific and actionable."""
        from procedurewriter.pipeline.processor import PipelineProcessor

        processor = PipelineProcessor()

        content = "Indsæt dræn."

        result = processor.process("pleuradræn", content)

        # Should have suggestions about missing elements
        suggestion_text = " ".join(result.suggestions).lower()
        assert (
            "landmark" in suggestion_text
            or "dybde" in suggestion_text
            or "depth" in suggestion_text
            or "anatomisk" in suggestion_text
        )


class TestPipelineProcessorSections:
    """Test processing of sectioned content."""

    def test_processes_dict_sections(self):
        """Processor should handle dict of sections."""
        from procedurewriter.pipeline.processor import PipelineProcessor

        processor = PipelineProcessor()

        sections = {
            "Indikationer": ["Pneumothorax", "Pleuraeffusion"],
            "Fremgangsmåde": [
                "Identificer 5. interkostalrum.",
                "Ring til bagvagt.",
                "Indsæt dræn.",
            ],
        }

        result = processor.process_sections("pleuradræn", sections)

        assert "Fremgangsmåde" in result.filtered_sections
        # Workflow removed from Fremgangsmåde
        fremgang = result.filtered_sections["Fremgangsmåde"]
        assert not any("bagvagt" in item.lower() for item in fremgang)


class TestPipelineProcessorPromptEnhancement:
    """Test prompt enhancement integration."""

    def test_can_enhance_prompt(self):
        """Processor should have method to enhance prompts."""
        from procedurewriter.pipeline.processor import PipelineProcessor

        processor = PipelineProcessor()
        assert hasattr(processor, "enhance_prompt")
        assert callable(processor.enhance_prompt)

    def test_enhanced_prompt_includes_constraints(self):
        """Enhanced prompt should include clinical constraints."""
        from procedurewriter.pipeline.processor import PipelineProcessor

        processor = PipelineProcessor()

        original = "Du er en medicinsk forfatter."
        enhanced = processor.enhance_prompt(original, "pleuradræn")

        assert len(enhanced) > len(original)
        assert "SKRIVER IKKE" in enhanced or "skriver ikke" in enhanced.lower()


class TestQualityScorer:
    """Test standalone QualityScorer."""

    def test_scorer_can_be_instantiated(self):
        """QualityScorer should be instantiable."""
        from procedurewriter.pipeline.processor import QualityScorer

        scorer = QualityScorer()
        assert scorer is not None

    def test_has_score_method(self):
        """Scorer should have score method."""
        from procedurewriter.pipeline.processor import QualityScorer

        scorer = QualityScorer()
        assert hasattr(scorer, "score")
        assert callable(scorer.score)

    def test_score_returns_float(self):
        """score should return float between 0 and 1."""
        from procedurewriter.pipeline.processor import QualityScorer

        scorer = QualityScorer()
        result = scorer.score(
            procedure_name="pleuradræn",
            content="Identificer 5. interkostalrum.",
            workflow_percentage=0.1,
            anatomical_completeness=0.8,
        )

        assert isinstance(result, float)
        assert 0.0 <= result <= 1.0

    def test_score_components(self):
        """Score should consider multiple components."""
        from procedurewriter.pipeline.processor import QualityScorer

        scorer = QualityScorer()

        # High workflow = low score
        high_workflow = scorer.score(
            procedure_name="pleuradræn",
            content="Test",
            workflow_percentage=0.8,
            anatomical_completeness=0.5,
        )

        # Low workflow = higher score
        low_workflow = scorer.score(
            procedure_name="pleuradræn",
            content="Test",
            workflow_percentage=0.1,
            anatomical_completeness=0.5,
        )

        assert low_workflow > high_workflow


class TestProcessingResult:
    """Test ProcessingResult dataclass."""

    def test_result_has_all_fields(self):
        """ProcessingResult should have all required fields."""
        from procedurewriter.pipeline.processor import ProcessingResult
        from procedurewriter.pipeline.anatomical_requirements import ValidationResult

        result = ProcessingResult(
            filtered_content="Test content",
            workflow_removed=["bagvagt reference"],
            anatomical_validation=ValidationResult(
                is_valid=True,
                missing_landmarks=[],
            ),
            quality_score=0.85,
            suggestions=[],
        )

        assert result.filtered_content == "Test content"
        assert result.quality_score == 0.85


class TestPipelineProcessorWithRealContent:
    """End-to-end tests with realistic content."""

    def test_full_processing_good_content(self):
        """Test complete processing of good clinical content."""
        from procedurewriter.pipeline.processor import PipelineProcessor

        processor = PipelineProcessor()

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

        # Should pass validation
        assert result.anatomical_validation.is_valid is True
        assert result.quality_score >= 0.8
        assert len(result.suggestions) == 0 or all(
            "optional" in s.lower() or "overvej" in s.lower()
            for s in result.suggestions
        ) or result.suggestions == []

    def test_full_processing_poor_content(self):
        """Test complete processing of poor workflow-heavy content."""
        from procedurewriter.pipeline.processor import PipelineProcessor

        processor = PipelineProcessor()

        content = """
        Forbered proceduren ifølge afdelingens protokol.
        Ring til bagvagt ved behov for assistance.
        Aftal rollefordeling med teamet.
        Indsæt drænet.
        Følg lokal retningslinje for efterpleje.
        Kontakt bagvagten ved komplikationer.
        """

        result = processor.process("pleuradræn", content)

        # Should fail validation
        assert result.anatomical_validation.is_valid is False
        assert result.quality_score < 0.5
        assert len(result.suggestions) > 0

        # Workflow should be filtered
        assert "bagvagt" not in result.filtered_content.lower()
        assert "lokal retningslinje" not in result.filtered_content.lower()


class TestPipelineProcessorPreservesStructure:
    """Test that processor preserves document structure."""

    def test_preserves_line_breaks(self):
        """Processor should preserve line breaks in filtered content."""
        from procedurewriter.pipeline.processor import PipelineProcessor

        processor = PipelineProcessor()

        content = """Identificer 5. interkostalrum.
Marker triangle of safety.
Indsæt nålen i 45 graders vinkel."""

        result = processor.process("pleuradræn", content)

        # Line breaks should be preserved
        assert "\n" in result.filtered_content
        lines = result.filtered_content.strip().split("\n")
        assert len(lines) >= 3


class TestPipelineProcessorRenumbering:
    """Test that processor renumbers steps after filtering."""

    def test_renumbers_steps_after_workflow_removal(self):
        """Steps should be renumbered sequentially after filtering."""
        from procedurewriter.pipeline.processor import PipelineProcessor

        processor = PipelineProcessor()

        content = """1. Identificer 5. interkostalrum.
2. Ring til bagvagt ved komplikationer.
3. Marker triangle of safety.
4. Følg lokal retningslinje.
5. Indsæt nålen."""

        result = processor.process("pleuradræn", content)

        # After removing steps 2 and 4 (workflow), should renumber to 1, 2, 3
        lines = result.filtered_content.strip().split("\n")
        step_numbers = []
        for line in lines:
            match = re.match(r"^(\d+)\.", line.strip())
            if match:
                step_numbers.append(int(match.group(1)))

        # Should be sequential: 1, 2, 3
        assert step_numbers == [1, 2, 3], f"Expected [1, 2, 3], got {step_numbers}"

    def test_renumbers_with_parenthesis_style(self):
        """Should also renumber steps like '1)' style."""
        from procedurewriter.pipeline.processor import PipelineProcessor

        processor = PipelineProcessor()

        content = """1) Identificer interkostalrum.
2) Ring til bagvagt.
3) Marker triangle of safety."""

        result = processor.process("pleuradræn", content)

        lines = result.filtered_content.strip().split("\n")
        step_numbers = []
        for line in lines:
            match = re.match(r"^(\d+)\)", line.strip())
            if match:
                step_numbers.append(int(match.group(1)))

        # Steps 1 and 3 remain, should be 1, 2
        assert step_numbers == [1, 2], f"Expected [1, 2], got {step_numbers}"


class TestPipelineProcessorMarkdownPreservation:
    """Test that processor preserves markdown structure."""

    def test_preserves_markdown_headings(self):
        """Markdown headings should be preserved."""
        from procedurewriter.pipeline.processor import PipelineProcessor

        processor = PipelineProcessor()

        content = """## Fremgangsmåde
1. Identificer 5. interkostalrum.
2. Marker triangle of safety.

## Komplikationer
- Blødning
- Infektion"""

        result = processor.process("pleuradræn", content)

        assert "## Fremgangsmåde" in result.filtered_content
        assert "## Komplikationer" in result.filtered_content

    def test_preserves_bullet_points(self):
        """Bullet points should be preserved."""
        from procedurewriter.pipeline.processor import PipelineProcessor

        processor = PipelineProcessor()

        content = """Indikationer:
- Pneumothorax
- Pleuraeffusion
- Hæmothorax"""

        result = processor.process("pleuradræn", content)

        # Should have at least 3 bullet points
        assert result.filtered_content.count("- ") >= 3 or result.filtered_content.count("-") >= 3

    def test_preserves_paragraph_breaks(self):
        """Double newlines (paragraph breaks) should be preserved."""
        from procedurewriter.pipeline.processor import PipelineProcessor

        processor = PipelineProcessor()

        content = """## Section 1
Content for section 1.

## Section 2
Content for section 2."""

        result = processor.process("pleuradræn", content)

        # Should preserve paragraph structure
        assert "\n\n" in result.filtered_content or result.filtered_content.count("##") == 2


class TestPhase5ModulesImport:
    """Test that all Phase 5 modules can be imported."""

    def test_can_import_processor(self):
        """processor module should be importable."""
        from procedurewriter.pipeline.processor import (
            PipelineProcessor,
            ProcessingResult,
            QualityScorer,
            SectionProcessingResult,
        )

        assert PipelineProcessor is not None
        assert ProcessingResult is not None
        assert QualityScorer is not None
        assert SectionProcessingResult is not None

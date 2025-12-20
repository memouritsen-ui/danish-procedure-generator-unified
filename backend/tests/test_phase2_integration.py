"""Integration tests for Phase 2: Workflow Content Filter & Repetition Elimination.

Tests the integration of workflow filtering and deduplication
with the existing pipeline infrastructure.
"""

from __future__ import annotations

import pytest


class TestWorkflowFilterWithPipeline:
    """Test integration of WorkflowFilter with pipeline data."""

    def test_filter_works_with_snippet_text(self):
        """WorkflowFilter should work with Snippet-like text data."""
        from procedurewriter.pipeline.workflow_filter import WorkflowFilter
        from procedurewriter.pipeline.types import Snippet

        # Simulate snippets from pipeline
        snippets = [
            Snippet(
                source_id="SRC0001",
                text="Identificer 5. interkostalrum. Ring til bagvagt ved tvivl.",
                location={"page": 1},
            ),
            Snippet(
                source_id="SRC0002",
                text="Indsæt nålen i 45 graders vinkel til hudoverfladen.",
                location={"page": 2},
            ),
        ]

        wf = WorkflowFilter()

        for snippet in snippets:
            clinical, workflow = wf.filter_workflow_content(snippet.text)
            # Should successfully split without error
            assert isinstance(clinical, str)
            assert isinstance(workflow, str)

    def test_filter_integrates_with_snippet_classifier(self):
        """WorkflowFilter and SnippetClassifier should work together."""
        from procedurewriter.pipeline.workflow_filter import WorkflowFilter
        from procedurewriter.pipeline.snippet_classifier import (
            SnippetClassifier,
            SnippetType,
        )

        # Mixed content
        text = (
            "Indsæt dræn i 5. interkostalrum. "
            "Ring til bagvagt ved komplikationer. "
            "Avancér 2-3 cm efter pleuragennembrud."
        )

        # First filter workflow content
        wf = WorkflowFilter()
        clinical, workflow = wf.filter_workflow_content(text)

        # Then classify the clinical content
        classifier = SnippetClassifier()
        result = classifier.classify(clinical)

        # Clinical content should be classified as TECHNIQUE
        assert result.snippet_type == SnippetType.TECHNIQUE


class TestRepetitionDetectorWithPipeline:
    """Test integration of RepetitionDetector with pipeline data."""

    def test_deduplication_works_with_section_structure(self):
        """RepetitionDetector should work with typical section structure."""
        from procedurewriter.pipeline.deduplication import RepetitionDetector

        # Simulate sections from a generated procedure
        sections = {
            "Indikationer": [
                "Akut pleuravæske med respiratorisk påvirkning.",
                "Ring til bagvagt ved usikkerhed.",
            ],
            "Fremgangsmåde": [
                "Positionér patient i lateral decubitus.",
                "Identificer 5. interkostalrum.",
                "Ring til bagvagt ved komplikationer.",
                "Indsæt dræn med roterende bevægelse.",
            ],
            "Efterbehandling": [
                "Verificer drænplacering med røntgen.",
                "Kontakt bagvagt ved problemer.",
            ],
        }

        rd = RepetitionDetector()
        result = rd.deduplicate_sections(sections, threshold=0.5)

        # Should have same structure
        assert set(result.keys()) == set(sections.keys())

        # Should have reduced bagvagt references
        total_bagvagt_before = sum(
            sum(1 for t in texts if "bagvagt" in t.lower())
            for texts in sections.values()
        )
        total_bagvagt_after = sum(
            sum(1 for t in texts if "bagvagt" in t.lower())
            for texts in result.values()
        )
        assert total_bagvagt_after < total_bagvagt_before


class TestPhase2EndToEnd:
    """End-to-end tests for Phase 2 components working together."""

    def test_full_phase2_pipeline(self):
        """Test complete Phase 2 processing: filter + deduplicate."""
        from procedurewriter.pipeline.workflow_filter import WorkflowFilter
        from procedurewriter.pipeline.deduplication import RepetitionDetector

        # Realistic procedure content with workflow noise and repetition
        raw_sections = {
            "Indikationer": [
                "Akut pneumothorax med respiratorisk påvirkning.",
                "Pleuraeffusion med behov for dræning.",
                "Ved tvivl ring til bagvagt.",
            ],
            "Forberedelse": [
                "Tjek afdelingens protokol for sterilteknik.",
                "Klargør sterilt udstyr: handsker, afdækning, dræn.",
                "Aftal rollefordeling med teamet.",
                "Ring til anæstesi ved behov for sedation.",
            ],
            "Fremgangsmåde": [
                "Positionér patienten i lateral decubitus.",
                "Identificer 5. interkostalrum i midtaksillærlinjen.",
                "Desinficér hudområdet grundigt.",
                "Infiltrér med lokalbedøvelse.",
                "Indsæt nål i 45 graders vinkel.",
                "Avancér 2-3 cm efter gennembrydning.",
                "Ring til bagvagt ved komplikationer.",
                "Tilkald anæstesi hvis patienten bliver ustabil.",
            ],
            "Efterbehandling": [
                "Verificer drænplacering med røntgen.",
                "Observér for pneumothorax.",
                "Kontakt bagvagt ved forværring.",
            ],
        }

        # Step 1: Filter workflow content from each section
        wf = WorkflowFilter()
        filtered_sections: dict[str, list[str]] = {}
        workflow_extracted: list[str] = []

        for section_name, texts in raw_sections.items():
            clinical_items = []
            for text in texts:
                clinical, workflow = wf.filter_workflow_content(text)
                if clinical.strip():
                    clinical_items.append(clinical)
                if workflow.strip():
                    workflow_extracted.append(workflow)
            filtered_sections[section_name] = clinical_items

        # Step 2: Deduplicate remaining content
        rd = RepetitionDetector()
        final_sections = rd.deduplicate_sections(filtered_sections, threshold=0.5)

        # Verify results
        # Should have reduced overall content
        original_count = sum(len(v) for v in raw_sections.values())
        final_count = sum(len(v) for v in final_sections.values())
        assert final_count < original_count, "Should have fewer items after processing"

        # Workflow content should have been extracted
        assert len(workflow_extracted) > 0, "Should have extracted workflow content"

        # Key clinical content should be preserved
        all_clinical = " ".join(
            " ".join(v) for v in final_sections.values()
        )
        assert "interkostalrum" in all_clinical
        assert "midtaksillær" in all_clinical
        assert "45 grader" in all_clinical or "45 grad" in all_clinical

    def test_phase2_reduces_workflow_percentage(self):
        """Phase 2 should significantly reduce workflow content percentage."""
        from procedurewriter.pipeline.workflow_filter import WorkflowFilter

        # Content with high workflow percentage (typical of current output)
        workflow_heavy_content = """
1. Positionér patienten i lateral decubitus.
2. Ring til bagvagt ved usikkerhed om indikation.
3. Identificer 5. interkostalrum i midtaksillærlinjen.
4. Følg lokal retningslinje for sterilteknik.
5. Desinficér hudområdet.
6. Aftal rollefordeling med teamet.
7. Infiltrér med lokalbedøvelse.
8. Kontakt anæstesi på tlf. 12345 ved behov.
9. Indsæt nål i 45 graders vinkel.
10. Ring til bagvagt ved komplikationer.
"""

        wf = WorkflowFilter()
        clinical, workflow = wf.filter_workflow_content(workflow_heavy_content)
        stats = wf.get_filter_stats()

        # Should identify significant workflow content
        assert stats["workflow_percentage"] > 20, "Should identify >20% workflow content"

        # Clinical content should still contain the technique steps
        assert "45 grad" in clinical or "45 grader" in clinical
        assert "lokalbedøvelse" in clinical


class TestPhase2Statistics:
    """Test that Phase 2 provides useful statistics."""

    def test_combined_statistics(self):
        """Should be able to get combined statistics from both components."""
        from procedurewriter.pipeline.workflow_filter import WorkflowFilter
        from procedurewriter.pipeline.deduplication import RepetitionDetector

        texts = [
            "Indsæt nål i 45 grader.",
            "Ring til bagvagt.",
            "Indsæt nål i 45 grader.",  # Duplicate
            "Følg lokal retningslinje.",
        ]

        # Filter
        wf = WorkflowFilter()
        clinical_texts = []
        for text in texts:
            clinical, _ = wf.filter_workflow_content(text)
            if clinical.strip():
                clinical_texts.append(clinical)

        filter_stats = wf.get_filter_stats()

        # Deduplicate
        rd = RepetitionDetector()
        final = rd.deduplicate(clinical_texts)
        dedup_stats = rd.get_stats()

        # Should have meaningful statistics
        assert "workflow_percentage" in filter_stats
        assert "items_removed" in dedup_stats


class TestPhase2ModulesImport:
    """Test that all Phase 2 modules can be imported."""

    def test_can_import_workflow_filter(self):
        """workflow_filter module should be importable."""
        from procedurewriter.pipeline.workflow_filter import (
            WorkflowFilter,
            WORKFLOW_PATTERNS,
        )

        assert WorkflowFilter is not None
        assert len(WORKFLOW_PATTERNS) > 0

    def test_can_import_deduplication(self):
        """deduplication module should be importable."""
        from procedurewriter.pipeline.deduplication import (
            RepetitionDetector,
            DuplicateGroup,
        )

        assert RepetitionDetector is not None
        assert DuplicateGroup is not None

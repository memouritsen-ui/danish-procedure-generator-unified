"""Tests for workflow content filtering.

TDD Phase 2: Workflow Content Filter
Separates organizational/workflow content from clinical content.
"""

from __future__ import annotations

import pytest


class TestWorkflowFilterClass:
    """Test WorkflowFilter class structure."""

    def test_workflow_filter_can_be_instantiated(self):
        """WorkflowFilter should be instantiable."""
        from procedurewriter.pipeline.workflow_filter import WorkflowFilter

        wf = WorkflowFilter()
        assert wf is not None

    def test_has_filter_method(self):
        """WorkflowFilter should have filter_workflow_content method."""
        from procedurewriter.pipeline.workflow_filter import WorkflowFilter

        wf = WorkflowFilter()
        assert hasattr(wf, "filter_workflow_content")
        assert callable(wf.filter_workflow_content)

    def test_filter_returns_tuple(self):
        """filter_workflow_content should return (clinical, workflow) tuple."""
        from procedurewriter.pipeline.workflow_filter import WorkflowFilter

        wf = WorkflowFilter()
        result = wf.filter_workflow_content("some text")

        assert isinstance(result, tuple)
        assert len(result) == 2


class TestWorkflowPatternDetection:
    """Test detection of workflow patterns in Danish medical text."""

    def test_detects_ring_til_bagvagt(self):
        """Should detect 'ring til bagvagt' as workflow content."""
        from procedurewriter.pipeline.workflow_filter import WorkflowFilter

        wf = WorkflowFilter()
        text = "Ved komplikationer ring til bagvagt på afdeling X."
        clinical, workflow = wf.filter_workflow_content(text)

        assert "ring til bagvagt" in workflow.lower()
        assert "ring til bagvagt" not in clinical.lower()

    def test_detects_phone_numbers(self):
        """Should detect phone numbers as workflow content."""
        from procedurewriter.pipeline.workflow_filter import WorkflowFilter

        wf = WorkflowFilter()
        text = "Kontakt anæstesi på tlf. 12345 ved behov for sedation."
        clinical, workflow = wf.filter_workflow_content(text)

        assert "tlf" in workflow.lower() or "12345" in workflow
        assert "12345" not in clinical

    def test_detects_tilkald_anaestesi(self):
        """Should detect 'tilkald anæstesi' variations as workflow."""
        from procedurewriter.pipeline.workflow_filter import WorkflowFilter

        wf = WorkflowFilter()
        text = "Tilkald anæstesi ved behov for dyb sedation eller tvivl."
        clinical, workflow = wf.filter_workflow_content(text)

        assert "tilkald" in workflow.lower()

    def test_detects_foelg_lokal_retningslinje(self):
        """Should detect 'følg lokal retningslinje' as workflow."""
        from procedurewriter.pipeline.workflow_filter import WorkflowFilter

        wf = WorkflowFilter()
        text = "Følg lokal retningslinje for dosering af antibiotika."
        clinical, workflow = wf.filter_workflow_content(text)

        assert "lokal retningslinje" in workflow.lower()

    def test_detects_aftal_rollefordeling(self):
        """Should detect 'aftal rollefordeling' as workflow."""
        from procedurewriter.pipeline.workflow_filter import WorkflowFilter

        wf = WorkflowFilter()
        text = "Aftal rollefordeling inden proceduren påbegyndes."
        clinical, workflow = wf.filter_workflow_content(text)

        assert "rollefordeling" in workflow.lower()

    def test_detects_spoerg_kollega(self):
        """Should detect 'spørg kollega' as workflow."""
        from procedurewriter.pipeline.workflow_filter import WorkflowFilter

        wf = WorkflowFilter()
        text = "Ved usikkerhed spørg en mere erfaren kollega."
        clinical, workflow = wf.filter_workflow_content(text)

        assert "kollega" in workflow.lower()

    def test_detects_tjek_afdelingens(self):
        """Should detect 'tjek afdelingens' as workflow."""
        from procedurewriter.pipeline.workflow_filter import WorkflowFilter

        wf = WorkflowFilter()
        text = "Tjek afdelingens protokol for lokalbedøvelse."
        clinical, workflow = wf.filter_workflow_content(text)

        assert "afdelingens" in workflow.lower()

    def test_detects_kontakt_forvagt(self):
        """Should detect 'kontakt forvagt' as workflow."""
        from procedurewriter.pipeline.workflow_filter import WorkflowFilter

        wf = WorkflowFilter()
        text = "Kontakt forvagt ved pludseligt behov for assistance."
        clinical, workflow = wf.filter_workflow_content(text)

        assert "forvagt" in workflow.lower()


class TestClinicalContentPreservation:
    """Test that clinical/technique content is preserved."""

    def test_preserves_anatomical_content(self):
        """Should preserve anatomical landmarks in clinical content."""
        from procedurewriter.pipeline.workflow_filter import WorkflowFilter

        wf = WorkflowFilter()
        text = "Identificer 5. interkostalrum i midtaksillærlinjen."
        clinical, workflow = wf.filter_workflow_content(text)

        assert "interkostalrum" in clinical
        assert "midtaksillær" in clinical

    def test_preserves_technique_steps(self):
        """Should preserve procedure technique in clinical content."""
        from procedurewriter.pipeline.workflow_filter import WorkflowFilter

        wf = WorkflowFilter()
        text = "Indsæt nålen i en vinkel på 45 grader til hudoverfladen."
        clinical, workflow = wf.filter_workflow_content(text)

        assert "45 grader" in clinical
        assert "nålen" in clinical

    def test_preserves_depth_guidance(self):
        """Should preserve depth guidance in clinical content."""
        from procedurewriter.pipeline.workflow_filter import WorkflowFilter

        wf = WorkflowFilter()
        text = "Avancér kateteret 2-3 cm efter gennembrydning af pleura."
        clinical, workflow = wf.filter_workflow_content(text)

        assert "2-3 cm" in clinical
        assert "pleura" in clinical

    def test_preserves_equipment_info(self):
        """Should preserve equipment information in clinical content."""
        from procedurewriter.pipeline.workflow_filter import WorkflowFilter

        wf = WorkflowFilter()
        text = "Anvend 18G eller 16G kanyle afhængig af indikation."
        clinical, workflow = wf.filter_workflow_content(text)

        assert "18G" in clinical
        assert "kanyle" in clinical


class TestMixedContent:
    """Test filtering of mixed clinical and workflow content."""

    def test_separates_mixed_sentence(self):
        """Should separate workflow from clinical in mixed text."""
        from procedurewriter.pipeline.workflow_filter import WorkflowFilter

        wf = WorkflowFilter()
        text = (
            "Indsæt dræn i 5. interkostalrum. "
            "Ring til bagvagt ved komplikationer. "
            "Avancér 2-3 cm efter pleuragennembrud."
        )
        clinical, workflow = wf.filter_workflow_content(text)

        # Clinical content preserved
        assert "interkostalrum" in clinical
        assert "2-3 cm" in clinical

        # Workflow content separated
        assert "bagvagt" in workflow

    def test_handles_multiline_mixed_content(self):
        """Should handle multiline mixed content."""
        from procedurewriter.pipeline.workflow_filter import WorkflowFilter

        wf = WorkflowFilter()
        text = """1. Positionér patienten i lateral decubitus.
2. Identificer 5. interkostalrum i midtaksillærlinjen.
3. Følg lokal retningslinje for steril teknik.
4. Infiltrer med lokalbedøvelse.
5. Ring til anæstesi ved behov for sedation."""

        clinical, workflow = wf.filter_workflow_content(text)

        # Clinical preserved
        assert "lateral decubitus" in clinical
        assert "lokalbedøvelse" in clinical

        # Workflow separated
        assert "lokal retningslinje" in workflow
        assert "Ring til anæstesi" in workflow


class TestEdgeCases:
    """Test edge cases for workflow filter."""

    def test_handles_empty_input(self):
        """Should handle empty input gracefully."""
        from procedurewriter.pipeline.workflow_filter import WorkflowFilter

        wf = WorkflowFilter()
        clinical, workflow = wf.filter_workflow_content("")

        assert clinical == ""
        assert workflow == ""

    def test_handles_pure_clinical_content(self):
        """Should handle text with no workflow content."""
        from procedurewriter.pipeline.workflow_filter import WorkflowFilter

        wf = WorkflowFilter()
        text = "Punktér huden i en vinkel på 90 grader. Aspirér for at verificere position."
        clinical, workflow = wf.filter_workflow_content(text)

        assert clinical.strip() != ""
        assert workflow.strip() == ""

    def test_handles_pure_workflow_content(self):
        """Should handle text with only workflow content."""
        from procedurewriter.pipeline.workflow_filter import WorkflowFilter

        wf = WorkflowFilter()
        text = "Ring til bagvagt. Følg lokal retningslinje. Aftal rollefordeling."
        clinical, workflow = wf.filter_workflow_content(text)

        assert workflow.strip() != ""
        # Clinical might be empty or contain only connectors

    def test_case_insensitive_matching(self):
        """Should match workflow patterns case-insensitively."""
        from procedurewriter.pipeline.workflow_filter import WorkflowFilter

        wf = WorkflowFilter()
        text = "RING TIL BAGVAGT ved akutte komplikationer."
        clinical, workflow = wf.filter_workflow_content(text)

        assert "RING TIL BAGVAGT" in workflow or "ring til bagvagt" in workflow.lower()


class TestFilterStatistics:
    """Test filter statistics and reporting."""

    def test_has_get_stats_method(self):
        """WorkflowFilter should have get_filter_stats method."""
        from procedurewriter.pipeline.workflow_filter import WorkflowFilter

        wf = WorkflowFilter()
        assert hasattr(wf, "get_filter_stats")

    def test_stats_includes_workflow_percentage(self):
        """Stats should include workflow content percentage."""
        from procedurewriter.pipeline.workflow_filter import WorkflowFilter

        wf = WorkflowFilter()
        text = "Teknik: Indsæt nålen. Ring til bagvagt ved problemer."
        wf.filter_workflow_content(text)
        stats = wf.get_filter_stats()

        assert "workflow_percentage" in stats
        assert 0 <= stats["workflow_percentage"] <= 100

    def test_stats_includes_pattern_counts(self):
        """Stats should include counts of matched patterns."""
        from procedurewriter.pipeline.workflow_filter import WorkflowFilter

        wf = WorkflowFilter()
        text = "Ring til bagvagt. Følg lokal retningslinje."
        wf.filter_workflow_content(text)
        stats = wf.get_filter_stats()

        assert "pattern_matches" in stats
        assert isinstance(stats["pattern_matches"], dict)


class TestBatchFiltering:
    """Test batch filtering of multiple texts."""

    def test_has_filter_batch_method(self):
        """WorkflowFilter should have filter_batch method."""
        from procedurewriter.pipeline.workflow_filter import WorkflowFilter

        wf = WorkflowFilter()
        assert hasattr(wf, "filter_batch")

    def test_filter_batch_returns_list(self):
        """filter_batch should return list of tuples."""
        from procedurewriter.pipeline.workflow_filter import WorkflowFilter

        wf = WorkflowFilter()
        texts = [
            "Indsæt nålen i 45 grader.",
            "Ring til bagvagt ved behov.",
        ]
        results = wf.filter_batch(texts)

        assert isinstance(results, list)
        assert len(results) == 2
        for result in results:
            assert isinstance(result, tuple)
            assert len(result) == 2

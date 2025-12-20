"""Tests for semantic repetition detection and deduplication.

TDD Phase 2: Repetition Elimination
Detects and removes semantically similar content across sections.
"""

from __future__ import annotations

import pytest


class TestRepetitionDetectorClass:
    """Test RepetitionDetector class structure."""

    def test_repetition_detector_can_be_instantiated(self):
        """RepetitionDetector should be instantiable."""
        from procedurewriter.pipeline.deduplication import RepetitionDetector

        rd = RepetitionDetector()
        assert rd is not None

    def test_has_detect_duplicates_method(self):
        """RepetitionDetector should have detect_duplicates method."""
        from procedurewriter.pipeline.deduplication import RepetitionDetector

        rd = RepetitionDetector()
        assert hasattr(rd, "detect_duplicates")
        assert callable(rd.detect_duplicates)

    def test_has_deduplicate_method(self):
        """RepetitionDetector should have deduplicate method."""
        from procedurewriter.pipeline.deduplication import RepetitionDetector

        rd = RepetitionDetector()
        assert hasattr(rd, "deduplicate")
        assert callable(rd.deduplicate)


class TestDuplicateGroup:
    """Test DuplicateGroup dataclass for grouping similar content."""

    def test_duplicate_group_has_required_fields(self):
        """DuplicateGroup should have items and canonical fields."""
        from procedurewriter.pipeline.deduplication import DuplicateGroup

        group = DuplicateGroup(
            items=["text1", "text2"],
            canonical="text1",
            similarity=0.92,
        )

        assert group.items == ["text1", "text2"]
        assert group.canonical == "text1"
        assert group.similarity == 0.92


class TestExactDuplicateDetection:
    """Test detection of exact duplicates."""

    def test_detects_exact_duplicate_sentences(self):
        """Should detect exact duplicate sentences."""
        from procedurewriter.pipeline.deduplication import RepetitionDetector

        rd = RepetitionDetector()
        texts = [
            "Tilkald anæstesi ved behov.",
            "Indsæt dræn i 5. interkostalrum.",
            "Tilkald anæstesi ved behov.",
        ]
        groups = rd.detect_duplicates(texts)

        # Should find at least one group with duplicates
        assert len(groups) >= 1
        dup_group = groups[0]
        assert len(dup_group.items) >= 2

    def test_detects_duplicate_with_different_case(self):
        """Should detect duplicates ignoring case."""
        from procedurewriter.pipeline.deduplication import RepetitionDetector

        rd = RepetitionDetector()
        texts = [
            "RING TIL BAGVAGT VED KOMPLIKATIONER.",
            "Ring til bagvagt ved komplikationer.",
        ]
        groups = rd.detect_duplicates(texts)

        assert len(groups) >= 1

    def test_ignores_unique_content(self):
        """Should not group unique content."""
        from procedurewriter.pipeline.deduplication import RepetitionDetector

        rd = RepetitionDetector()
        texts = [
            "Indsæt nål i 5. interkostalrum.",
            "Aspirér for at verificere position.",
            "Avancér kateter 2-3 cm.",
        ]
        groups = rd.detect_duplicates(texts)

        # All unique, so either no groups or groups of size 1
        for group in groups:
            assert len(group.items) == 1


class TestSemanticDuplicateDetection:
    """Test detection of semantically similar content."""

    def test_detects_paraphrased_call_instructions(self):
        """Should detect similar call/contact instructions."""
        from procedurewriter.pipeline.deduplication import RepetitionDetector

        rd = RepetitionDetector()
        texts = [
            "Ring til bagvagt ved komplikationer.",
            "Kontakt bagvagten hvis der opstår komplikationer.",
            "Ved komplikationer tilkaldes bagvagten.",
        ]
        groups = rd.detect_duplicates(texts, threshold=0.6)

        # Should group all three as semantically similar
        assert len(groups) >= 1
        # At least one group should have multiple items
        has_multi_item_group = any(len(g.items) >= 2 for g in groups)
        assert has_multi_item_group

    def test_detects_similar_lokal_retningslinje_references(self):
        """Should group similar 'local guideline' references."""
        from procedurewriter.pipeline.deduplication import RepetitionDetector

        rd = RepetitionDetector()
        texts = [
            "Følg lokal retningslinje for dosering.",
            "Se lokal retningslinje vedr. dosering.",
            "Doseringsanbefalinger: se lokal instruks.",
        ]
        groups = rd.detect_duplicates(texts, threshold=0.5)

        # Should recognize these as similar
        has_multi_item_group = any(len(g.items) >= 2 for g in groups)
        assert has_multi_item_group

    def test_does_not_group_unrelated_content(self):
        """Should not group semantically unrelated content."""
        from procedurewriter.pipeline.deduplication import RepetitionDetector

        rd = RepetitionDetector()
        texts = [
            "Identificer 5. interkostalrum i midtaksillærlinjen.",
            "Komplikationer omfatter pneumothorax og blødning.",
            "Udstyr: sterile handsker, desinfektionsmiddel.",
        ]
        groups = rd.detect_duplicates(texts, threshold=0.7)

        # These are unrelated, should be in separate groups
        for group in groups:
            assert len(group.items) == 1


class TestDeduplication:
    """Test the deduplicate method for removing repetitive content."""

    def test_removes_exact_duplicates(self):
        """Should remove exact duplicates, keeping first occurrence."""
        from procedurewriter.pipeline.deduplication import RepetitionDetector

        rd = RepetitionDetector()
        texts = [
            "Tilkald anæstesi ved behov.",
            "Indsæt dræn.",
            "Tilkald anæstesi ved behov.",
            "Verificer position.",
        ]
        result = rd.deduplicate(texts)

        assert len(result) == 3
        assert result.count("Tilkald anæstesi ved behov.") == 1

    def test_keeps_first_occurrence(self):
        """Should keep the first occurrence of duplicates."""
        from procedurewriter.pipeline.deduplication import RepetitionDetector

        rd = RepetitionDetector()
        texts = [
            "A",
            "B",
            "A",
            "C",
            "B",
        ]
        result = rd.deduplicate(texts)

        assert result == ["A", "B", "C"]

    def test_handles_empty_input(self):
        """Should handle empty input."""
        from procedurewriter.pipeline.deduplication import RepetitionDetector

        rd = RepetitionDetector()
        result = rd.deduplicate([])

        assert result == []

    def test_semantic_deduplication_with_threshold(self):
        """Should deduplicate semantically similar content with threshold."""
        from procedurewriter.pipeline.deduplication import RepetitionDetector

        rd = RepetitionDetector()
        texts = [
            "Ring til bagvagt ved problemer.",
            "Indsæt nål i korrekt vinkel.",
            "Kontakt bagvagten ved komplikationer.",
        ]
        result = rd.deduplicate(texts, threshold=0.6)

        # Should keep only one of the "bagvagt" sentences
        bagvagt_count = sum(1 for t in result if "bagvagt" in t.lower())
        assert bagvagt_count == 1


class TestCanonicalSelection:
    """Test selection of canonical (best) version from duplicates."""

    def test_prefers_longer_version(self):
        """Should prefer longer/more detailed version as canonical."""
        from procedurewriter.pipeline.deduplication import RepetitionDetector

        rd = RepetitionDetector()
        texts = [
            "Ring bagvagt.",
            "Ring til bagvagt ved komplikationer eller tvivl om behandling.",
        ]
        groups = rd.detect_duplicates(texts, threshold=0.5)

        if groups:
            # The longer version should be canonical
            canonical = groups[0].canonical
            assert len(canonical) > len("Ring bagvagt.")

    def test_prefers_more_specific_content(self):
        """Should prefer specific over vague content."""
        from procedurewriter.pipeline.deduplication import RepetitionDetector

        rd = RepetitionDetector()
        texts = [
            "Følg lokal retningslinje.",
            "Følg lokal retningslinje for dosering af lokalbedøvelse.",
        ]
        groups = rd.detect_duplicates(texts, threshold=0.5)

        if groups and len(groups[0].items) > 1:
            canonical = groups[0].canonical
            assert "dosering" in canonical or "lokalbedøvelse" in canonical


class TestSectionDeduplication:
    """Test deduplication across document sections."""

    def test_deduplicate_sections_dict(self):
        """Should deduplicate across sections in a document."""
        from procedurewriter.pipeline.deduplication import RepetitionDetector

        rd = RepetitionDetector()
        sections = {
            "Indikationer": ["Akut pleuravæske.", "Ring til bagvagt ved tvivl."],
            "Fremgangsmåde": ["Indsæt dræn.", "Ring til bagvagt ved komplikationer."],
            "Efterbehandling": ["Observér patienten.", "Kontakt bagvagt ved problemer."],
        }
        result = rd.deduplicate_sections(sections, threshold=0.5)

        # Should have same structure
        assert set(result.keys()) == set(sections.keys())

        # Total "bagvagt" mentions should be reduced
        total_bagvagt_original = sum(
            sum(1 for t in texts if "bagvagt" in t.lower())
            for texts in sections.values()
        )
        total_bagvagt_result = sum(
            sum(1 for t in texts if "bagvagt" in t.lower())
            for texts in result.values()
        )
        assert total_bagvagt_result < total_bagvagt_original


class TestDeduplicationStats:
    """Test statistics and reporting for deduplication."""

    def test_has_get_stats_method(self):
        """RepetitionDetector should have get_stats method."""
        from procedurewriter.pipeline.deduplication import RepetitionDetector

        rd = RepetitionDetector()
        assert hasattr(rd, "get_stats")

    def test_stats_includes_items_removed(self):
        """Stats should include count of removed items."""
        from procedurewriter.pipeline.deduplication import RepetitionDetector

        rd = RepetitionDetector()
        texts = ["A", "B", "A", "C", "A"]
        rd.deduplicate(texts)
        stats = rd.get_stats()

        assert "items_removed" in stats
        assert stats["items_removed"] == 2  # Two "A"s removed

    def test_stats_includes_duplicate_groups(self):
        """Stats should include number of duplicate groups found."""
        from procedurewriter.pipeline.deduplication import RepetitionDetector

        rd = RepetitionDetector()
        texts = ["A", "B", "A", "C", "B"]
        rd.deduplicate(texts)
        stats = rd.get_stats()

        assert "duplicate_groups" in stats
        assert stats["duplicate_groups"] >= 2  # "A" and "B" are duplicated

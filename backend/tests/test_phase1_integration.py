"""Integration tests for Phase 1: Source Diversification.

Tests the integration of international sources and snippet classification
with the existing pipeline infrastructure.
"""

from __future__ import annotations

import pytest
from pathlib import Path


class TestInternationalSourcesWithPipeline:
    """Test integration of international sources with existing pipeline."""

    def test_international_source_can_be_converted_to_source_record(self):
        """InternationalSource should be convertible to SourceRecord for pipeline."""
        from procedurewriter.pipeline.international_sources import (
            InternationalSource,
            SourceTier,
        )
        from procedurewriter.pipeline.types import SourceRecord

        int_source = InternationalSource(
            url="https://www.nice.org.uk/guidance/ng39",
            title="Anaphylaxis: assessment and referral",
            source_type="nice_guideline",
            evidence_tier=SourceTier.TIER_1_INTERNATIONAL,
            abstract="This guideline covers assessment...",
            publication_year=2020,
        )

        # Should be able to create a SourceRecord from InternationalSource
        source_record = SourceRecord(
            source_id="INTL0001",
            fetched_at_utc="2025-12-20T00:00:00Z",
            url=int_source.url,
            title=int_source.title,
            kind=int_source.source_type,
            raw_path="",
            normalized_path="",
            raw_sha256="",
            normalized_sha256="",
            year=int_source.publication_year,
            doi=None,
            pmid=None,
            extraction_notes=None,
            terms_licence_note=None,
            extra={
                "evidence_tier": int_source.evidence_tier,
                "abstract": int_source.abstract,
            },
        )

        assert source_record.source_id == "INTL0001"
        assert source_record.url == "https://www.nice.org.uk/guidance/ng39"
        assert source_record.kind == "nice_guideline"
        assert source_record.year == 2020
        assert source_record.extra["evidence_tier"] == 1

    def test_snippet_classifier_works_with_pipeline_snippets(self):
        """SnippetClassifier should work with Snippet objects from pipeline."""
        from procedurewriter.pipeline.snippet_classifier import (
            SnippetClassifier,
            SnippetType,
        )
        from procedurewriter.pipeline.types import Snippet

        # Create pipeline Snippet objects
        pipeline_snippets = [
            Snippet(
                source_id="SRC0001",
                text="Identificer 5. interkostalrum i midtaksillærlinjen",
                location={"page": 1},
            ),
            Snippet(
                source_id="SRC0002",
                text="Ring til bagvagt ved komplikationer tlf. 12345",
                location={"page": 2},
            ),
        ]

        classifier = SnippetClassifier()

        # Classify texts from Snippet objects
        classified = classifier.classify_batch(
            [s.text for s in pipeline_snippets],
            [s.source_id for s in pipeline_snippets],
        )

        # First should be TECHNIQUE (anatomical content)
        assert classified[0].snippet_type == SnippetType.TECHNIQUE
        assert classified[0].source_id == "SRC0001"

        # Second should be WORKFLOW (call instructions + phone)
        assert classified[1].snippet_type == SnippetType.WORKFLOW
        assert classified[1].source_id == "SRC0002"

    def test_filter_snippets_by_type_for_section(self):
        """Should be able to filter snippets for section-specific content."""
        from procedurewriter.pipeline.snippet_classifier import (
            SnippetClassifier,
            SnippetType,
        )

        texts = [
            "Indsæt nålen i en vinkel på 45 grader",  # TECHNIQUE
            "Ring til anæstesi ved komplikationer",  # WORKFLOW
            "Udstyr: Sterile handsker, kateter 18G",  # EQUIPMENT
            "Komplikationer omfatter pneumothorax",  # SAFETY
            "Et RCT af Hansen et al. (2023) viste...",  # EVIDENCE
        ]

        classifier = SnippetClassifier()
        classified = classifier.classify_batch(texts)

        # For "Fremgangsmåde" section, only want TECHNIQUE
        technique_only = classifier.filter_by_type(classified, SnippetType.TECHNIQUE)
        assert len(technique_only) == 1
        assert "45 grader" in technique_only[0].text

        # For "Udstyr" section, only want EQUIPMENT
        equipment_only = classifier.filter_by_type(classified, SnippetType.EQUIPMENT)
        assert len(equipment_only) == 1
        assert "18G" in equipment_only[0].text


class TestSourceAllowlistIntegration:
    """Test that source allowlist is correctly configured."""

    def test_allowlist_file_exists(self):
        """source_allowlist.yaml should exist."""
        config_dir = Path(__file__).parent.parent.parent / "config"
        allowlist_path = config_dir / "source_allowlist.yaml"

        assert allowlist_path.exists(), f"Allowlist not found at {allowlist_path}"

    def test_allowlist_has_international_sources(self):
        """Allowlist should include international sources."""
        import yaml

        config_dir = Path(__file__).parent.parent.parent / "config"
        allowlist_path = config_dir / "source_allowlist.yaml"

        with open(allowlist_path) as f:
            config = yaml.safe_load(f)

        prefixes = config.get("allowed_url_prefixes", [])

        # Check for key international sources
        nice_present = any("nice.org.uk" in p for p in prefixes)
        cochrane_present = any("cochrane" in p for p in prefixes)
        bts_present = any("brit-thoracic" in p for p in prefixes)
        who_present = any("who.int" in p for p in prefixes)

        assert nice_present, "NICE guidelines should be in allowlist"
        assert cochrane_present, "Cochrane Library should be in allowlist"
        assert bts_present, "British Thoracic Society should be in allowlist"
        assert who_present, "WHO should be in allowlist"

    def test_allowlist_has_seed_urls_for_key_procedures(self):
        """Allowlist should have seed URLs for key procedures."""
        import yaml

        config_dir = Path(__file__).parent.parent.parent / "config"
        allowlist_path = config_dir / "source_allowlist.yaml"

        with open(allowlist_path) as f:
            config = yaml.safe_load(f)

        seed_urls = config.get("seed_urls", [])

        # Should have at least some seed URLs
        assert len(seed_urls) >= 1, "Should have at least 1 seed URL"

        # Check seed URL structure
        for seed in seed_urls:
            assert "url" in seed, "Seed URL should have 'url' field"
            assert "procedure_keywords" in seed, "Seed URL should have 'procedure_keywords'"


class TestPipelineModulesImport:
    """Test that all new modules can be imported."""

    def test_can_import_international_sources(self):
        """international_sources module should be importable."""
        from procedurewriter.pipeline.international_sources import (
            InternationalSource,
            SourceTier,
            NICEClient,
            CochraneClient,
            InternationalSourceAggregator,
        )

        assert InternationalSource is not None
        assert SourceTier is not None
        assert NICEClient is not None
        assert CochraneClient is not None
        assert InternationalSourceAggregator is not None

    def test_can_import_snippet_classifier(self):
        """snippet_classifier module should be importable."""
        from procedurewriter.pipeline.snippet_classifier import (
            SnippetType,
            ClassifiedSnippet,
            SnippetClassifier,
        )

        assert SnippetType is not None
        assert ClassifiedSnippet is not None
        assert SnippetClassifier is not None


class TestSourceTierPrioritization:
    """Test that source tier prioritization works correctly."""

    def test_tier_1_sources_come_before_tier_4(self):
        """Tier 1 (international) sources should be prioritized over Tier 4 (Danish)."""
        from procedurewriter.pipeline.international_sources import (
            InternationalSource,
            SourceTier,
        )

        sources = [
            InternationalSource(
                url="https://e-dok.rm.dk/...",
                title="Danish regional guideline",
                source_type="danish_guideline",
                evidence_tier=SourceTier.TIER_4_DANISH,
            ),
            InternationalSource(
                url="https://www.nice.org.uk/...",
                title="NICE guideline",
                source_type="nice_guideline",
                evidence_tier=SourceTier.TIER_1_INTERNATIONAL,
            ),
            InternationalSource(
                url="https://www.cochranelibrary.com/...",
                title="Cochrane review",
                source_type="cochrane_review",
                evidence_tier=SourceTier.TIER_1_INTERNATIONAL,
            ),
        ]

        # Sort by tier
        sorted_sources = sorted(sources, key=lambda s: s.evidence_tier)

        # First two should be Tier 1
        assert sorted_sources[0].evidence_tier == 1
        assert sorted_sources[1].evidence_tier == 1

        # Last should be Tier 4
        assert sorted_sources[2].evidence_tier == 4


class TestWorkflowContentFiltering:
    """Test filtering of workflow content from clinical content."""

    def test_can_separate_technique_from_workflow_content(self):
        """Should separate technique content from workflow content."""
        from procedurewriter.pipeline.snippet_classifier import (
            SnippetClassifier,
            SnippetType,
        )

        # Mixed content from a typical Danish guideline
        mixed_content = [
            "Identificer 5. interkostalrum i midtaksillærlinjen",
            "Ring til bagvagt ved tvivl eller komplikationer",
            "Indsæt trokar med rotererende bevægelse",
            "Følg lokal retningslinje for antibiotika",
            "Avancér kateter 2-3 cm efter gennembrydning af pleura",
            "Kontakt anæstesi på tlf. 12345 ved behov for sedation",
        ]

        classifier = SnippetClassifier()
        classified = classifier.classify_batch(mixed_content)

        technique_snippets = classifier.filter_by_type(classified, SnippetType.TECHNIQUE)
        workflow_snippets = classifier.filter_by_type(classified, SnippetType.WORKFLOW)

        # Should have technique content
        assert len(technique_snippets) >= 2, "Should identify at least 2 technique snippets"

        # Should have workflow content
        assert len(workflow_snippets) >= 2, "Should identify at least 2 workflow snippets"

        # Workflow snippets should contain call/phone/lokal references
        workflow_texts = [s.text for s in workflow_snippets]
        assert any("bagvagt" in t or "lokal" in t or "tlf" in t for t in workflow_texts)

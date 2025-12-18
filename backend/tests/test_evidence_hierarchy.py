"""Tests for the evidence hierarchy module."""
from pathlib import Path

import pytest

from procedurewriter.pipeline.evidence_hierarchy import (
    EvidenceHierarchy,
    EvidenceLevel,
    classify_source,
    get_evidence_hierarchy,
)

# Path to the evidence hierarchy config file (backend/tests -> backend -> unified -> config)
CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "evidence_hierarchy.yaml"


class TestEvidenceLevel:
    """Tests for EvidenceLevel dataclass."""

    def test_evidence_level_creation(self) -> None:
        level = EvidenceLevel(
            level_id="test",
            priority=100,
            badge="Test Badge",
            badge_color="#ff0000",
            description="Test description",
        )
        assert level.level_id == "test"
        assert level.priority == 100
        assert level.badge == "Test Badge"
        assert level.badge_color == "#ff0000"
        assert level.description == "Test description"

    def test_evidence_level_is_immutable(self) -> None:
        level = EvidenceLevel(
            level_id="test",
            priority=100,
            badge="Test",
            badge_color="#ff0000",
            description="Test",
        )
        with pytest.raises(AttributeError):
            level.priority = 200  # type: ignore


class TestEvidenceHierarchy:
    """Tests for EvidenceHierarchy class."""

    def test_default_config_has_levels(self) -> None:
        hierarchy = EvidenceHierarchy()
        levels = hierarchy.get_all_levels()
        assert len(levels) > 0
        # Should have at least danish_guideline and unclassified
        level_ids = [lvl.level_id for lvl in levels]
        assert "danish_guideline" in level_ids
        assert "unclassified" in level_ids

    def test_classify_by_url_danish(self) -> None:
        hierarchy = EvidenceHierarchy.from_config(CONFIG_PATH)
        level = hierarchy.classify_source(url="https://sst.dk/guidelines/something")
        assert level.level_id == "danish_guideline"
        assert level.priority == 1000
        assert "DK" in level.badge

    def test_classify_by_url_nordic(self) -> None:
        hierarchy = EvidenceHierarchy.from_config(CONFIG_PATH)
        level = hierarchy.classify_source(url="https://socialstyrelsen.se/regler")
        assert level.level_id == "nordic_guideline"
        assert level.priority == 900

    def test_classify_by_url_international(self) -> None:
        hierarchy = EvidenceHierarchy.from_config(CONFIG_PATH)
        level = hierarchy.classify_source(url="https://nice.org.uk/guidance/ng123")
        assert level.level_id == "international_guideline"
        assert level.priority == 800

    def test_classify_by_pubmed_systematic_review(self) -> None:
        hierarchy = EvidenceHierarchy.from_config(CONFIG_PATH)
        level = hierarchy.classify_source(publication_types=["Systematic Review", "Journal Article"])
        assert level.level_id == "systematic_review"
        assert level.priority == 700

    def test_classify_by_pubmed_rct(self) -> None:
        hierarchy = EvidenceHierarchy.from_config(CONFIG_PATH)
        level = hierarchy.classify_source(publication_types=["Randomized Controlled Trial"])
        assert level.level_id == "rct"
        assert level.priority == 500

    def test_classify_by_pubmed_practice_guideline(self) -> None:
        hierarchy = EvidenceHierarchy.from_config(CONFIG_PATH)
        level = hierarchy.classify_source(publication_types=["Practice Guideline"])
        assert level.level_id == "practice_guideline"
        assert level.priority == 650

    def test_classify_unknown_url_returns_unclassified(self) -> None:
        hierarchy = EvidenceHierarchy()
        level = hierarchy.classify_source(url="https://example.com/random")
        assert level.level_id == "unclassified"
        assert level.priority == 100  # Updated from 50 to 100 for more balanced scoring

    def test_classify_library_danish_keywords(self) -> None:
        config = {
            "evidence_levels": {
                "danish_guideline": {
                    "priority": 1000,
                    "badge": "DK",
                    "badge_color": "#22c55e",
                    "description": "Danish",
                },
                "unclassified": {
                    "priority": 50,
                    "badge": "Source",
                    "badge_color": "#d1d5db",
                    "description": "Unclassified",
                },
            },
            "library_source_rules": {
                "danish_keywords": ["retningslinje", "vejledning"],
            },
        }
        hierarchy = EvidenceHierarchy(config)
        level = hierarchy.classify_source(kind="library", title="National retningslinje for diabetes")
        assert level.level_id == "danish_guideline"

    def test_classify_library_nordic_keywords(self) -> None:
        config = {
            "evidence_levels": {
                "nordic_guideline": {
                    "priority": 900,
                    "badge": "Nordic",
                    "badge_color": "#3b82f6",
                    "description": "Nordic",
                },
                "unclassified": {
                    "priority": 50,
                    "badge": "Source",
                    "badge_color": "#d1d5db",
                    "description": "Unclassified",
                },
            },
            "library_source_rules": {
                "nordic_keywords": ["riktlinje", "veileder"],
            },
        }
        hierarchy = EvidenceHierarchy(config)
        level = hierarchy.classify_source(kind="library", title="Nationella riktlinje for stroke")
        assert level.level_id == "nordic_guideline"

    def test_get_priority_boost(self) -> None:
        hierarchy = EvidenceHierarchy.from_config(CONFIG_PATH)
        boost_danish = hierarchy.get_priority_boost(url="https://sst.dk/x")
        boost_nice = hierarchy.get_priority_boost(url="https://nice.org.uk/y")
        boost_unknown = hierarchy.get_priority_boost(url="https://example.com/z")

        assert boost_danish > boost_nice
        assert boost_nice > boost_unknown

    def test_get_all_levels_sorted_by_priority(self) -> None:
        hierarchy = EvidenceHierarchy()
        levels = hierarchy.get_all_levels()
        priorities = [lvl.priority for lvl in levels]
        assert priorities == sorted(priorities, reverse=True)


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_classify_source_function(self) -> None:
        # Reset global hierarchy to ensure config_path is used
        import procedurewriter.pipeline.evidence_hierarchy as eh
        eh._hierarchy = None

        level = classify_source(url="https://sst.dk/test", config_path=CONFIG_PATH)
        assert level.level_id == "danish_guideline"

        # Reset again for other tests
        eh._hierarchy = None

    def test_get_evidence_hierarchy_returns_instance(self) -> None:
        hierarchy = get_evidence_hierarchy()
        assert isinstance(hierarchy, EvidenceHierarchy)


class TestFromConfig:
    """Tests for loading from config file."""

    def test_from_config_nonexistent_file_returns_default(self, tmp_path) -> None:
        hierarchy = EvidenceHierarchy.from_config(tmp_path / "nonexistent.yaml")
        # Should use default levels
        levels = hierarchy.get_all_levels()
        assert len(levels) > 0

    def test_from_config_none_returns_default(self) -> None:
        hierarchy = EvidenceHierarchy.from_config(None)
        levels = hierarchy.get_all_levels()
        assert len(levels) > 0

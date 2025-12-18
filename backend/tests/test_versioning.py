"""Tests for the versioning module."""

from procedurewriter.pipeline.versioning import (
    ChangeType,
    Section,
    SectionDiff,
    SourceDiff,
    VersionDiff,
    calculate_text_similarity,
    create_version_diff,
    diff_sections,
    diff_sources,
    diff_to_dict,
    generate_unified_diff,
    normalize_section_heading,
    parse_markdown_sections,
)


class TestParseMarkdownSections:
    """Tests for parse_markdown_sections."""

    def test_single_section(self) -> None:
        md = """# Indledning

Dette er en indledning til proceduren.
"""
        sections = parse_markdown_sections(md)
        assert len(sections) == 1
        assert sections[0].heading == "Indledning"
        assert sections[0].level == 1
        assert "indledning til proceduren" in sections[0].content

    def test_multiple_sections(self) -> None:
        md = """# Indledning

Indledning tekst.

## Baggrund

Baggrund tekst.

## Metode

Metode tekst.
"""
        sections = parse_markdown_sections(md)
        assert len(sections) == 3
        assert sections[0].heading == "Indledning"
        assert sections[0].level == 1
        assert sections[1].heading == "Baggrund"
        assert sections[1].level == 2
        assert sections[2].heading == "Metode"
        assert sections[2].level == 2

    def test_nested_sections(self) -> None:
        md = """# Hovedafsnit

Intro.

## Underafsnit 1

Tekst 1.

### Underunderafsnit

Tekst 1.1.

## Underafsnit 2

Tekst 2.
"""
        sections = parse_markdown_sections(md)
        assert len(sections) == 4
        assert sections[2].level == 3

    def test_empty_content(self) -> None:
        md = """# Tom sektion

# Næste sektion

Med indhold.
"""
        sections = parse_markdown_sections(md)
        assert len(sections) == 2
        assert sections[0].content == ""
        assert "indhold" in sections[1].content

    def test_no_headings(self) -> None:
        md = "Bare noget tekst uden overskrifter."
        sections = parse_markdown_sections(md)
        assert len(sections) == 0


class TestNormalizeSectionHeading:
    """Tests for normalize_section_heading."""

    def test_basic_normalization(self) -> None:
        assert normalize_section_heading("Indledning") == "indledning"
        assert normalize_section_heading("  BAGGRUND  ") == "baggrund"

    def test_numbered_sections(self) -> None:
        assert normalize_section_heading("1. Indledning") == "indledning"
        assert normalize_section_heading("1.2 Baggrund") == "baggrund"
        assert normalize_section_heading("1.2.3 Metode") == "metode"

    def test_lettered_sections(self) -> None:
        assert normalize_section_heading("a) Første punkt") == "første punkt"


class TestCalculateTextSimilarity:
    """Tests for calculate_text_similarity."""

    def test_identical_texts(self) -> None:
        assert calculate_text_similarity("hello", "hello") == 1.0

    def test_completely_different(self) -> None:
        sim = calculate_text_similarity("abc", "xyz")
        assert sim < 0.5

    def test_similar_texts(self) -> None:
        sim = calculate_text_similarity("Dette er en test", "Dette er en prøve")
        assert 0.5 < sim < 1.0

    def test_empty_strings(self) -> None:
        assert calculate_text_similarity("", "") == 1.0
        assert calculate_text_similarity("abc", "") == 0.0
        assert calculate_text_similarity("", "abc") == 0.0


class TestGenerateUnifiedDiff:
    """Tests for generate_unified_diff."""

    def test_no_changes(self) -> None:
        diff = generate_unified_diff("line1\nline2", "line1\nline2")
        assert diff == ""

    def test_added_line(self) -> None:
        diff = generate_unified_diff("line1\nline2", "line1\nline2\nline3")
        assert "+line3" in diff

    def test_removed_line(self) -> None:
        diff = generate_unified_diff("line1\nline2\nline3", "line1\nline2")
        assert "-line3" in diff

    def test_modified_line(self) -> None:
        diff = generate_unified_diff("line1\nold_line\nline3", "line1\nnew_line\nline3")
        assert "-old_line" in diff
        assert "+new_line" in diff


class TestDiffSections:
    """Tests for diff_sections."""

    def test_no_changes(self) -> None:
        sections = [Section("Test", 1, "Content", 0, 2)]
        diffs = diff_sections(sections, sections)
        assert len(diffs) == 1
        assert diffs[0].change_type == ChangeType.UNCHANGED

    def test_added_section(self) -> None:
        old = [Section("Existing", 1, "Old content", 0, 2)]
        new = [
            Section("Existing", 1, "Old content", 0, 2),
            Section("New Section", 1, "New content", 3, 5),
        ]
        diffs = diff_sections(old, new)
        assert len(diffs) == 2
        added = [d for d in diffs if d.change_type == ChangeType.ADDED]
        assert len(added) == 1
        assert added[0].heading == "New Section"

    def test_removed_section(self) -> None:
        old = [
            Section("Keep", 1, "Content", 0, 2),
            Section("Remove", 1, "To be removed", 3, 5),
        ]
        new = [Section("Keep", 1, "Content", 0, 2)]
        diffs = diff_sections(old, new)
        assert len(diffs) == 2
        removed = [d for d in diffs if d.change_type == ChangeType.REMOVED]
        assert len(removed) == 1
        assert removed[0].heading == "Remove"

    def test_modified_section(self) -> None:
        old = [Section("Test", 1, "Old content here", 0, 2)]
        new = [Section("Test", 1, "Completely different content", 0, 2)]
        diffs = diff_sections(old, new)
        assert len(diffs) == 1
        assert diffs[0].change_type == ChangeType.MODIFIED
        assert diffs[0].unified_diff is not None

    def test_heading_normalization(self) -> None:
        """Sections should match even with different heading formats."""
        old = [Section("1. Indledning", 1, "Same content", 0, 2)]
        new = [Section("Indledning", 1, "Same content", 0, 2)]
        diffs = diff_sections(old, new)
        assert len(diffs) == 1
        assert diffs[0].change_type == ChangeType.UNCHANGED


class TestDiffSources:
    """Tests for diff_sources."""

    def test_no_changes(self) -> None:
        sources = ["src1", "src2", "src3"]
        diff = diff_sources(sources, sources)
        assert len(diff.added) == 0
        assert len(diff.removed) == 0
        assert len(diff.unchanged) == 3

    def test_added_sources(self) -> None:
        old = ["src1", "src2"]
        new = ["src1", "src2", "src3", "src4"]
        diff = diff_sources(old, new)
        assert diff.added == ["src3", "src4"]
        assert len(diff.removed) == 0
        assert len(diff.unchanged) == 2

    def test_removed_sources(self) -> None:
        old = ["src1", "src2", "src3"]
        new = ["src1"]
        diff = diff_sources(old, new)
        assert len(diff.added) == 0
        assert diff.removed == ["src2", "src3"]
        assert len(diff.unchanged) == 1

    def test_mixed_changes(self) -> None:
        old = ["src1", "src2", "src3"]
        new = ["src2", "src4"]
        diff = diff_sources(old, new)
        assert diff.added == ["src4"]
        assert sorted(diff.removed) == ["src1", "src3"]
        assert diff.unchanged == ["src2"]


class TestCreateVersionDiff:
    """Tests for create_version_diff."""

    def test_basic_diff(self) -> None:
        old_md = """# Indledning

Gammel indledning.

## Metode

Gammel metode.
"""
        new_md = """# Indledning

Ny indledning med mere tekst.

## Metode

Gammel metode.

## Resultater

Nye resultater.
"""
        diff = create_version_diff(
            old_run_id="run1",
            new_run_id="run2",
            old_version=1,
            new_version=2,
            procedure="Test Procedure",
            old_markdown=old_md,
            new_markdown=new_md,
        )

        assert diff.old_run_id == "run1"
        assert diff.new_run_id == "run2"
        assert diff.has_changes
        assert diff.sections_added == 1  # Resultater
        assert diff.sections_modified == 1  # Indledning
        assert diff.sections_removed == 0

    def test_with_sources(self) -> None:
        diff = create_version_diff(
            old_run_id="run1",
            new_run_id="run2",
            old_version=1,
            new_version=2,
            procedure="Test",
            old_markdown="# Test\n\nContent",
            new_markdown="# Test\n\nContent",
            old_source_ids=["src1", "src2"],
            new_source_ids=["src2", "src3"],
        )

        assert diff.source_diff is not None
        assert diff.source_diff.added == ["src3"]
        assert diff.source_diff.removed == ["src1"]

    def test_summary_generation(self) -> None:
        old_md = "# A\n\nold"
        new_md = "# A\n\nnew\n\n# B\n\nadded"
        diff = create_version_diff(
            old_run_id="r1",
            new_run_id="r2",
            old_version=1,
            new_version=2,
            procedure="P",
            old_markdown=old_md,
            new_markdown=new_md,
            old_source_ids=["s1"],
            new_source_ids=["s2"],
        )

        # Should mention added sections and source changes
        assert "afsnit" in diff.summary.lower()
        assert "kilder" in diff.summary.lower()

    def test_no_changes(self) -> None:
        md = "# Test\n\nSame content"
        diff = create_version_diff(
            old_run_id="r1",
            new_run_id="r2",
            old_version=1,
            new_version=2,
            procedure="P",
            old_markdown=md,
            new_markdown=md,
        )
        assert not diff.has_changes
        assert "ingen" in diff.summary.lower()


class TestDiffToDict:
    """Tests for diff_to_dict."""

    def test_serialization(self) -> None:
        diff = VersionDiff(
            old_run_id="r1",
            new_run_id="r2",
            old_version=1,
            new_version=2,
            procedure="Test",
            section_diffs=[
                SectionDiff(
                    heading="Test",
                    change_type=ChangeType.MODIFIED,
                    old_content="old",
                    new_content="new",
                    similarity=0.5,
                ),
            ],
            source_diff=SourceDiff(
                added=["src1"],
                removed=["src2"],
                unchanged=["src3"],
            ),
            summary="Test summary",
        )

        d = diff_to_dict(diff)

        assert d["old_run_id"] == "r1"
        assert d["new_run_id"] == "r2"
        assert d["has_changes"] is True
        assert len(d["section_diffs"]) == 1
        assert d["section_diffs"][0]["change_type"] == "modified"
        assert d["source_diff"]["added"] == ["src1"]

    def test_no_source_diff(self) -> None:
        diff = VersionDiff(
            old_run_id="r1",
            new_run_id="r2",
            old_version=1,
            new_version=2,
            procedure="Test",
        )
        d = diff_to_dict(diff)
        assert d["source_diff"] is None


class TestVersionDiffProperties:
    """Tests for VersionDiff computed properties."""

    def test_has_changes_with_sections(self) -> None:
        diff = VersionDiff(
            old_run_id="r1",
            new_run_id="r2",
            old_version=1,
            new_version=2,
            procedure="P",
            section_diffs=[
                SectionDiff("A", ChangeType.MODIFIED),
            ],
        )
        assert diff.has_changes

    def test_has_changes_with_sources(self) -> None:
        diff = VersionDiff(
            old_run_id="r1",
            new_run_id="r2",
            old_version=1,
            new_version=2,
            procedure="P",
            section_diffs=[
                SectionDiff("A", ChangeType.UNCHANGED),
            ],
            source_diff=SourceDiff(added=["s1"]),
        )
        assert diff.has_changes

    def test_no_changes(self) -> None:
        diff = VersionDiff(
            old_run_id="r1",
            new_run_id="r2",
            old_version=1,
            new_version=2,
            procedure="P",
            section_diffs=[
                SectionDiff("A", ChangeType.UNCHANGED),
            ],
            source_diff=SourceDiff(unchanged=["s1"]),
        )
        assert not diff.has_changes

    def test_count_properties(self) -> None:
        diff = VersionDiff(
            old_run_id="r1",
            new_run_id="r2",
            old_version=1,
            new_version=2,
            procedure="P",
            section_diffs=[
                SectionDiff("A", ChangeType.ADDED),
                SectionDiff("B", ChangeType.ADDED),
                SectionDiff("C", ChangeType.REMOVED),
                SectionDiff("D", ChangeType.MODIFIED),
                SectionDiff("E", ChangeType.MODIFIED),
                SectionDiff("F", ChangeType.MODIFIED),
                SectionDiff("G", ChangeType.UNCHANGED),
            ],
        )
        assert diff.sections_added == 2
        assert diff.sections_removed == 1
        assert diff.sections_modified == 3

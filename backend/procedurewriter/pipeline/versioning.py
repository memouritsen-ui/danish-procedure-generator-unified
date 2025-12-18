"""
Procedure Versioning & Diff System

Provides structural diff capabilities for comparing procedure versions:
- Section-level diffs (added, removed, modified)
- Source diffs (added, removed sources between versions)
- Text-level changes within sections
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher, unified_diff
from enum import Enum
from pathlib import Path
from typing import Any


class ChangeType(str, Enum):
    """Type of change between versions."""
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    UNCHANGED = "unchanged"


@dataclass
class Section:
    """A section from a markdown procedure document."""
    heading: str
    level: int  # 1 for #, 2 for ##, etc.
    content: str
    line_start: int
    line_end: int

    @property
    def full_text(self) -> str:
        """Full section text including heading."""
        prefix = "#" * self.level
        return f"{prefix} {self.heading}\n{self.content}"


@dataclass
class SectionDiff:
    """Diff result for a single section."""
    heading: str
    change_type: ChangeType
    old_content: str | None = None
    new_content: str | None = None
    unified_diff: str | None = None
    similarity: float = 1.0  # 0-1, how similar the sections are


@dataclass
class SourceDiff:
    """Diff result for sources between versions."""
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)


@dataclass
class VersionDiff:
    """Complete diff between two procedure versions."""
    old_run_id: str
    new_run_id: str
    old_version: int
    new_version: int
    procedure: str
    section_diffs: list[SectionDiff] = field(default_factory=list)
    source_diff: SourceDiff | None = None
    summary: str = ""

    @property
    def has_changes(self) -> bool:
        """Check if there are any changes."""
        return any(
            d.change_type != ChangeType.UNCHANGED
            for d in self.section_diffs
        ) or (
            self.source_diff and (
                len(self.source_diff.added) > 0 or
                len(self.source_diff.removed) > 0
            )
        )

    @property
    def sections_added(self) -> int:
        return sum(1 for d in self.section_diffs if d.change_type == ChangeType.ADDED)

    @property
    def sections_removed(self) -> int:
        return sum(1 for d in self.section_diffs if d.change_type == ChangeType.REMOVED)

    @property
    def sections_modified(self) -> int:
        return sum(1 for d in self.section_diffs if d.change_type == ChangeType.MODIFIED)


def parse_markdown_sections(markdown: str) -> list[Section]:
    """Parse markdown into sections based on headings.

    Args:
        markdown: The markdown text to parse

    Returns:
        List of Section objects
    """
    lines = markdown.split("\n")
    sections: list[Section] = []
    current_heading: str | None = None
    current_level = 0
    current_content: list[str] = []
    current_start = 0

    # Regex for markdown headings (# Heading)
    heading_pattern = re.compile(r"^(#{1,6})\s+(.+)$")

    for i, line in enumerate(lines):
        match = heading_pattern.match(line)
        if match:
            # Save previous section if exists
            if current_heading is not None:
                sections.append(Section(
                    heading=current_heading,
                    level=current_level,
                    content="\n".join(current_content).strip(),
                    line_start=current_start,
                    line_end=i - 1,
                ))

            # Start new section
            current_level = len(match.group(1))
            current_heading = match.group(2).strip()
            current_content = []
            current_start = i
        else:
            current_content.append(line)

    # Don't forget last section
    if current_heading is not None:
        sections.append(Section(
            heading=current_heading,
            level=current_level,
            content="\n".join(current_content).strip(),
            line_start=current_start,
            line_end=len(lines) - 1,
        ))

    return sections


def normalize_section_heading(heading: str) -> str:
    """Normalize heading for comparison (lowercase, strip, remove numbering)."""
    heading = heading.lower().strip()
    # Remove leading numbers like "1.", "1.1", "a)", etc.
    heading = re.sub(r"^[\d.]+\s*", "", heading)
    heading = re.sub(r"^[a-z]\)\s*", "", heading)
    return heading


def calculate_text_similarity(text1: str, text2: str) -> float:
    """Calculate similarity between two texts (0-1)."""
    if not text1 and not text2:
        return 1.0
    if not text1 or not text2:
        return 0.0
    return SequenceMatcher(None, text1, text2).ratio()


def generate_unified_diff(old_text: str, new_text: str, context: int = 3) -> str:
    """Generate unified diff between two texts."""
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)

    diff = unified_diff(
        old_lines,
        new_lines,
        fromfile="old",
        tofile="new",
        lineterm="",
        n=context,
    )
    return "".join(diff)


def diff_sections(
    old_sections: list[Section],
    new_sections: list[Section],
    similarity_threshold: float = 0.6,
) -> list[SectionDiff]:
    """Compare two lists of sections and generate diffs.

    Args:
        old_sections: Sections from old version
        new_sections: Sections from new version
        similarity_threshold: Minimum similarity (0-1) to consider sections as modified vs. replaced

    Returns:
        List of SectionDiff objects
    """
    diffs: list[SectionDiff] = []

    # Create normalized heading maps
    old_by_heading = {normalize_section_heading(s.heading): s for s in old_sections}
    new_by_heading = {normalize_section_heading(s.heading): s for s in new_sections}

    all_headings = set(old_by_heading.keys()) | set(new_by_heading.keys())

    for norm_heading in sorted(all_headings):
        old_section = old_by_heading.get(norm_heading)
        new_section = new_by_heading.get(norm_heading)

        if old_section and new_section:
            # Section exists in both - check if modified
            similarity = calculate_text_similarity(old_section.content, new_section.content)

            if similarity >= 0.99:  # Effectively unchanged
                diffs.append(SectionDiff(
                    heading=new_section.heading,
                    change_type=ChangeType.UNCHANGED,
                    old_content=old_section.content,
                    new_content=new_section.content,
                    similarity=similarity,
                ))
            else:
                diffs.append(SectionDiff(
                    heading=new_section.heading,
                    change_type=ChangeType.MODIFIED,
                    old_content=old_section.content,
                    new_content=new_section.content,
                    unified_diff=generate_unified_diff(old_section.content, new_section.content),
                    similarity=similarity,
                ))

        elif old_section and not new_section:
            # Section removed
            diffs.append(SectionDiff(
                heading=old_section.heading,
                change_type=ChangeType.REMOVED,
                old_content=old_section.content,
                similarity=0.0,
            ))

        else:
            # Section added
            diffs.append(SectionDiff(
                heading=new_section.heading,  # type: ignore
                change_type=ChangeType.ADDED,
                new_content=new_section.content,  # type: ignore
                similarity=0.0,
            ))

    return diffs


def diff_sources(old_source_ids: list[str], new_source_ids: list[str]) -> SourceDiff:
    """Compare source lists between versions.

    Args:
        old_source_ids: Source IDs from old version
        new_source_ids: Source IDs from new version

    Returns:
        SourceDiff with added, removed, and unchanged sources
    """
    old_set = set(old_source_ids)
    new_set = set(new_source_ids)

    return SourceDiff(
        added=sorted(new_set - old_set),
        removed=sorted(old_set - new_set),
        unchanged=sorted(old_set & new_set),
    )


def create_version_diff(
    old_run_id: str,
    new_run_id: str,
    old_version: int,
    new_version: int,
    procedure: str,
    old_markdown: str,
    new_markdown: str,
    old_source_ids: list[str] | None = None,
    new_source_ids: list[str] | None = None,
) -> VersionDiff:
    """Create a complete diff between two procedure versions.

    Args:
        old_run_id: Run ID of older version
        new_run_id: Run ID of newer version
        old_version: Version number of older version
        new_version: Version number of newer version
        procedure: Procedure name
        old_markdown: Markdown content of older version
        new_markdown: Markdown content of newer version
        old_source_ids: Optional source IDs from old version
        new_source_ids: Optional source IDs from new version

    Returns:
        VersionDiff object with complete comparison
    """
    # Parse sections
    old_sections = parse_markdown_sections(old_markdown)
    new_sections = parse_markdown_sections(new_markdown)

    # Diff sections
    section_diffs = diff_sections(old_sections, new_sections)

    # Diff sources if provided
    source_diff = None
    if old_source_ids is not None and new_source_ids is not None:
        source_diff = diff_sources(old_source_ids, new_source_ids)

    # Create diff object
    diff = VersionDiff(
        old_run_id=old_run_id,
        new_run_id=new_run_id,
        old_version=old_version,
        new_version=new_version,
        procedure=procedure,
        section_diffs=section_diffs,
        source_diff=source_diff,
    )

    # Generate summary
    parts = []
    if diff.sections_added:
        parts.append(f"{diff.sections_added} afsnit tilføjet")
    if diff.sections_removed:
        parts.append(f"{diff.sections_removed} afsnit fjernet")
    if diff.sections_modified:
        parts.append(f"{diff.sections_modified} afsnit ændret")
    if source_diff:
        if source_diff.added:
            parts.append(f"{len(source_diff.added)} kilder tilføjet")
        if source_diff.removed:
            parts.append(f"{len(source_diff.removed)} kilder fjernet")

    diff.summary = ", ".join(parts) if parts else "Ingen ændringer"

    return diff


def load_procedure_markdown(run_dir: Path) -> str | None:
    """Load procedure markdown from a run directory.

    Args:
        run_dir: Path to the run directory

    Returns:
        Markdown content or None if not found
    """
    # Try standard output path
    procedure_path = run_dir / "procedure.md"
    if procedure_path.exists():
        return procedure_path.read_text(encoding="utf-8")

    # Try manifest.json for procedure_md field
    manifest_path = run_dir / "manifest.json"
    if manifest_path.exists():
        import json
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if "procedure_md" in manifest:
                return manifest["procedure_md"]
        except (json.JSONDecodeError, KeyError):
            pass

    return None


def load_source_ids(run_dir: Path) -> list[str]:
    """Load source IDs from a run directory.

    Args:
        run_dir: Path to the run directory

    Returns:
        List of source IDs
    """
    import json

    source_ids: list[str] = []
    sources_path = run_dir / "sources.jsonl"

    if sources_path.exists():
        with sources_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        record = json.loads(line)
                        if "source_id" in record:
                            source_ids.append(record["source_id"])
                    except json.JSONDecodeError:
                        pass

    return source_ids


def diff_to_dict(diff: VersionDiff) -> dict[str, Any]:
    """Convert VersionDiff to a JSON-serializable dict.

    Args:
        diff: The VersionDiff to convert

    Returns:
        Dictionary representation
    """
    return {
        "old_run_id": diff.old_run_id,
        "new_run_id": diff.new_run_id,
        "old_version": diff.old_version,
        "new_version": diff.new_version,
        "procedure": diff.procedure,
        "has_changes": diff.has_changes,
        "summary": diff.summary,
        "sections_added": diff.sections_added,
        "sections_removed": diff.sections_removed,
        "sections_modified": diff.sections_modified,
        "section_diffs": [
            {
                "heading": sd.heading,
                "change_type": sd.change_type.value,
                "old_content": sd.old_content,
                "new_content": sd.new_content,
                "unified_diff": sd.unified_diff,
                "similarity": round(sd.similarity, 3),
            }
            for sd in diff.section_diffs
        ],
        "source_diff": {
            "added": diff.source_diff.added,
            "removed": diff.source_diff.removed,
            "unchanged": diff.source_diff.unchanged,
        } if diff.source_diff else None,
    }

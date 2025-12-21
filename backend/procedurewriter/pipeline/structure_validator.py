from __future__ import annotations

from dataclasses import dataclass

from procedurewriter.pipeline.versioning import normalize_section_heading, parse_markdown_sections


class StructureValidationError(ValueError):
    """Raised when required section structure is missing or out of order."""


@dataclass(frozen=True)
class StructureValidationResult:
    required_headings: list[str]
    found_headings: list[str]
    missing_headings: list[str]
    out_of_order_headings: list[str]
    wrong_level_headings: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "required_headings": self.required_headings,
            "found_headings": self.found_headings,
            "missing_headings": self.missing_headings,
            "out_of_order_headings": self.out_of_order_headings,
            "wrong_level_headings": self.wrong_level_headings,
        }

    @property
    def is_valid(self) -> bool:
        return not (self.missing_headings or self.out_of_order_headings or self.wrong_level_headings)


def validate_required_sections(
    markdown_text: str,
    *,
    required_headings: list[str],
    required_level: int = 2,
) -> StructureValidationResult:
    """Validate that required headings exist and appear in the correct order."""
    sections = parse_markdown_sections(markdown_text)
    found_by_norm: dict[str, tuple[str, int, int]] = {}
    for idx, sec in enumerate(sections):
        norm = normalize_section_heading(sec.heading)
        if norm not in found_by_norm:
            found_by_norm[norm] = (sec.heading, sec.level, idx)

    required_norms = [normalize_section_heading(h) for h in required_headings]
    missing: list[str] = []
    wrong_level: list[str] = []
    found_headings: list[str] = []
    order_indices: list[tuple[str, int]] = []

    for heading, norm in zip(required_headings, required_norms):
        found = found_by_norm.get(norm)
        if not found:
            missing.append(heading)
            continue
        found_headings.append(found[0])
        if found[1] != required_level:
            wrong_level.append(found[0])
        order_indices.append((heading, found[2]))

    out_of_order: list[str] = []
    last_idx = -1
    for heading, idx in order_indices:
        if idx < last_idx:
            out_of_order.append(heading)
        last_idx = max(last_idx, idx)

    return StructureValidationResult(
        required_headings=required_headings,
        found_headings=found_headings,
        missing_headings=missing,
        out_of_order_headings=out_of_order,
        wrong_level_headings=wrong_level,
    )

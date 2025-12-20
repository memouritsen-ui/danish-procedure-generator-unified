"""Pipeline processor for integrating all phases.

Phase 5: Pipeline Integration
Integrates all Phase 1-4 components into a unified processing flow.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from procedurewriter.pipeline.anatomical_requirements import (
    AnatomicalValidator,
    ValidationResult,
)
from procedurewriter.pipeline.clinical_prompts import PromptEnhancer
from procedurewriter.pipeline.deduplication import RepetitionDetector
from procedurewriter.pipeline.workflow_filter import WorkflowFilter


@dataclass
class ProcessingResult:
    """Result of processing procedure content through the pipeline."""

    filtered_content: str
    workflow_removed: list[str]
    anatomical_validation: ValidationResult
    quality_score: float
    suggestions: list[str] = field(default_factory=list)


@dataclass
class SectionProcessingResult:
    """Result of processing sectioned procedure content."""

    filtered_sections: dict[str, list[str]]
    workflow_removed: list[str]
    anatomical_validation: ValidationResult
    quality_score: float
    suggestions: list[str] = field(default_factory=list)


class QualityScorer:
    """Scores the quality of procedure content."""

    def __init__(self) -> None:
        self._weights = {
            "workflow_penalty": 0.4,  # High workflow = penalty
            "anatomical_completeness": 0.4,
            "content_density": 0.2,
        }

    def score(
        self,
        procedure_name: str,
        content: str,
        workflow_percentage: float,
        anatomical_completeness: float,
    ) -> float:
        """Calculate quality score for procedure content.

        Args:
            procedure_name: Name of the procedure
            content: The content to score
            workflow_percentage: Percentage of content that was workflow (0-1)
            anatomical_completeness: Anatomical completeness score (0-1)

        Returns:
            Quality score between 0 and 1
        """
        # Workflow penalty (more workflow = lower score)
        workflow_score = 1.0 - workflow_percentage

        # Content density (longer content = higher score, up to a point)
        content_length = len(content.strip())
        if content_length < 50:
            density_score = 0.2
        elif content_length < 200:
            density_score = 0.5
        elif content_length < 500:
            density_score = 0.8
        else:
            density_score = 1.0

        # Weighted combination
        total = (
            self._weights["workflow_penalty"] * workflow_score
            + self._weights["anatomical_completeness"] * anatomical_completeness
            + self._weights["content_density"] * density_score
        )

        return max(0.0, min(1.0, total))


class PipelineProcessor:
    """Integrates all pipeline phases into unified processing."""

    def __init__(self) -> None:
        self._workflow_filter = WorkflowFilter()
        self._deduplicator = RepetitionDetector()
        self._validator = AnatomicalValidator()
        self._prompt_enhancer = PromptEnhancer()
        self._scorer = QualityScorer()

    def process(self, procedure_name: str, content: str) -> ProcessingResult:
        """Process content through the full pipeline.

        Args:
            procedure_name: Name of the procedure (e.g., "pleuradræn")
            content: Raw content to process

        Returns:
            ProcessingResult with filtered content and quality metrics
        """
        # Phase 2: Filter workflow content
        clinical_content, workflow_content = self._workflow_filter.filter_workflow_content(
            content
        )

        # Track removed workflow items
        # WorkflowFilter joins segments with spaces, so split by sentence endings
        workflow_removed = []
        if workflow_content.strip():
            # Split by sentence-ending punctuation
            segments = re.split(r"(?<=[.!?])\s+", workflow_content.strip())
            workflow_removed = [s.strip() for s in segments if s.strip()]

        # Phase 2: Deduplicate
        # Split by actual line breaks to preserve structure
        lines = clinical_content.strip().split("\n")

        # Separate markdown structure from content lines
        content_lines = []
        structure_map = []  # Track position and type of each line

        for line in lines:
            stripped = line.strip()
            if not stripped:
                # Empty line - preserve for paragraph breaks
                structure_map.append(("empty", ""))
            elif self._is_markdown_heading(stripped):
                # Markdown heading - preserve as-is, don't deduplicate
                structure_map.append(("heading", stripped))
            elif self._is_markdown_bullet(stripped):
                # Bullet point - deduplicate content but preserve structure
                structure_map.append(("content", stripped))
                content_lines.append(stripped)
            else:
                # Regular content - deduplicate
                structure_map.append(("content", stripped))
                content_lines.append(stripped)

        # Deduplicate only the content lines (not headings or structure)
        if content_lines:
            deduped_content = self._deduplicator.deduplicate(content_lines)
            deduped_set = set(deduped_content)

            # Rebuild with structure preserved
            filtered_lines = []
            for line_type, line_text in structure_map:
                if line_type == "heading":
                    # Always keep headings
                    filtered_lines.append(line_text)
                elif line_type == "empty":
                    # Keep empty lines for structure
                    filtered_lines.append("")
                elif line_type == "content":
                    # Only keep if deduplicator kept it
                    if line_text in deduped_set:
                        filtered_lines.append(line_text)
                        deduped_set.discard(line_text)  # Remove to handle duplicates correctly

            # Preserve markdown paragraph breaks
            filtered_content = self._preserve_paragraph_breaks(filtered_lines)
        else:
            filtered_content = ""

        # Renumber steps after filtering
        filtered_content = self._renumber_steps(filtered_content)

        # Phase 3: Validate anatomical content
        anatomical_validation = self._validator.validate(procedure_name, filtered_content)

        # Calculate workflow percentage
        original_length = len(content.strip()) if content.strip() else 1
        workflow_length = len(workflow_content.strip())
        workflow_percentage = workflow_length / original_length

        # Calculate quality score
        quality_score = self._scorer.score(
            procedure_name=procedure_name,
            content=filtered_content,
            workflow_percentage=workflow_percentage,
            anatomical_completeness=anatomical_validation.completeness_score,
        )

        # Generate suggestions based on validation
        suggestions = self._generate_suggestions(anatomical_validation, quality_score)

        return ProcessingResult(
            filtered_content=filtered_content,
            workflow_removed=workflow_removed,
            anatomical_validation=anatomical_validation,
            quality_score=quality_score,
            suggestions=suggestions,
        )

    def process_sections(
        self, procedure_name: str, sections: dict[str, list[str]]
    ) -> SectionProcessingResult:
        """Process sectioned content through the pipeline.

        Args:
            procedure_name: Name of the procedure
            sections: Dict mapping section names to lists of content items

        Returns:
            SectionProcessingResult with filtered sections
        """
        filtered_sections: dict[str, list[str]] = {}
        all_workflow_removed: list[str] = []
        all_content: list[str] = []

        for section_name, items in sections.items():
            filtered_items: list[str] = []
            for item in items:
                clinical, workflow = self._workflow_filter.filter_workflow_content(item)
                if clinical.strip():
                    filtered_items.append(clinical.strip())
                if workflow.strip():
                    all_workflow_removed.append(workflow.strip())

            # Deduplicate within section
            if filtered_items:
                deduped = self._deduplicator.deduplicate(filtered_items)
                filtered_sections[section_name] = list(deduped)
                all_content.extend(deduped)
            else:
                filtered_sections[section_name] = []

        # Validate combined content
        combined = " ".join(all_content)
        anatomical_validation = self._validator.validate(procedure_name, combined)

        # Calculate metrics
        total_original = sum(len(" ".join(items)) for items in sections.values())
        total_workflow = sum(len(w) for w in all_workflow_removed)
        workflow_percentage = total_workflow / total_original if total_original > 0 else 0

        quality_score = self._scorer.score(
            procedure_name=procedure_name,
            content=combined,
            workflow_percentage=workflow_percentage,
            anatomical_completeness=anatomical_validation.completeness_score,
        )

        suggestions = self._generate_suggestions(anatomical_validation, quality_score)

        return SectionProcessingResult(
            filtered_sections=filtered_sections,
            workflow_removed=all_workflow_removed,
            anatomical_validation=anatomical_validation,
            quality_score=quality_score,
            suggestions=suggestions,
        )

    def enhance_prompt(self, original_prompt: str, procedure_name: str) -> str:
        """Enhance a prompt with clinical constraints.

        Args:
            original_prompt: The original prompt to enhance
            procedure_name: Name of the procedure

        Returns:
            Enhanced prompt with clinical focus
        """
        return self._prompt_enhancer.enhance(original_prompt, procedure_name)

    def _renumber_steps(self, content: str) -> str:
        """Renumber steps sequentially after filtering.

        Handles patterns like:
        - "1. Step text"
        - "1) Step text"

        Args:
            content: Content with potentially non-sequential step numbers

        Returns:
            Content with renumbered steps (1, 2, 3, ...)
        """
        lines = content.split("\n")
        result_lines = []
        current_step = 1

        for line in lines:
            stripped = line.strip()
            if not stripped:
                result_lines.append(line)
                continue

            # Match numbered step patterns: "1. text" or "1) text"
            match = re.match(r"^(\d+)([.\)])\s*(.*)$", stripped)
            if match:
                separator = match.group(2)  # "." or ")"
                text = match.group(3)
                result_lines.append(f"{current_step}{separator} {text}")
                current_step += 1
            else:
                result_lines.append(line)

        return "\n".join(result_lines)

    def _generate_suggestions(
        self, validation: ValidationResult, quality_score: float
    ) -> list[str]:
        """Generate improvement suggestions based on validation.

        Args:
            validation: Anatomical validation result
            quality_score: Calculated quality score

        Returns:
            List of actionable suggestions
        """
        suggestions: list[str] = []

        # Add suggestions for missing landmarks
        if validation.missing_landmarks:
            for landmark in validation.missing_landmarks[:3]:  # Top 3
                suggestions.append(f"Tilføj anatomisk landemærke: {landmark}")

        # Add depth suggestion if missing
        if not validation.has_depth_guidance:
            suggestions.append(
                "Tilføj dybdevejledning (f.eks. 'avancér 2-3 cm' eller 'depth of X cm')"
            )

        # Add angle suggestion if missing
        if not validation.has_angle_guidance:
            suggestions.append(
                "Tilføj vinkelguidance (f.eks. '45 graders vinkel' eller 'kranial retning')"
            )

        # General quality suggestions
        if quality_score < 0.5:
            suggestions.append(
                "Fokusér på klinisk indhold frem for workflow-beskrivelser"
            )

        return suggestions

    def _is_markdown_separator(self, line: str) -> bool:
        """Check if line represents a markdown structural element.

        Args:
            line: Line to check

        Returns:
            True if line is empty or markdown structure
        """
        # Empty lines are structural separators in markdown
        return not line.strip()

    def _is_markdown_heading(self, line: str) -> bool:
        """Check if line is a markdown heading.

        Args:
            line: Line to check

        Returns:
            True if line is a markdown heading (starts with #)
        """
        return line.strip().startswith("#")

    def _is_markdown_bullet(self, line: str) -> bool:
        """Check if line is a markdown bullet point.

        Args:
            line: Line to check

        Returns:
            True if line is a bullet point (starts with - or *)
        """
        stripped = line.strip()
        return stripped.startswith("- ") or stripped.startswith("* ")

    def _preserve_paragraph_breaks(self, lines: list[str]) -> str:
        """Preserve paragraph breaks (double newlines) in markdown content.

        Args:
            lines: List of content lines

        Returns:
            Content with paragraph breaks preserved
        """
        result = []
        previous_was_heading = False

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Check if this is a markdown heading
            is_heading = stripped.startswith("#")

            # Add double newline before headings (except the first one)
            if is_heading and result:
                # Add blank line before heading for paragraph separation
                if result and result[-1] != "":
                    result.append("")

            result.append(line)
            previous_was_heading = is_heading

        return "\n".join(result)

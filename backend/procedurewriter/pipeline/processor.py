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
        # WorkflowFilter joins segments with spaces, so split by sentence endings
        sentences = re.split(r"(?<=[.!?])\s+", clinical_content.strip())
        sentences = [s.strip() for s in sentences if s.strip()]
        if sentences:
            deduped_sentences = self._deduplicator.deduplicate(sentences)
            filtered_content = " ".join(deduped_sentences)
        else:
            filtered_content = ""

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

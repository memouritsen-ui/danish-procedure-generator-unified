"""Stage 05: Draft - Generate procedure draft using WriterAgent.

The Draft stage produces structured procedure content:
1. Receives notes from Stage 04 (EvidenceNotes)
2. Converts notes to source references for Writer
3. Calls WriterAgent to generate structured procedure draft
4. Outputs draft markdown for ClaimExtract stage
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

from procedurewriter.agents.models import SourceReference, WriterInput
from procedurewriter.pipeline.events import EventType
from procedurewriter.pipeline.stages.base import PipelineStage

if TYPE_CHECKING:
    from procedurewriter.agents.writer import WriterAgent
    from procedurewriter.pipeline.events import EventEmitter

logger = logging.getLogger(__name__)

# Default procedure outline (standard Danish emergency procedure sections)
DEFAULT_OUTLINE = [
    "Indikationer",
    "Kontraindikationer",
    "Udstyr og forberedelse",
    "Procedure",
    "Efterbehandling og overvågning",
    "Komplikationer",
    "Særlige patientgrupper",
    "Dokumentation",
]


@dataclass
class EvidenceNoteRef:
    """Reference to an evidence note for the Draft stage.

    Lightweight representation of evidence notes for drafting.

    Attributes:
        chunk_id: UUID of the source evidence chunk.
        source_id: Source document ID (e.g., "SRC001").
        summary: The clinical summary text.
        source_title: Title of the source document.
        source_type: Type of source (guideline, review, etc.).
    """

    chunk_id: UUID
    source_id: str
    summary: str
    source_title: str = ""
    source_type: str = ""


@dataclass
class DraftInput:
    """Input for the Draft stage."""

    run_id: str
    run_dir: Path
    procedure_title: str
    notes: list[EvidenceNoteRef]
    outline: list[str] | None = None
    style_guide: str | None = None
    emitter: "EventEmitter | None" = None


class TemplateNotFoundError(Exception):
    """R4-010: Raised when required template is not found."""

    pass


@dataclass
class DraftOutput:
    """Output from the Draft stage."""

    run_id: str
    run_dir: Path
    procedure_title: str
    content_markdown: str
    sections: list[str]
    citations_used: list[str]
    word_count: int = 0
    success: bool = True
    error: str | None = None
    missing_sections: list[str] = field(default_factory=list)  # R4-011: Track missing sections


class DraftStage(PipelineStage[DraftInput, DraftOutput]):
    """Stage 05: Draft - Generate procedure draft using WriterAgent."""

    def __init__(self, writer_agent: "WriterAgent | None" = None) -> None:
        """Initialize the Draft stage.

        Args:
            writer_agent: Optional WriterAgent to use. If not provided,
                          will be created on first use.
        """
        self._writer_agent = writer_agent

    @property
    def name(self) -> str:
        """Return the stage name."""
        return "draft"

    def _get_writer_agent(self) -> "WriterAgent":
        """Get or create the WriterAgent."""
        if self._writer_agent is None:
            from procedurewriter.agents.writer import WriterAgent
            from procedurewriter.llm import get_llm_client

            llm_client = get_llm_client()
            self._writer_agent = WriterAgent(llm_client=llm_client)
        return self._writer_agent

    def execute(self, input_data: DraftInput) -> DraftOutput:
        """Execute the draft stage.

        Calls WriterAgent to generate structured procedure content.

        Args:
            input_data: Draft input containing notes and config

        Returns:
            Draft output with generated markdown content
        """
        # Emit progress event if emitter provided
        if input_data.emitter is not None:
            input_data.emitter.emit(
                EventType.PROGRESS,
                {
                    "message": f"Generating draft for {input_data.procedure_title}",
                    "stage": "draft",
                    "notes_count": len(input_data.notes),
                },
            )

        try:
            # Convert notes to source references
            sources = self._notes_to_sources(input_data.notes)

            # Build writer input
            writer_input = WriterInput(
                procedure_title=input_data.procedure_title,
                sources=sources,
                outline=input_data.outline or DEFAULT_OUTLINE,
                style_guide=input_data.style_guide,
            )

            # Call writer agent
            writer = self._get_writer_agent()
            result = writer.execute(writer_input)

            if not result.output.success:
                logger.error(f"WriterAgent failed: {result.output.error}")
                return DraftOutput(
                    run_id=input_data.run_id,
                    run_dir=input_data.run_dir,
                    procedure_title=input_data.procedure_title,
                    content_markdown="",
                    sections=[],
                    citations_used=[],
                    word_count=0,
                    success=False,
                    error=result.output.error,
                )

            # Save draft to file
            self._save_draft(input_data.run_dir, result.output.content_markdown)

            # R4-011: Check for missing sections from outline
            expected_sections = set(input_data.outline or DEFAULT_OUTLINE)
            generated_sections = set(result.output.sections)
            missing_sections = list(expected_sections - generated_sections)

            if missing_sections:
                logger.warning(
                    f"R4-011: Missing {len(missing_sections)} expected sections: {missing_sections}"
                )

            logger.info(
                f"Generated draft with {result.output.word_count} words, "
                f"{len(result.output.sections)} sections"
            )

            return DraftOutput(
                run_id=input_data.run_id,
                run_dir=input_data.run_dir,
                procedure_title=input_data.procedure_title,
                content_markdown=result.output.content_markdown,
                sections=result.output.sections,
                citations_used=result.output.citations_used,
                word_count=result.output.word_count,
                success=True,
                missing_sections=missing_sections,  # R4-011
            )

        except Exception as e:
            logger.error(f"Draft stage failed: {e}")
            return DraftOutput(
                run_id=input_data.run_id,
                run_dir=input_data.run_dir,
                procedure_title=input_data.procedure_title,
                content_markdown="",
                sections=[],
                citations_used=[],
                word_count=0,
                success=False,
                error=str(e),
            )

    def _notes_to_sources(
        self, notes: list[EvidenceNoteRef]
    ) -> list[SourceReference]:
        """Convert evidence notes to source references for Writer.

        Args:
            notes: List of evidence notes

        Returns:
            List of SourceReference objects for WriterAgent
        """
        sources: list[SourceReference] = []
        seen_ids: set[str] = set()

        for note in notes:
            # Deduplicate by source_id
            if note.source_id in seen_ids:
                continue
            seen_ids.add(note.source_id)

            sources.append(
                SourceReference(
                    source_id=note.source_id,
                    title=note.source_title or note.source_id,
                    source_type=note.source_type,
                    abstract_excerpt=note.summary,
                )
            )

        return sources

    def _save_draft(self, run_dir: Path, content: str) -> None:
        """Save draft content to run directory.

        Args:
            run_dir: Directory for this pipeline run
            content: Markdown content to save
        """
        draft_file = run_dir / "draft.md"
        try:
            draft_file.write_text(content, encoding="utf-8")
            logger.debug(f"Saved draft to {draft_file}")
        except Exception as e:
            logger.warning(f"Failed to save draft file: {e}")

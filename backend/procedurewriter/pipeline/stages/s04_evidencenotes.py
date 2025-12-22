"""Stage 04: EvidenceNotes - Generate clinical notes from evidence chunks.

The EvidenceNotes stage processes chunks using LLM:
1. Receives chunks from Stage 03 (Chunk)
2. Calls LLM to generate clinical notes for each chunk
3. Creates EvidenceNote objects with structured summaries
4. Outputs notes for Draft stage to use
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from procedurewriter.models.evidence import EvidenceChunk
from procedurewriter.pipeline.events import EventType
from procedurewriter.pipeline.stages.base import PipelineStage

if TYPE_CHECKING:
    from procedurewriter.llm.providers import LLMProvider
    from procedurewriter.pipeline.events import EventEmitter

logger = logging.getLogger(__name__)

# Default model for evidence notes (use cheaper model for summarization)
DEFAULT_MODEL = "gpt-4o-mini"

# System prompt for generating clinical notes
SYSTEM_PROMPT = """You are a medical documentation specialist. Your task is to extract key clinical information from evidence chunks.

For each evidence chunk, create a concise clinical note that:
1. Identifies the main clinical finding or recommendation
2. Notes any dosages, thresholds, or specific values
3. Highlights contraindications or warnings if present
4. Preserves source attribution information

Output a single, focused summary paragraph (2-4 sentences).
Use professional medical terminology appropriate for Danish emergency medicine documentation."""


@dataclass
class EvidenceNote:
    """A clinical note extracted from an evidence chunk.

    Attributes:
        id: Unique identifier for this note.
        chunk_id: UUID of the source evidence chunk.
        summary: The clinical summary text.
        source_title: Title of the source document.
        source_type: Type of source (guideline, review, etc.).
        created_at: When this note was created.
    """

    id: UUID = field(default_factory=uuid4)
    chunk_id: UUID = field(default_factory=uuid4)
    summary: str = ""
    source_title: str = ""
    source_type: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class EvidenceNotesInput:
    """Input for the EvidenceNotes stage."""

    run_id: str
    run_dir: Path
    procedure_title: str
    chunks: list[EvidenceChunk]
    model: str = DEFAULT_MODEL
    emitter: "EventEmitter | None" = None


@dataclass
class EvidenceNotesOutput:
    """Output from the EvidenceNotes stage."""

    run_id: str
    run_dir: Path
    procedure_title: str
    notes: list[EvidenceNote]
    total_notes: int
    chunks_processed: int = 0
    chunks_failed: int = 0


class EvidenceNotesStage(PipelineStage[EvidenceNotesInput, EvidenceNotesOutput]):
    """Stage 04: EvidenceNotes - Generate clinical notes from evidence chunks."""

    def __init__(self, llm_client: "LLMProvider | None" = None) -> None:
        """Initialize the EvidenceNotes stage.

        Args:
            llm_client: Optional LLM client to use. If not provided,
                        will be created on first use.
        """
        self._llm_client = llm_client

    @property
    def name(self) -> str:
        """Return the stage name."""
        return "evidencenotes"

    def _get_llm_client(self) -> "LLMProvider":
        """Get or create the LLM client."""
        if self._llm_client is None:
            from procedurewriter.llm import get_llm_client

            self._llm_client = get_llm_client()
        return self._llm_client

    def execute(self, input_data: EvidenceNotesInput) -> EvidenceNotesOutput:
        """Execute the evidence notes stage.

        Processes each chunk with LLM to generate clinical notes.

        Args:
            input_data: EvidenceNotes input containing chunks and config

        Returns:
            EvidenceNotes output with list of EvidenceNote objects
        """
        # Emit progress event if emitter provided
        if input_data.emitter is not None:
            input_data.emitter.emit(
                EventType.PROGRESS,
                {
                    "message": f"Generating evidence notes for {input_data.procedure_title}",
                    "stage": "evidencenotes",
                    "total_chunks": len(input_data.chunks),
                },
            )

        notes: list[EvidenceNote] = []
        chunks_processed = 0
        chunks_failed = 0

        for i, chunk in enumerate(input_data.chunks):
            try:
                # Generate note for this chunk
                note = self._generate_note(
                    chunk=chunk,
                    procedure_title=input_data.procedure_title,
                    model=input_data.model,
                )
                notes.append(note)
                chunks_processed += 1

                # Emit progress update
                if input_data.emitter is not None and (i + 1) % 5 == 0:
                    input_data.emitter.emit(
                        EventType.PROGRESS,
                        {
                            "message": f"Processed {i + 1}/{len(input_data.chunks)} chunks",
                            "stage": "evidencenotes",
                        },
                    )

            except Exception as e:
                logger.warning(f"Error generating note for chunk {chunk.id}: {e}")
                chunks_failed += 1

        logger.info(
            f"Generated {len(notes)} notes from {chunks_processed} chunks "
            f"({chunks_failed} failed)"
        )

        return EvidenceNotesOutput(
            run_id=input_data.run_id,
            run_dir=input_data.run_dir,
            procedure_title=input_data.procedure_title,
            notes=notes,
            total_notes=len(notes),
            chunks_processed=chunks_processed,
            chunks_failed=chunks_failed,
        )

    def _generate_note(
        self,
        chunk: EvidenceChunk,
        procedure_title: str,
        model: str,
    ) -> EvidenceNote:
        """Generate a clinical note from a single chunk.

        Args:
            chunk: The evidence chunk to summarize
            procedure_title: Title of the procedure for context
            model: LLM model to use

        Returns:
            EvidenceNote with the generated summary
        """
        llm = self._get_llm_client()

        # Build prompt with chunk context
        source_title = chunk.metadata.get("source_title", "Unknown source")
        source_type = chunk.metadata.get("source_type", "unclassified")

        user_prompt = f"""Procedure: {procedure_title}
Source: {source_title} ({source_type})

Evidence text:
{chunk.text}

Generate a concise clinical note summarizing the key findings from this evidence."""

        response = llm.chat_completion(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            model=model,
            temperature=0.3,  # Low temperature for consistent output
            max_tokens=300,  # Keep notes concise
        )

        return EvidenceNote(
            chunk_id=chunk.id,
            summary=response.content.strip(),
            source_title=source_title,
            source_type=source_type,
        )

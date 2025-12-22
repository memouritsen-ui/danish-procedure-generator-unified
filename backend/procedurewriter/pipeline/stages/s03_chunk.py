"""Stage 03: Chunk - Split source content into evidence chunks.

The Chunk stage processes retrieved sources:
1. Reads raw content from sources in run_dir/raw/
2. Splits content into semantically meaningful chunks
3. Creates EvidenceChunk objects with metadata
4. Outputs chunks for evidence notes extraction
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from procedurewriter.models.evidence import EvidenceChunk
from procedurewriter.pipeline.events import EventType
from procedurewriter.pipeline.stages.base import PipelineStage
from procedurewriter.pipeline.stages.s02_retrieve import SourceInfo

if TYPE_CHECKING:
    from procedurewriter.pipeline.events import EventEmitter

logger = logging.getLogger(__name__)

# Default chunk configuration
DEFAULT_CHUNK_SIZE = 1000  # characters
DEFAULT_CHUNK_OVERLAP = 100  # characters


@dataclass
class ChunkInput:
    """Input for the Chunk stage."""

    run_id: str
    run_dir: Path
    procedure_title: str
    sources: list[SourceInfo]
    raw_content_dir: Path
    chunk_size: int = DEFAULT_CHUNK_SIZE
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP
    emitter: EventEmitter | None = None


@dataclass
class ChunkOutput:
    """Output from the Chunk stage."""

    run_id: str
    run_dir: Path
    procedure_title: str
    chunks: list[EvidenceChunk]
    total_chunks: int
    sources_processed: int = 0


class ChunkStage(PipelineStage[ChunkInput, ChunkOutput]):
    """Stage 03: Chunk - Split source content into evidence chunks."""

    @property
    def name(self) -> str:
        """Return the stage name."""
        return "chunk"

    def execute(self, input_data: ChunkInput) -> ChunkOutput:
        """Execute the chunk stage.

        Reads source content and splits into evidence chunks.

        Args:
            input_data: Chunk input containing sources and config

        Returns:
            Chunk output with list of EvidenceChunk objects
        """
        # Emit progress event if emitter provided
        if input_data.emitter is not None:
            input_data.emitter.emit(
                EventType.PROGRESS,
                {
                    "message": f"Chunking sources for {input_data.procedure_title}",
                    "stage": "chunk",
                },
            )

        all_chunks: list[EvidenceChunk] = []
        sources_processed = 0

        for source in input_data.sources:
            try:
                # Read source content
                content = self._read_source_content(
                    source, input_data.raw_content_dir
                )

                if content:
                    # Split into chunks
                    chunks = self._split_into_chunks(
                        content=content,
                        source=source,
                        run_id=input_data.run_id,
                        chunk_size=input_data.chunk_size,
                        chunk_overlap=input_data.chunk_overlap,
                    )
                    all_chunks.extend(chunks)
                    sources_processed += 1

            except Exception as e:
                logger.warning(f"Error processing source {source.source_id}: {e}")

        logger.info(
            f"Created {len(all_chunks)} chunks from {sources_processed} sources"
        )

        return ChunkOutput(
            run_id=input_data.run_id,
            run_dir=input_data.run_dir,
            procedure_title=input_data.procedure_title,
            chunks=all_chunks,
            total_chunks=len(all_chunks),
            sources_processed=sources_processed,
        )

    def _read_source_content(
        self, source: SourceInfo, raw_dir: Path
    ) -> str | None:
        """Read content from a source's raw file.

        Args:
            source: Source to read
            raw_dir: Directory containing raw files

        Returns:
            Source content as string, or None if not found
        """
        source_file = raw_dir / f"{source.source_id}.json"

        if not source_file.exists():
            logger.debug(f"Source file not found: {source_file}")
            return None

        try:
            with open(source_file, encoding="utf-8") as f:
                data = json.load(f)

            # Combine available text fields
            content_parts = []

            if data.get("title"):
                content_parts.append(f"Title: {data['title']}")

            if data.get("abstract"):
                content_parts.append(data["abstract"])

            if data.get("content"):
                content_parts.append(data["content"])

            if data.get("full_text"):
                content_parts.append(data["full_text"])

            return "\n\n".join(content_parts) if content_parts else None

        except Exception as e:
            logger.warning(f"Error reading source {source.source_id}: {e}")
            return None

    def _split_into_chunks(
        self,
        content: str,
        source: SourceInfo,
        run_id: str,
        chunk_size: int,
        chunk_overlap: int,
    ) -> list[EvidenceChunk]:
        """Split content into overlapping chunks.

        Uses paragraph-based chunking when possible, falls back to
        character-based chunking for content without paragraph breaks.

        Args:
            content: Text content to chunk
            source: Source metadata
            run_id: Pipeline run ID
            chunk_size: Target chunk size in characters
            chunk_overlap: Overlap between chunks

        Returns:
            List of EvidenceChunk objects
        """
        chunks: list[EvidenceChunk] = []

        # If content is shorter than chunk size, return as single chunk
        if len(content) <= chunk_size:
            chunks.append(
                EvidenceChunk(
                    run_id=run_id,
                    source_id=source.source_id,
                    text=content.strip(),
                    chunk_index=0,
                    start_char=0,
                    end_char=len(content),
                    metadata={
                        "source_title": source.title,
                        "source_type": source.source_type,
                    },
                )
            )
            return chunks

        # Check if content has paragraph breaks
        paragraphs = content.split("\n\n")
        has_paragraphs = len(paragraphs) > 1

        if has_paragraphs:
            # Use paragraph-aware chunking
            return self._chunk_by_paragraphs(
                content, paragraphs, source, run_id, chunk_size, chunk_overlap
            )
        else:
            # Fall back to character-based chunking
            return self._chunk_by_characters(
                content, source, run_id, chunk_size, chunk_overlap
            )

    def _chunk_by_paragraphs(
        self,
        content: str,
        paragraphs: list[str],
        source: SourceInfo,
        run_id: str,
        chunk_size: int,
        chunk_overlap: int,
    ) -> list[EvidenceChunk]:
        """Chunk content using paragraph boundaries."""
        chunks: list[EvidenceChunk] = []
        current_chunk = ""
        current_start = 0
        char_pos = 0
        chunk_index = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                char_pos += 2  # Account for \n\n
                continue

            # If adding this paragraph would exceed chunk size
            if len(current_chunk) + len(para) + 2 > chunk_size:
                # Save current chunk if it has content
                if current_chunk.strip():
                    chunks.append(
                        EvidenceChunk(
                            run_id=run_id,
                            source_id=source.source_id,
                            text=current_chunk.strip(),
                            chunk_index=chunk_index,
                            start_char=current_start,
                            end_char=char_pos,
                            metadata={
                                "source_title": source.title,
                                "source_type": source.source_type,
                            },
                        )
                    )
                    chunk_index += 1

                # Start new chunk with overlap from previous
                if chunk_overlap > 0 and current_chunk:
                    overlap_text = current_chunk[-chunk_overlap:]
                    current_chunk = overlap_text + "\n\n" + para
                    current_start = max(0, char_pos - chunk_overlap)
                else:
                    current_chunk = para
                    current_start = char_pos
            else:
                # Add paragraph to current chunk
                if current_chunk:
                    current_chunk += "\n\n" + para
                else:
                    current_chunk = para

            char_pos += len(para) + 2  # +2 for \n\n

        # Don't forget the last chunk
        if current_chunk.strip():
            chunks.append(
                EvidenceChunk(
                    run_id=run_id,
                    source_id=source.source_id,
                    text=current_chunk.strip(),
                    chunk_index=chunk_index,
                    start_char=current_start,
                    end_char=len(content),
                    metadata={
                        "source_title": source.title,
                        "source_type": source.source_type,
                    },
                )
            )

        return chunks

    def _chunk_by_characters(
        self,
        content: str,
        source: SourceInfo,
        run_id: str,
        chunk_size: int,
        chunk_overlap: int,
    ) -> list[EvidenceChunk]:
        """Chunk content by character count with overlap."""
        chunks: list[EvidenceChunk] = []
        chunk_index = 0
        start = 0

        while start < len(content):
            end = min(start + chunk_size, len(content))

            # Try to break at word boundary
            if end < len(content):
                # Look for last space within chunk
                last_space = content.rfind(" ", start, end)
                if last_space > start:
                    end = last_space

            chunk_text = content[start:end].strip()

            if chunk_text:
                chunks.append(
                    EvidenceChunk(
                        run_id=run_id,
                        source_id=source.source_id,
                        text=chunk_text,
                        chunk_index=chunk_index,
                        start_char=start,
                        end_char=end,
                        metadata={
                            "source_title": source.title,
                            "source_type": source.source_type,
                        },
                    )
                )
                chunk_index += 1

            # Move start forward, accounting for overlap
            start = end - chunk_overlap if chunk_overlap > 0 else end

            # Prevent infinite loop if overlap >= chunk_size
            if start <= chunks[-1].start_char if chunks else False:
                start = end

        return chunks

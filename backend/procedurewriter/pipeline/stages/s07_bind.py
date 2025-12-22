"""Stage 07: Bind - Link claims to their supporting evidence.

The Bind stage creates traceability between claims and evidence:
1. Receives claims from Stage 06 (ClaimExtract)
2. Receives evidence chunks (from pipeline context)
3. Uses keyword matching to find links (source_ref → source_id)
4. Creates ClaimEvidenceLink objects
5. Outputs bound claims for Evals stage
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from procedurewriter.models.claims import Claim
from procedurewriter.models.evidence import (
    BindingType,
    ClaimEvidenceLink,
    EvidenceChunk,
)
from procedurewriter.pipeline.events import EventType
from procedurewriter.pipeline.stages.base import PipelineStage

if TYPE_CHECKING:
    from procedurewriter.pipeline.events import EventEmitter

logger = logging.getLogger(__name__)

# Minimum keyword overlap ratio for binding
MIN_KEYWORD_OVERLAP = 0.2


@dataclass
class BindInput:
    """Input for the Bind stage."""

    run_id: str
    run_dir: Path
    procedure_title: str
    claims: list[Claim]
    chunks: list[EvidenceChunk]
    emitter: "EventEmitter | None" = None


@dataclass
class BindOutput:
    """Output from the Bind stage."""

    run_id: str
    run_dir: Path
    procedure_title: str
    claims: list[Claim]
    links: list[ClaimEvidenceLink]
    total_links: int
    unbound_claims: list[Claim] = field(default_factory=list)


class BindStage(PipelineStage[BindInput, BindOutput]):
    """Stage 07: Bind - Link claims to their supporting evidence."""

    @property
    def name(self) -> str:
        """Return the stage name."""
        return "bind"

    def execute(self, input_data: BindInput) -> BindOutput:
        """Execute the bind stage.

        Links claims to evidence chunks using source references and keyword matching.

        Args:
            input_data: Bind input containing claims and evidence chunks

        Returns:
            Bind output with list of ClaimEvidenceLink objects
        """
        # Emit progress event if emitter provided
        if input_data.emitter is not None:
            input_data.emitter.emit(
                EventType.PROGRESS,
                {
                    "message": f"Binding claims to evidence for {input_data.procedure_title}",
                    "stage": "bind",
                },
            )

        # Handle empty inputs
        if not input_data.claims:
            logger.info("No claims to bind")
            return BindOutput(
                run_id=input_data.run_id,
                run_dir=input_data.run_dir,
                procedure_title=input_data.procedure_title,
                claims=input_data.claims,
                links=[],
                total_links=0,
                unbound_claims=[],
            )

        if not input_data.chunks:
            logger.info("No chunks available, all claims will be unbound")
            return BindOutput(
                run_id=input_data.run_id,
                run_dir=input_data.run_dir,
                procedure_title=input_data.procedure_title,
                claims=input_data.claims,
                links=[],
                total_links=0,
                unbound_claims=input_data.claims.copy(),
            )

        # Build index of chunks by source_id
        chunks_by_source = self._build_chunk_index(input_data.chunks)

        # Bind each claim
        all_links: list[ClaimEvidenceLink] = []
        unbound_claims: list[Claim] = []

        for claim in input_data.claims:
            links = self._bind_claim(claim, input_data.chunks, chunks_by_source)

            if links:
                all_links.extend(links)
            else:
                unbound_claims.append(claim)

        logger.info(
            f"Created {len(all_links)} links, {len(unbound_claims)} unbound claims"
        )

        return BindOutput(
            run_id=input_data.run_id,
            run_dir=input_data.run_dir,
            procedure_title=input_data.procedure_title,
            claims=input_data.claims,
            links=all_links,
            total_links=len(all_links),
            unbound_claims=unbound_claims,
        )

    def _build_chunk_index(
        self, chunks: list[EvidenceChunk]
    ) -> dict[str, list[EvidenceChunk]]:
        """Build an index of chunks by source_id.

        Args:
            chunks: List of evidence chunks

        Returns:
            Dictionary mapping source_id to list of chunks
        """
        index: dict[str, list[EvidenceChunk]] = {}

        for chunk in chunks:
            if chunk.source_id not in index:
                index[chunk.source_id] = []
            index[chunk.source_id].append(chunk)

        return index

    def _bind_claim(
        self,
        claim: Claim,
        all_chunks: list[EvidenceChunk],
        chunks_by_source: dict[str, list[EvidenceChunk]],
    ) -> list[ClaimEvidenceLink]:
        """Bind a single claim to relevant evidence chunks.

        Uses two strategies:
        1. Source reference matching: claim.source_refs → chunk.source_id
        2. Keyword overlap: find chunks with significant text overlap

        Args:
            claim: Claim to bind
            all_chunks: All available chunks
            chunks_by_source: Index of chunks by source_id

        Returns:
            List of ClaimEvidenceLink objects for this claim
        """
        links: list[ClaimEvidenceLink] = []
        linked_chunk_ids: set = set()

        # Strategy 1: Match by source reference
        for source_ref in claim.source_refs:
            if source_ref in chunks_by_source:
                for chunk in chunks_by_source[source_ref]:
                    if chunk.id not in linked_chunk_ids:
                        score = self._calculate_keyword_score(claim.text, chunk.text)
                        links.append(
                            ClaimEvidenceLink(
                                claim_id=claim.id,
                                evidence_chunk_id=chunk.id,
                                binding_type=BindingType.KEYWORD,
                                binding_score=max(0.5, score),  # Minimum 0.5 for source match
                            )
                        )
                        linked_chunk_ids.add(chunk.id)

        # Strategy 2: Keyword matching for chunks not already linked
        if not links:  # Only if no source refs matched
            claim_keywords = self._extract_keywords(claim.text)

            for chunk in all_chunks:
                if chunk.id in linked_chunk_ids:
                    continue

                chunk_keywords = self._extract_keywords(chunk.text)
                overlap = self._calculate_overlap(claim_keywords, chunk_keywords)

                if overlap >= MIN_KEYWORD_OVERLAP:
                    score = self._calculate_keyword_score(claim.text, chunk.text)
                    links.append(
                        ClaimEvidenceLink(
                            claim_id=claim.id,
                            evidence_chunk_id=chunk.id,
                            binding_type=BindingType.KEYWORD,
                            binding_score=score,
                        )
                    )
                    linked_chunk_ids.add(chunk.id)

        return links

    def _extract_keywords(self, text: str) -> set[str]:
        """Extract significant keywords from text.

        Filters out common stopwords and short words.

        Args:
            text: Text to extract keywords from

        Returns:
            Set of lowercase keywords
        """
        # Simple word extraction (alphanumeric)
        words = re.findall(r"\b[a-zA-Z0-9æøåÆØÅ]+\b", text.lower())

        # Filter out short words and common stopwords
        stopwords = {
            "a", "an", "the", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "must", "shall",
            "can", "to", "of", "in", "for", "on", "with", "at", "by",
            "from", "as", "or", "and", "but", "if", "not", "no", "so",
            "than", "too", "very", "just", "about", "into", "through",
            "during", "before", "after", "above", "below", "between",
            "under", "again", "further", "then", "once", "here", "there",
            "when", "where", "why", "how", "all", "each", "few", "more",
            "most", "other", "some", "such", "only", "own", "same",
            "this", "that", "these", "those", "it", "its",
            # Danish stopwords
            "og", "i", "at", "er", "en", "af", "til", "på", "med", "som",
            "det", "de", "den", "for", "ikke", "der", "var", "har", "kan",
            "fra", "eller", "et", "om", "skal", "ved", "sig", "vil", "være",
            "efter", "også", "nu", "når", "hans", "hans", "selv", "hen",
        }

        keywords = {
            word for word in words
            if len(word) >= 3 and word not in stopwords
        }

        return keywords

    def _calculate_overlap(
        self, keywords1: set[str], keywords2: set[str]
    ) -> float:
        """Calculate Jaccard similarity between two keyword sets.

        Args:
            keywords1: First set of keywords
            keywords2: Second set of keywords

        Returns:
            Overlap ratio (0.0 to 1.0)
        """
        if not keywords1 or not keywords2:
            return 0.0

        intersection = keywords1 & keywords2
        union = keywords1 | keywords2

        return len(intersection) / len(union) if union else 0.0

    def _calculate_keyword_score(self, claim_text: str, chunk_text: str) -> float:
        """Calculate binding score based on keyword overlap.

        Args:
            claim_text: Claim text
            chunk_text: Evidence chunk text

        Returns:
            Score between 0.0 and 1.0
        """
        claim_keywords = self._extract_keywords(claim_text)
        chunk_keywords = self._extract_keywords(chunk_text)

        if not claim_keywords:
            return 0.3  # Low default score for empty claims

        # What fraction of claim keywords are in the chunk?
        matches = claim_keywords & chunk_keywords
        coverage = len(matches) / len(claim_keywords)

        # Boost score if chunk contains the claim keywords
        return min(1.0, coverage * 1.2)  # Scale up slightly, cap at 1.0

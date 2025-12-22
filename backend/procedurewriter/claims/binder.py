"""EvidenceBinder - Link claims to evidence chunks.

This module provides the EvidenceBinder class that matches extracted claims
to evidence chunks using keyword overlap scoring. Semantic (embedding-based)
binding will be added in a future task.

The binder:
1. Takes claims and evidence chunks as input
2. Scores each claim-chunk pair based on keyword overlap
3. Creates ClaimEvidenceLink objects for matches above threshold
4. Tracks unbound claims for review
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from procedurewriter.models.claims import Claim
from procedurewriter.models.evidence import (
    BindingType,
    ClaimEvidenceLink,
    EvidenceChunk,
)

if TYPE_CHECKING:
    pass


# Stop words to ignore in keyword matching (Danish and English)
STOP_WORDS: set[str] = {
    # Danish
    "og", "i", "at", "er", "en", "et", "den", "det", "de", "på", "til",
    "med", "som", "for", "af", "fra", "om", "ved", "eller", "kan", "skal",
    "bør", "har", "ikke", "være", "vil", "blev", "bliver", "var", "være",
    # English
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "must", "and", "or", "but", "if", "then",
    "of", "to", "in", "for", "on", "with", "at", "by", "from", "as",
}

# Minimum word length to consider as keyword
MIN_WORD_LENGTH = 2


@dataclass
class BindingResult:
    """Result of binding claims to evidence chunks.

    Attributes:
        links: List of ClaimEvidenceLink objects for successful bindings.
        unbound_claims: Claims that could not be bound to any evidence.
        binding_stats: Statistics about the binding process.
    """

    links: list[ClaimEvidenceLink] = field(default_factory=list)
    unbound_claims: list[Claim] = field(default_factory=list)
    binding_stats: dict[str, int] = field(default_factory=dict)


class EvidenceBinder:
    """Binds claims to evidence chunks using keyword overlap.

    The binder scores each claim-chunk pair based on the overlap of
    significant keywords. Claims with source references get boosted
    scores when matching chunks from those sources.

    Attributes:
        min_score: Minimum score threshold for creating a link (0-1).
        max_links_per_claim: Maximum number of links per claim.
    """

    def __init__(
        self,
        min_score: float = 0.1,
        max_links_per_claim: int = 3,
    ) -> None:
        """Initialize the evidence binder.

        Args:
            min_score: Minimum score threshold for creating links (0-1).
            max_links_per_claim: Maximum evidence links per claim.
        """
        self.min_score = min_score
        self.max_links_per_claim = max_links_per_claim

    def bind(
        self,
        claims: list[Claim],
        chunks: list[EvidenceChunk],
    ) -> BindingResult:
        """Bind claims to evidence chunks.

        For each claim, finds the best matching evidence chunks based on
        keyword overlap. Creates ClaimEvidenceLink objects for matches
        above the minimum score threshold.

        Args:
            claims: List of claims to bind.
            chunks: List of evidence chunks to match against.

        Returns:
            BindingResult with links, unbound claims, and statistics.
        """
        links: list[ClaimEvidenceLink] = []
        unbound_claims: list[Claim] = []

        for claim in claims:
            claim_links = self._bind_claim(claim, chunks)
            if claim_links:
                links.extend(claim_links)
            else:
                unbound_claims.append(claim)

        # Calculate statistics
        stats = {
            "total_claims": len(claims),
            "bound_claims": len(claims) - len(unbound_claims),
            "unbound_claims": len(unbound_claims),
            "total_links": len(links),
        }

        return BindingResult(
            links=links,
            unbound_claims=unbound_claims,
            binding_stats=stats,
        )

    def _bind_claim(
        self,
        claim: Claim,
        chunks: list[EvidenceChunk],
    ) -> list[ClaimEvidenceLink]:
        """Bind a single claim to evidence chunks.

        Args:
            claim: Claim to bind.
            chunks: Available evidence chunks.

        Returns:
            List of ClaimEvidenceLink objects for this claim.
        """
        if not chunks:
            return []

        # Score each chunk
        scored_chunks: list[tuple[EvidenceChunk, float]] = []
        claim_keywords = self._extract_keywords(claim.text)

        for chunk in chunks:
            score = self._calculate_score(claim, chunk, claim_keywords)
            if score >= self.min_score:
                scored_chunks.append((chunk, score))

        # Sort by score descending and take top N
        scored_chunks.sort(key=lambda x: x[1], reverse=True)
        top_chunks = scored_chunks[: self.max_links_per_claim]

        # Create links
        links = []
        for chunk, score in top_chunks:
            link = ClaimEvidenceLink(
                claim_id=claim.id,
                evidence_chunk_id=chunk.id,
                binding_type=BindingType.KEYWORD,
                binding_score=score,
            )
            links.append(link)

        return links

    def _calculate_score(
        self,
        claim: Claim,
        chunk: EvidenceChunk,
        claim_keywords: set[str],
    ) -> float:
        """Calculate binding score between claim and chunk.

        Score is based on:
        1. Keyword overlap (Jaccard-like similarity)
        2. Source reference match bonus
        3. Exact phrase match bonus

        Args:
            claim: The claim being bound.
            chunk: The evidence chunk to score.
            claim_keywords: Pre-extracted claim keywords.

        Returns:
            Binding score between 0.0 and 1.0.
        """
        if not claim_keywords:
            return 0.0

        chunk_keywords = self._extract_keywords(chunk.text)
        if not chunk_keywords:
            return 0.0

        # Calculate keyword overlap (modified Jaccard)
        overlap = claim_keywords & chunk_keywords
        if not overlap:
            return 0.0

        # Score based on how much of the claim is covered
        claim_coverage = len(overlap) / len(claim_keywords)

        # Base score from coverage
        score = claim_coverage * 0.7  # Max 0.7 from keyword overlap

        # Bonus for source reference match
        if claim.source_refs:
            if chunk.source_id in claim.source_refs:
                score += 0.2  # Significant bonus for source match

        # Bonus for exact phrase match (substring)
        claim_lower = claim.text.lower()
        chunk_lower = chunk.text.lower()
        if claim_lower in chunk_lower:
            score += 0.1  # Bonus for exact match

        # Cap at 1.0
        return min(score, 1.0)

    def _extract_keywords(self, text: str) -> set[str]:
        """Extract significant keywords from text.

        Removes stop words, short words, and normalizes to lowercase.
        Also extracts numbers and medical units as keywords.

        Args:
            text: Text to extract keywords from.

        Returns:
            Set of keyword strings.
        """
        if not text:
            return set()

        # Normalize text
        text_lower = text.lower()

        # Extract words (including numbers and units)
        # Matches: words, numbers, and common medical patterns like "500mg"
        word_pattern = re.compile(r"[a-zA-ZæøåÆØÅμ]+|\d+(?:[.,]\d+)?")
        words = word_pattern.findall(text_lower)

        # Filter out stop words and short words
        keywords = {
            word
            for word in words
            if word not in STOP_WORDS and len(word) >= MIN_WORD_LENGTH
        }

        return keywords

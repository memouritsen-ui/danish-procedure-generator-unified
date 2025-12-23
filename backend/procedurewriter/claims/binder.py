"""EvidenceBinder - Link claims to evidence chunks.

This module provides the EvidenceBinder class that matches extracted claims
to evidence chunks using keyword overlap scoring and semantic (embedding-based)
similarity.

The binder:
1. Takes claims and evidence chunks as input
2. Scores each claim-chunk pair based on keyword overlap and/or embeddings
3. Creates ClaimEvidenceLink objects for matches above threshold
4. Tracks unbound claims for review
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, runtime_checkable

logger = logging.getLogger(__name__)

from procedurewriter.models.claims import Claim
from procedurewriter.models.evidence import (
    BindingType,
    ClaimEvidenceLink,
    EvidenceChunk,
)

if TYPE_CHECKING:
    pass


class EmbeddingError(Exception):
    """Raised when embedding generation fails."""

    pass


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Protocol for embedding providers."""

    def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Get embeddings for a list of texts.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors (list of floats).
        """
        ...


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


def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Calculate cosine similarity between two vectors.

    Args:
        vec_a: First vector.
        vec_b: Second vector.

    Returns:
        Cosine similarity between 0 and 1.
    """
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0

    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot_product / (norm_a * norm_b)


class EvidenceBinder:
    """Binds claims to evidence chunks using keyword overlap and semantic similarity.

    The binder scores each claim-chunk pair based on:
    1. Keyword overlap (always used)
    2. Semantic similarity via embeddings (when provider is available)

    Claims with source references get boosted scores when matching chunks
    from those sources.

    Attributes:
        min_score: Minimum score threshold for creating a link (0-1).
        max_links_per_claim: Maximum number of links per claim.
        embedding_provider: Optional provider for generating embeddings.
    """

    def __init__(
        self,
        min_score: float = 0.1,
        max_links_per_claim: int = 3,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        """Initialize the evidence binder.

        Args:
            min_score: Minimum score threshold for creating links (0-1).
            max_links_per_claim: Maximum evidence links per claim.
            embedding_provider: Optional embedding provider for semantic binding.
        """
        self.min_score = min_score
        self.max_links_per_claim = max_links_per_claim
        self.embedding_provider = embedding_provider

    def bind(
        self,
        claims: list[Claim],
        chunks: list[EvidenceChunk],
    ) -> BindingResult:
        """Bind claims to evidence chunks.

        For each claim, finds the best matching evidence chunks based on
        keyword overlap and/or semantic similarity. Creates ClaimEvidenceLink
        objects for matches above the minimum score threshold.

        Args:
            claims: List of claims to bind.
            chunks: List of evidence chunks to match against.

        Returns:
            BindingResult with links, unbound claims, and statistics.
        """
        links: list[ClaimEvidenceLink] = []
        unbound_claims: list[Claim] = []
        semantic_bindings = 0
        keyword_bindings = 0

        # Get embeddings if provider is available
        embeddings: dict[str, list[float]] = {}
        if self.embedding_provider and claims and chunks:
            try:
                embeddings = self._get_embeddings(claims, chunks)
            except EmbeddingError as e:
                logger.warning(
                    f"Embedding failed, falling back to keyword binding: {e}"
                )
                # Continue with empty embeddings - keyword binding will be used

        for claim in claims:
            claim_embedding = embeddings.get(f"claim_{claim.id}")
            chunk_embeddings = {
                chunk.id: embeddings.get(f"chunk_{chunk.id}")
                for chunk in chunks
            }
            claim_links = self._bind_claim(
                claim, chunks, claim_embedding, chunk_embeddings
            )
            if claim_links:
                links.extend(claim_links)
                # Count binding types
                for link in claim_links:
                    if link.binding_type == BindingType.SEMANTIC:
                        semantic_bindings += 1
                    else:
                        keyword_bindings += 1
            else:
                unbound_claims.append(claim)

        # Calculate statistics
        stats = {
            "total_claims": len(claims),
            "bound_claims": len(claims) - len(unbound_claims),
            "unbound_claims": len(unbound_claims),
            "total_links": len(links),
            "semantic_bindings": semantic_bindings,
            "keyword_bindings": keyword_bindings,
        }

        return BindingResult(
            links=links,
            unbound_claims=unbound_claims,
            binding_stats=stats,
        )

    def _get_embeddings(
        self,
        claims: list[Claim],
        chunks: list[EvidenceChunk],
    ) -> dict[str, list[float]]:
        """Get embeddings for all claims and chunks.

        Args:
            claims: List of claims.
            chunks: List of evidence chunks.

        Returns:
            Dictionary mapping text IDs to embeddings.
        """
        if not self.embedding_provider:
            return {}

        # Collect all texts with their IDs
        texts: list[str] = []
        text_ids: list[str] = []

        for claim in claims:
            texts.append(claim.text)
            text_ids.append(f"claim_{claim.id}")

        for chunk in chunks:
            texts.append(chunk.text)
            text_ids.append(f"chunk_{chunk.id}")

        if not texts:
            return {}

        # Get embeddings from provider
        try:
            embedding_vectors = self.embedding_provider.get_embeddings(texts)
            return dict(zip(text_ids, embedding_vectors))
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}", exc_info=True)
            raise EmbeddingError(
                f"Failed to generate embeddings for {len(texts)} texts: {e}"
            ) from e

    def _bind_claim(
        self,
        claim: Claim,
        chunks: list[EvidenceChunk],
        claim_embedding: list[float] | None = None,
        chunk_embeddings: dict | None = None,
    ) -> list[ClaimEvidenceLink]:
        """Bind a single claim to evidence chunks.

        Uses semantic similarity (embeddings) when available, otherwise
        falls back to keyword-based scoring.

        Args:
            claim: Claim to bind.
            chunks: Available evidence chunks.
            claim_embedding: Embedding for the claim (optional).
            chunk_embeddings: Dict mapping chunk IDs to embeddings (optional).

        Returns:
            List of ClaimEvidenceLink objects for this claim.
        """
        if not chunks:
            return []

        chunk_embeddings = chunk_embeddings or {}
        use_semantic = claim_embedding is not None and any(chunk_embeddings.values())

        # Score each chunk
        scored_chunks: list[tuple[EvidenceChunk, float, BindingType]] = []
        claim_keywords = self._extract_keywords(claim.text)

        for chunk in chunks:
            if use_semantic:
                # Use semantic similarity as primary score
                chunk_emb = chunk_embeddings.get(chunk.id)
                if chunk_emb:
                    semantic_score = _cosine_similarity(claim_embedding, chunk_emb)
                    # Normalize to binding score range
                    score = max(0.0, min(1.0, semantic_score))
                    if score >= self.min_score:
                        scored_chunks.append((chunk, score, BindingType.SEMANTIC))
            else:
                # Use keyword-based scoring
                score = self._calculate_score(claim, chunk, claim_keywords)
                if score >= self.min_score:
                    scored_chunks.append((chunk, score, BindingType.KEYWORD))

        # Sort by score descending and take top N
        scored_chunks.sort(key=lambda x: x[1], reverse=True)
        top_chunks = scored_chunks[: self.max_links_per_claim]

        # Create links
        links = []
        for chunk, score, binding_type in top_chunks:
            link = ClaimEvidenceLink(
                claim_id=claim.id,
                evidence_chunk_id=chunk.id,
                binding_type=binding_type,
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

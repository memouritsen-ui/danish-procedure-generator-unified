"""Semantic deduplication for medical procedure content.

Phase 2: Repetition Elimination
Detects and removes semantically similar content across sections.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class DuplicateGroup:
    """A group of semantically similar items."""

    items: list[str]
    canonical: str  # The "best" version to keep
    similarity: float  # Average similarity within group


@dataclass
class DeduplicationStats:
    """Statistics from deduplication operation."""

    items_removed: int = 0
    duplicate_groups: int = 0
    original_count: int = 0
    final_count: int = 0


class RepetitionDetector:
    """Detects and removes repeated/similar content in medical procedures.

    Uses token-based similarity for semantic matching without requiring
    external embedding models.
    """

    def __init__(self) -> None:
        self._last_stats: DeduplicationStats | None = None
        # Stop words for Danish medical text
        self._stopwords = {
            "og", "i", "på", "til", "ved", "af", "for", "med", "den", "det",
            "en", "et", "er", "som", "kan", "skal", "vil", "har", "være",
            "eller", "hvis", "når", "da", "så", "også", "men", "fra",
        }
        # High-value keywords that indicate semantic similarity (stemmed forms)
        self._semantic_keywords = {
            "bagvagt", "forvagt", "anæstesi", "anaestesi",
            "ring", "kontakt", "tilkald",
            "lokal", "retningslinje", "instruks", "protokol",
            "komplikation",  # Stemmed from komplikationer
            "dosering", "dosis",
            "problem",  # Stemmed from problemer
        }

    def detect_duplicates(
        self, texts: list[str], threshold: float = 0.8
    ) -> list[DuplicateGroup]:
        """Detect duplicate or similar items in a list of texts.

        Args:
            texts: List of text strings to check for duplicates
            threshold: Similarity threshold (0.0-1.0) for grouping

        Returns:
            List of DuplicateGroup objects, one per group of similar items
        """
        if not texts:
            return []

        # Normalize texts for comparison
        normalized = [self._normalize(t) for t in texts]

        # Track which items have been grouped
        grouped: set[int] = set()
        groups: list[DuplicateGroup] = []

        for i, norm_i in enumerate(normalized):
            if i in grouped:
                continue

            # Find all items similar to this one
            similar_indices = [i]
            similar_texts = [texts[i]]

            for j, norm_j in enumerate(normalized):
                if j <= i or j in grouped:
                    continue

                similarity = self._calculate_similarity(norm_i, norm_j)
                if similarity >= threshold:
                    similar_indices.append(j)
                    similar_texts.append(texts[j])

            # Mark all as grouped
            grouped.update(similar_indices)

            # Select canonical version (prefer longer, more specific)
            canonical = self._select_canonical(similar_texts)

            # Calculate average similarity within group
            if len(similar_texts) > 1:
                avg_sim = self._calculate_group_similarity(
                    [normalized[idx] for idx in similar_indices]
                )
            else:
                avg_sim = 1.0

            groups.append(
                DuplicateGroup(
                    items=similar_texts,
                    canonical=canonical,
                    similarity=avg_sim,
                )
            )

        return groups

    def deduplicate(
        self, texts: list[str], threshold: float = 0.8
    ) -> list[str]:
        """Remove duplicate/similar items, keeping first/best occurrence.

        Args:
            texts: List of text strings
            threshold: Similarity threshold for considering items as duplicates

        Returns:
            Deduplicated list preserving order of first occurrences
        """
        if not texts:
            self._last_stats = DeduplicationStats()
            return []

        groups = self.detect_duplicates(texts, threshold)

        # Build set of items to keep (canonical from each group)
        keep_canonical = {g.canonical for g in groups}

        # For each group, we keep only the canonical version
        # But we want to maintain original order
        result: list[str] = []
        seen_canonical: set[str] = set()

        # Map each text to its canonical form
        text_to_canonical: dict[str, str] = {}
        for group in groups:
            for item in group.items:
                text_to_canonical[item] = group.canonical

        for text in texts:
            canonical = text_to_canonical.get(text, text)
            if canonical not in seen_canonical:
                result.append(canonical)
                seen_canonical.add(canonical)

        # Calculate stats
        items_removed = len(texts) - len(result)
        duplicate_groups = sum(1 for g in groups if len(g.items) > 1)

        self._last_stats = DeduplicationStats(
            items_removed=items_removed,
            duplicate_groups=duplicate_groups,
            original_count=len(texts),
            final_count=len(result),
        )

        return result

    def deduplicate_sections(
        self, sections: dict[str, list[str]], threshold: float = 0.8
    ) -> dict[str, list[str]]:
        """Deduplicate content across document sections.

        Args:
            sections: Dict mapping section names to lists of text items
            threshold: Similarity threshold

        Returns:
            Dict with same structure but deduplicated content
        """
        # Flatten all texts with section tracking
        all_texts: list[tuple[str, str, int]] = []  # (section, text, index)
        for section_name, texts in sections.items():
            for idx, text in enumerate(texts):
                all_texts.append((section_name, text, idx))

        # Get all unique texts across all sections
        unique_texts = list({t[1] for t in all_texts})
        groups = self.detect_duplicates(unique_texts, threshold)

        # Build mapping from any variant to canonical
        text_to_canonical: dict[str, str] = {}
        for group in groups:
            for item in group.items:
                text_to_canonical[item] = group.canonical

        # Track which canonicals we've seen globally
        seen_canonical: set[str] = set()
        result: dict[str, list[str]] = {name: [] for name in sections}

        # Process in original order, keeping first occurrence
        for section_name, text, _ in all_texts:
            canonical = text_to_canonical.get(text, text)
            if canonical not in seen_canonical:
                result[section_name].append(canonical)
                seen_canonical.add(canonical)

        return result

    def get_stats(self) -> dict:
        """Get statistics from the last deduplication operation.

        Returns:
            Dict with items_removed, duplicate_groups, etc.
        """
        if self._last_stats is None:
            return {
                "items_removed": 0,
                "duplicate_groups": 0,
                "original_count": 0,
                "final_count": 0,
            }

        return {
            "items_removed": self._last_stats.items_removed,
            "duplicate_groups": self._last_stats.duplicate_groups,
            "original_count": self._last_stats.original_count,
            "final_count": self._last_stats.final_count,
        }

    def _normalize(self, text: str) -> str:
        """Normalize text for comparison.

        - Lowercase
        - Remove punctuation
        - Collapse whitespace
        """
        text = text.lower()
        text = re.sub(r"[^\w\sæøåÆØÅ]", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _tokenize(self, text: str) -> set[str]:
        """Tokenize normalized text into word set with basic stemming."""
        words = text.split()
        # Remove stopwords and apply basic stemming
        stemmed = set()
        for w in words:
            if w in self._stopwords or len(w) <= 1:
                continue
            # Basic Danish stemming - remove common suffixes
            stem = self._simple_stem(w)
            stemmed.add(stem)
        return stemmed

    def _simple_stem(self, word: str) -> str:
        """Simple Danish word stemming.

        Removes common inflectional suffixes to normalize word forms.
        """
        # Common Danish suffixes (order matters - longest first)
        suffixes = [
            "erne", "ene", "en", "et", "er",  # Definite/plural forms
            "ede", "te", "es", "s",  # Past tense, genitive
        ]
        for suffix in suffixes:
            if word.endswith(suffix) and len(word) - len(suffix) >= 3:
                return word[:-len(suffix)]
        return word

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two normalized texts.

        Uses Jaccard similarity on token sets, with boosting for semantic keywords.
        """
        # Exact match
        if text1 == text2:
            return 1.0

        tokens1 = self._tokenize(text1)
        tokens2 = self._tokenize(text2)

        if not tokens1 or not tokens2:
            return 0.0

        intersection = tokens1 & tokens2
        union = tokens1 | tokens2

        # Base Jaccard similarity
        jaccard = len(intersection) / len(union)

        # Boost similarity if both texts contain the same semantic keywords
        keywords1 = tokens1 & self._semantic_keywords
        keywords2 = tokens2 & self._semantic_keywords
        shared_keywords = keywords1 & keywords2

        # Category-based boost (e.g., both about contacting, both about problems)
        contact_keywords = {"ring", "kontakt", "tilkald"}
        problem_keywords = {"komplikation", "problem"}
        target_keywords = {"bagvagt", "forvagt", "anæstesi"}

        has_contact1 = bool(keywords1 & contact_keywords)
        has_contact2 = bool(keywords2 & contact_keywords)
        has_problem1 = bool(keywords1 & problem_keywords)
        has_problem2 = bool(keywords2 & problem_keywords)
        has_target1 = bool(keywords1 & target_keywords)
        has_target2 = bool(keywords2 & target_keywords)

        # Calculate total boost
        boost = 0.0

        # Boost for shared semantic keywords
        if shared_keywords:
            boost += min(0.3, len(shared_keywords) * 0.15)

        # Boost if both are contact-related
        if has_contact1 and has_contact2:
            boost += 0.15

        # Boost if both discuss problems/complications
        if has_problem1 and has_problem2:
            boost += 0.15

        # Boost if both have the same target (bagvagt, anæstesi, etc.)
        if has_target1 and has_target2:
            boost += 0.15

        return min(1.0, jaccard + boost)

    def _calculate_group_similarity(self, normalized_texts: list[str]) -> float:
        """Calculate average pairwise similarity within a group."""
        if len(normalized_texts) <= 1:
            return 1.0

        similarities = []
        for i, t1 in enumerate(normalized_texts):
            for t2 in normalized_texts[i + 1:]:
                similarities.append(self._calculate_similarity(t1, t2))

        return sum(similarities) / len(similarities) if similarities else 1.0

    def _select_canonical(self, texts: list[str]) -> str:
        """Select the best/canonical version from a group of similar texts.

        Prefers:
        1. Longer text (more complete)
        2. More specific content (has more unique words)
        """
        if not texts:
            return ""

        if len(texts) == 1:
            return texts[0]

        # Score each text
        scored = []
        for text in texts:
            # Length score (normalized)
            length_score = len(text)

            # Specificity score (unique meaningful words)
            normalized = self._normalize(text)
            tokens = self._tokenize(normalized)
            specificity_score = len(tokens)

            # Combined score
            total_score = length_score + specificity_score * 10
            scored.append((total_score, text))

        # Return highest scoring
        scored.sort(reverse=True, key=lambda x: x[0])
        return scored[0][1]

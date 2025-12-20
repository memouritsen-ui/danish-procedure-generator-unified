"""
LLM-based evidence verification system.

Verifies that citations in generated procedures actually support the claims made.
Uses Claude Haiku for cost-effective verification of each citation.

NO MOCKS - All verification uses real LLM calls.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from anthropic import AsyncAnthropic

logger = logging.getLogger(__name__)

# Support levels for evidence verification
SupportLevel = Literal[
    "fully_supported",
    "partially_supported",
    "not_supported",
    "contradicted",
    "unverified",
]


@dataclass
class EvidenceVerification:
    """Result of verifying a single citation."""

    claim_text: str
    source_id: str
    support_level: SupportLevel
    confidence: int  # 0-100
    explanation: str  # LLM explanation in Danish
    source_excerpt: str  # Relevant excerpt from source
    line_number: int | None = None


@dataclass
class VerificationSummary:
    """Summary of all evidence verifications for a document."""

    total_citations: int
    fully_supported: int
    partially_supported: int
    not_supported: int
    contradicted: int
    unverified: int
    overall_score: int  # 0-100
    verifications: list[EvidenceVerification]


# LLM prompt for evidence verification
_VERIFICATION_PROMPT = """Du er en medicinsk faktachecker. Vurder om kilden understøtter påstanden.

PÅSTAND (fra genereret procedure):
{claim_text}

KILDE (citeret dokument, uddrag):
{source_excerpt}

Vurder forholdet mellem påstand og kilde:

1. FULLY_SUPPORTED - Kilden understøtter direkte og specifikt påstanden
2. PARTIALLY_SUPPORTED - Kilden understøtter dele af påstanden, men ikke alt
3. NOT_SUPPORTED - Kilden nævner ikke det påstanden handler om
4. CONTRADICTED - Kilden modsiger påstanden

Returner KUN valid JSON (ingen markdown, ingen forklaring udenfor JSON):
{{
  "support_level": "fully_supported|partially_supported|not_supported|contradicted",
  "confidence": <heltal 0-100, hvor sikker du er på din vurdering>,
  "explanation": "<1-2 sætninger på dansk der forklarer din vurdering>",
  "relevant_quote": "<kort citat fra kilden der er relevant for påstanden, eller tom streng hvis ingen>"
}}

VIGTIGT:
- Vær præcis - kun "fully_supported" hvis kilden direkte bekræfter påstanden
- "partially_supported" hvis kilden understøtter noget men mangler detaljer
- "not_supported" hvis kilden ikke adresserer påstanden (selv hvis den ikke modsiger)
- "contradicted" KUN hvis kilden eksplicit modsiger påstanden"""


def _fix_unescaped_quotes_in_json(json_str: str) -> str:
    """
    Fix unescaped quotes inside JSON string values.

    LLMs sometimes return JSON like:
    {"explanation": "The source mentions "some term" which..."}

    This function attempts to escape such internal quotes.
    """
    # Strategy: Find string values and escape internal quotes
    result = []
    i = 0
    in_string = False
    string_start = -1

    while i < len(json_str):
        char = json_str[i]

        if char == '\\' and i + 1 < len(json_str):
            # Skip escaped character
            result.append(char)
            result.append(json_str[i + 1])
            i += 2
            continue

        if char == '"':
            if not in_string:
                # Starting a string
                in_string = True
                string_start = i
                result.append(char)
            else:
                # Check if this is the end of the string
                # Look ahead for : , } or end of content
                rest = json_str[i + 1:].lstrip()
                if rest and rest[0] in ':,}]':
                    # This is likely the end of the string
                    in_string = False
                    result.append(char)
                elif not rest:
                    # End of text
                    in_string = False
                    result.append(char)
                else:
                    # This is an internal quote - escape it
                    result.append('\\"')
                    i += 1
                    continue
        else:
            result.append(char)

        i += 1

    return ''.join(result)


def _extract_json_from_response(response_text: str) -> dict[str, Any] | None:
    """Extract JSON from LLM response, handling various formats."""
    text = response_text.strip()

    # Try parsing as pure JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Extract from markdown code block
    code_block_pattern = r"```(?:json)?\s*\n?(.*?)\n?```"
    matches = re.findall(code_block_pattern, text, re.DOTALL)
    for match in matches:
        try:
            return json.loads(match.strip())
        except json.JSONDecodeError:
            continue

    # Find JSON object boundaries
    first_brace = text.find("{")
    last_brace = text.rfind("}")

    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        json_str = text[first_brace:last_brace + 1]

        # Try parsing as-is
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass

        # Try fixing unescaped quotes
        try:
            fixed = _fix_unescaped_quotes_in_json(json_str)
            return json.loads(fixed)
        except json.JSONDecodeError:
            pass

        # Fallback: regex extraction for known fields
        try:
            support_match = re.search(r'"support_level"\s*:\s*"([^"]+)"', json_str)
            confidence_match = re.search(r'"confidence"\s*:\s*(\d+)', json_str)

            if support_match:
                # Extract explanation more carefully - find the value after "explanation":
                expl_start = json_str.find('"explanation"')
                if expl_start != -1:
                    colon_pos = json_str.find(':', expl_start)
                    if colon_pos != -1:
                        # Find the opening quote
                        quote_start = json_str.find('"', colon_pos)
                        if quote_start != -1:
                            # Find closing - look for ", or "}
                            rest = json_str[quote_start + 1:]
                            # Find the next field or end
                            end_patterns = ['",', '"}', '"\n}']
                            end_pos = len(rest)
                            for pattern in end_patterns:
                                pos = rest.find(pattern)
                                if pos != -1 and pos < end_pos:
                                    end_pos = pos
                            explanation = rest[:end_pos]
                        else:
                            explanation = ""
                    else:
                        explanation = ""
                else:
                    explanation = ""

                return {
                    "support_level": support_match.group(1),
                    "confidence": int(confidence_match.group(1)) if confidence_match else 50,
                    "explanation": explanation,
                    "relevant_quote": "",
                }
        except Exception:
            pass

    logger.warning("Failed to extract JSON from verification response: %s", text[:200])
    return None


def _extract_source_excerpt(source_content: str, claim_text: str, max_chars: int = 2000) -> str:
    """
    Extract relevant excerpt from source content based on claim keywords.

    Uses keyword matching to find the most relevant section of the source.
    """
    if not source_content:
        return ""

    # Extract significant words from claim (excluding common words)
    stop_words = {
        "og", "i", "på", "til", "med", "af", "for", "ved", "en", "et", "den", "det",
        "er", "som", "kan", "skal", "bør", "må", "vil", "har", "være", "blive",
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    }
    claim_words = set(claim_text.lower().split()) - stop_words
    claim_words = {w for w in claim_words if len(w) > 2}

    if not claim_words:
        # Fallback: return beginning of source
        return source_content[:max_chars]

    # Find paragraph with most keyword matches
    paragraphs = source_content.split("\n\n")
    best_para = ""
    best_score = 0

    for para in paragraphs:
        if len(para.strip()) < 50:
            continue
        para_lower = para.lower()
        score = sum(1 for w in claim_words if w in para_lower)
        if score > best_score:
            best_score = score
            best_para = para

    if best_para:
        # Include some context around best paragraph
        idx = source_content.find(best_para)
        start = max(0, idx - 200)
        end = min(len(source_content), idx + len(best_para) + 200)
        excerpt = source_content[start:end]
        if start > 0:
            excerpt = "..." + excerpt
        if end < len(source_content):
            excerpt = excerpt + "..."
        return excerpt[:max_chars]

    return source_content[:max_chars]


def _calculate_haiku_cost(input_tokens: int, output_tokens: int) -> float:
    """Calculate cost for Claude Haiku API call."""
    # Haiku pricing: $0.25/MTok input, $1.25/MTok output
    input_cost = (input_tokens / 1_000_000) * 0.25
    output_cost = (output_tokens / 1_000_000) * 1.25
    return input_cost + output_cost


async def verify_citation(
    claim_text: str,
    source_content: str,
    source_id: str,
    anthropic_client: AsyncAnthropic,
    *,
    line_number: int | None = None,
) -> tuple[EvidenceVerification, float]:
    """
    Use LLM to verify if a source supports a claim.

    Args:
        claim_text: The claim/sentence from the procedure
        source_content: Full content of the cited source
        source_id: ID of the source (e.g., "SRC0001")
        anthropic_client: Anthropic API client
        line_number: Optional line number of the claim

    Returns:
        Tuple of (EvidenceVerification, cost_usd)
    """
    # Extract relevant excerpt from source
    source_excerpt = _extract_source_excerpt(source_content, claim_text)

    if not source_excerpt:
        return EvidenceVerification(
            claim_text=claim_text,
            source_id=source_id,
            support_level="unverified",
            confidence=0,
            explanation="Kunne ikke læse kildeindhold",
            source_excerpt="",
            line_number=line_number,
        ), 0.0

    prompt = _VERIFICATION_PROMPT.format(
        claim_text=claim_text,
        source_excerpt=source_excerpt,
    )

    try:
        response = await anthropic_client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )

        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        cost = _calculate_haiku_cost(input_tokens, output_tokens)

        response_text = response.content[0].text.strip()
        result = _extract_json_from_response(response_text)

        if result is None:
            logger.error("Failed to parse verification response for %s: %s", source_id, response_text[:200])
            return EvidenceVerification(
                claim_text=claim_text,
                source_id=source_id,
                support_level="unverified",
                confidence=0,
                explanation="Kunne ikke parse LLM-svar",
                source_excerpt=source_excerpt[:500],
                line_number=line_number,
            ), cost

        support_level = result.get("support_level", "unverified")
        if support_level not in ("fully_supported", "partially_supported", "not_supported", "contradicted"):
            support_level = "unverified"

        return EvidenceVerification(
            claim_text=claim_text,
            source_id=source_id,
            support_level=support_level,
            confidence=min(100, max(0, int(result.get("confidence", 50)))),
            explanation=result.get("explanation", ""),
            source_excerpt=result.get("relevant_quote", source_excerpt[:500]),
            line_number=line_number,
        ), cost

    except Exception as e:
        logger.exception("Error verifying citation %s: %s", source_id, e)
        return EvidenceVerification(
            claim_text=claim_text,
            source_id=source_id,
            support_level="unverified",
            confidence=0,
            explanation=f"Verifikationsfejl: {str(e)[:100]}",
            source_excerpt="",
            line_number=line_number,
        ), 0.0


def extract_cited_sentences(markdown_text: str) -> list[tuple[str, list[str], int]]:
    """
    Extract sentences with citations from markdown text.

    Returns list of (sentence_text, [source_ids], line_number)
    """
    citation_pattern = re.compile(r"\[(?:S:)?(SRC\d+)\]")
    results = []

    for line_no, line in enumerate(markdown_text.split("\n"), start=1):
        # Skip headers and empty lines
        if not line.strip() or line.strip().startswith("#"):
            continue

        # Find all citations in this line
        citations = citation_pattern.findall(line)
        if citations:
            # Remove citations from text for claim
            claim_text = citation_pattern.sub("", line).strip()
            # Remove bullet points and numbering
            claim_text = re.sub(r"^[\s\-\*\d\.]+", "", claim_text).strip()
            if claim_text and len(claim_text) > 10:
                results.append((claim_text, citations, line_no))

    return results


async def verify_all_citations(
    markdown_text: str,
    sources: dict[str, str],  # source_id -> content
    anthropic_client: AsyncAnthropic,
    *,
    max_concurrent: int = 5,
    max_verifications: int = 50,
) -> tuple[VerificationSummary, float]:
    """
    Verify all citations in a markdown document.

    Args:
        markdown_text: The procedure markdown with citations
        sources: Dict mapping source_id to source content
        anthropic_client: Anthropic API client
        max_concurrent: Maximum concurrent verification calls
        max_verifications: Maximum number of citations to verify

    Returns:
        Tuple of (VerificationSummary, total_cost_usd)
    """
    cited_sentences = extract_cited_sentences(markdown_text)

    if not cited_sentences:
        return VerificationSummary(
            total_citations=0,
            fully_supported=0,
            partially_supported=0,
            not_supported=0,
            contradicted=0,
            unverified=0,
            overall_score=100,
            verifications=[],
        ), 0.0

    # Limit number of verifications for cost control
    if len(cited_sentences) > max_verifications:
        logger.warning(
            "Limiting verification from %d to %d citations",
            len(cited_sentences),
            max_verifications,
        )
        cited_sentences = cited_sentences[:max_verifications]

    # Create verification tasks
    semaphore = asyncio.Semaphore(max_concurrent)

    async def verify_with_semaphore(
        claim: str, source_ids: list[str], line_no: int
    ) -> list[tuple[EvidenceVerification, float]]:
        async with semaphore:
            results = []
            for source_id in source_ids:
                source_content = sources.get(source_id, "")
                if source_content:
                    result, cost = await verify_citation(
                        claim, source_content, source_id, anthropic_client, line_number=line_no
                    )
                    results.append((result, cost))
                else:
                    results.append((
                        EvidenceVerification(
                            claim_text=claim,
                            source_id=source_id,
                            support_level="unverified",
                            confidence=0,
                            explanation="Kilde ikke fundet",
                            source_excerpt="",
                            line_number=line_no,
                        ),
                        0.0,
                    ))
            return results

    # Run verifications concurrently
    tasks = [
        verify_with_semaphore(claim, source_ids, line_no)
        for claim, source_ids, line_no in cited_sentences
    ]
    all_results = await asyncio.gather(*tasks)

    # Flatten results
    verifications: list[EvidenceVerification] = []
    total_cost = 0.0
    for result_list in all_results:
        for verification, cost in result_list:
            verifications.append(verification)
            total_cost += cost

    # Count support levels
    counts = {
        "fully_supported": 0,
        "partially_supported": 0,
        "not_supported": 0,
        "contradicted": 0,
        "unverified": 0,
    }
    for v in verifications:
        counts[v.support_level] = counts.get(v.support_level, 0) + 1

    # Calculate overall score
    total = len(verifications)
    if total > 0:
        # Weighted score: fully=100, partial=60, not_supported=20, contradicted=0, unverified=50
        weighted_sum = (
            counts["fully_supported"] * 100
            + counts["partially_supported"] * 60
            + counts["not_supported"] * 20
            + counts["contradicted"] * 0
            + counts["unverified"] * 50
        )
        overall_score = int(weighted_sum / total)
    else:
        overall_score = 100

    return VerificationSummary(
        total_citations=total,
        fully_supported=counts["fully_supported"],
        partially_supported=counts["partially_supported"],
        not_supported=counts["not_supported"],
        contradicted=counts["contradicted"],
        unverified=counts["unverified"],
        overall_score=overall_score,
        verifications=verifications,
    ), total_cost


def read_source_content(source_path: str | Path | None) -> str:
    """Read source content from file."""
    if not source_path:
        return ""
    try:
        path = Path(source_path)
        if path.exists() and path.is_file():
            return path.read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeDecodeError) as e:
        logger.warning("Failed to read source file %s: %s", source_path, e)
    return ""


def verification_to_dict(v: EvidenceVerification) -> dict[str, Any]:
    """Convert EvidenceVerification to dict for JSON serialization."""
    return {
        "claim_text": v.claim_text,
        "source_id": v.source_id,
        "support_level": v.support_level,
        "confidence": v.confidence,
        "explanation": v.explanation,
        "source_excerpt": v.source_excerpt,
        "line_number": v.line_number,
    }


def summary_to_dict(s: VerificationSummary) -> dict[str, Any]:
    """Convert VerificationSummary to dict for JSON serialization."""
    return {
        "total_citations": s.total_citations,
        "fully_supported": s.fully_supported,
        "partially_supported": s.partially_supported,
        "not_supported": s.not_supported,
        "contradicted": s.contradicted,
        "unverified": s.unverified,
        "overall_score": s.overall_score,
        "verifications": [verification_to_dict(v) for v in s.verifications],
    }

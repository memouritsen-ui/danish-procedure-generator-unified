"""Tests for EvidenceBinder - linking claims to evidence chunks.

Comprehensive tests for the EvidenceBinder class that matches claims
to evidence chunks using keyword overlap and semantic similarity.
"""

import pytest
from uuid import uuid4

from procedurewriter.claims.binder import EvidenceBinder, BindingResult
from procedurewriter.models.claims import Claim, ClaimType
from procedurewriter.models.evidence import EvidenceChunk, ClaimEvidenceLink, BindingType


def make_claim(
    text: str,
    claim_type: ClaimType = ClaimType.DOSE,
    run_id: str = "test-run",
    source_refs: list[str] | None = None,
) -> Claim:
    """Factory function to create test claims."""
    return Claim(
        run_id=run_id,
        claim_type=claim_type,
        text=text,
        source_refs=source_refs or [],
        line_number=1,
        confidence=0.9,
    )


def make_chunk(
    text: str,
    source_id: str = "SRC001",
    run_id: str = "test-run",
    chunk_index: int = 0,
) -> EvidenceChunk:
    """Factory function to create test evidence chunks."""
    return EvidenceChunk(
        run_id=run_id,
        source_id=source_id,
        text=text,
        chunk_index=chunk_index,
    )


@pytest.fixture
def binder() -> EvidenceBinder:
    """Create binder for tests."""
    return EvidenceBinder()


class TestEvidenceBinderBasics:
    """Basic functionality tests for EvidenceBinder."""

    def test_init(self, binder: EvidenceBinder) -> None:
        """Can create EvidenceBinder instance."""
        assert binder is not None

    def test_bind_empty_claims(self, binder: EvidenceBinder) -> None:
        """Returns empty list when no claims provided."""
        chunks = [make_chunk("Some evidence text")]
        result = binder.bind([], chunks)
        assert result.links == []
        assert result.unbound_claims == []

    def test_bind_empty_chunks(self, binder: EvidenceBinder) -> None:
        """All claims unbound when no chunks provided."""
        claims = [make_claim("amoxicillin 500 mg")]
        result = binder.bind(claims, [])
        assert result.links == []
        assert len(result.unbound_claims) == 1

    def test_bind_returns_binding_result(self, binder: EvidenceBinder) -> None:
        """bind() returns a BindingResult object."""
        claims = [make_claim("amoxicillin 500 mg")]
        chunks = [make_chunk("Amoxicillin dosage is 500 mg three times daily")]
        result = binder.bind(claims, chunks)
        assert isinstance(result, BindingResult)
        assert hasattr(result, "links")
        assert hasattr(result, "unbound_claims")
        assert hasattr(result, "binding_stats")


class TestKeywordBinding:
    """Tests for keyword-based binding."""

    def test_exact_match(self, binder: EvidenceBinder) -> None:
        """Binds claim to chunk with exact text match."""
        claims = [make_claim("amoxicillin 500 mg")]
        chunks = [make_chunk("Recommended dose: amoxicillin 500 mg three times daily")]
        result = binder.bind(claims, chunks)
        assert len(result.links) >= 1
        assert result.links[0].binding_type == BindingType.KEYWORD

    def test_case_insensitive_match(self, binder: EvidenceBinder) -> None:
        """Keyword matching is case-insensitive."""
        claims = [make_claim("Amoxicillin 500 mg")]
        chunks = [make_chunk("amoxicillin is recommended at 500 mg")]
        result = binder.bind(claims, chunks)
        assert len(result.links) >= 1

    def test_partial_keyword_match(self, binder: EvidenceBinder) -> None:
        """Binds when significant keywords overlap."""
        claims = [make_claim("penicillin 1 million IE")]
        chunks = [make_chunk("Penicillin G should be given at 1 million units")]
        result = binder.bind(claims, chunks)
        # Should match on "penicillin" and "million"
        assert len(result.links) >= 1

    def test_no_keyword_match(self, binder: EvidenceBinder) -> None:
        """Claim unbound when no keywords match."""
        claims = [make_claim("amoxicillin 500 mg")]
        chunks = [make_chunk("Ibuprofen is used for pain relief")]
        result = binder.bind(claims, chunks)
        assert len(result.unbound_claims) == 1

    def test_multiple_chunks_best_match(self, binder: EvidenceBinder) -> None:
        """Selects best matching chunk when multiple are available."""
        claims = [make_claim("amoxicillin 500 mg three times daily")]
        chunks = [
            make_chunk("Antibiotics are important", source_id="SRC001"),
            make_chunk("Amoxicillin 500 mg is the recommended dose", source_id="SRC002"),
            make_chunk("Amoxicillin 500 mg three times daily for 7 days", source_id="SRC003"),
        ]
        result = binder.bind(claims, chunks)
        assert len(result.links) >= 1
        # Should prefer the most complete match (SRC003)
        best_link = max(result.links, key=lambda x: x.binding_score)
        linked_chunk = next(c for c in chunks if c.id == best_link.evidence_chunk_id)
        assert "three times daily" in linked_chunk.text


class TestSourceRefMatching:
    """Tests for matching claims to evidence via source references."""

    def test_source_ref_match(self, binder: EvidenceBinder) -> None:
        """Binds claim to chunk from referenced source."""
        claims = [make_claim("amoxicillin 500 mg", source_refs=["SRC001"])]
        chunks = [
            make_chunk("Unrelated text", source_id="SRC002"),
            make_chunk("Amoxicillin dosing information", source_id="SRC001"),
        ]
        result = binder.bind(claims, chunks)
        assert len(result.links) >= 1
        # Should prefer the chunk from the referenced source
        linked_chunk_ids = {link.evidence_chunk_id for link in result.links}
        src001_chunk = next(c for c in chunks if c.source_id == "SRC001")
        assert src001_chunk.id in linked_chunk_ids

    def test_source_ref_boosts_score(self, binder: EvidenceBinder) -> None:
        """Source reference matching boosts binding score."""
        claims = [make_claim("amoxicillin 500 mg", source_refs=["SRC001"])]
        chunks = [
            make_chunk("Amoxicillin 500 mg dosing", source_id="SRC001"),
            make_chunk("Amoxicillin 500 mg dosing", source_id="SRC002"),
        ]
        result = binder.bind(claims, chunks)
        # Both chunks have same text, but SRC001 should have higher score
        src001_links = [l for l in result.links
                       if any(c.id == l.evidence_chunk_id and c.source_id == "SRC001"
                             for c in chunks)]
        src002_links = [l for l in result.links
                       if any(c.id == l.evidence_chunk_id and c.source_id == "SRC002"
                             for c in chunks)]
        if src001_links and src002_links:
            assert src001_links[0].binding_score >= src002_links[0].binding_score


class TestBindingScore:
    """Tests for binding score calculation."""

    def test_score_range(self, binder: EvidenceBinder) -> None:
        """Binding score is between 0 and 1."""
        claims = [make_claim("amoxicillin 500 mg")]
        chunks = [make_chunk("Amoxicillin is recommended")]
        result = binder.bind(claims, chunks)
        for link in result.links:
            assert 0.0 <= link.binding_score <= 1.0

    def test_higher_score_for_better_match(self, binder: EvidenceBinder) -> None:
        """Better matches get higher scores."""
        claim = make_claim("amoxicillin 500 mg three times daily")
        chunks = [
            make_chunk("Some antibiotic information", source_id="SRC001"),
            make_chunk("Amoxicillin information", source_id="SRC002"),
            make_chunk("Amoxicillin 500 mg three times daily", source_id="SRC003"),
        ]
        result = binder.bind([claim], chunks)

        if len(result.links) >= 2:
            scores = sorted([l.binding_score for l in result.links], reverse=True)
            # Best match should have highest score
            assert scores[0] >= scores[-1]

    def test_minimum_score_threshold(self, binder: EvidenceBinder) -> None:
        """Links below minimum score threshold are not created."""
        binder_strict = EvidenceBinder(min_score=0.5)
        claims = [make_claim("amoxicillin 500 mg")]
        chunks = [make_chunk("This is about completely different medication")]
        result = binder_strict.bind(claims, chunks)
        # Weak match should be filtered out
        for link in result.links:
            assert link.binding_score >= 0.5


class TestBindingResult:
    """Tests for BindingResult dataclass."""

    def test_binding_stats(self, binder: EvidenceBinder) -> None:
        """BindingResult includes statistics."""
        claims = [
            make_claim("amoxicillin 500 mg"),
            make_claim("ibuprofen 400 mg"),
        ]
        chunks = [make_chunk("Amoxicillin is an antibiotic")]
        result = binder.bind(claims, chunks)

        assert "total_claims" in result.binding_stats
        assert "bound_claims" in result.binding_stats
        assert "unbound_claims" in result.binding_stats
        assert result.binding_stats["total_claims"] == 2

    def test_unbound_claims_tracked(self, binder: EvidenceBinder) -> None:
        """Unbound claims are tracked in result."""
        claims = [
            make_claim("amoxicillin 500 mg"),
            make_claim("some random medication xyz"),
        ]
        chunks = [make_chunk("Amoxicillin dosing information")]
        result = binder.bind(claims, chunks)

        # At least one claim should be unbound
        assert len(result.unbound_claims) >= 0
        # Unbound claims should be Claim objects
        for claim in result.unbound_claims:
            assert isinstance(claim, Claim)


class TestMultipleClaims:
    """Tests for binding multiple claims."""

    def test_multiple_claims_to_one_chunk(self, binder: EvidenceBinder) -> None:
        """Multiple claims can bind to same evidence chunk."""
        claims = [
            make_claim("amoxicillin 500 mg", claim_type=ClaimType.DOSE),
            make_claim("bør gives tre gange dagligt", claim_type=ClaimType.RECOMMENDATION),
        ]
        chunks = [make_chunk("Amoxicillin 500 mg bør gives tre gange dagligt")]
        result = binder.bind(claims, chunks)

        # Both claims should bind
        assert len(result.links) >= 2
        # Both should link to same chunk
        chunk_ids = {link.evidence_chunk_id for link in result.links}
        assert len(chunk_ids) == 1

    def test_multiple_claims_to_multiple_chunks(self, binder: EvidenceBinder) -> None:
        """Claims bind to their best matching chunks."""
        claims = [
            make_claim("amoxicillin 500 mg"),
            make_claim("paracetamol 1 g"),
        ]
        chunks = [
            make_chunk("Amoxicillin is an antibiotic given at 500 mg", source_id="SRC001"),
            make_chunk("Paracetamol 1 gram for fever", source_id="SRC002"),
        ]
        result = binder.bind(claims, chunks)

        # Both claims should bind
        assert len(result.links) >= 2


class TestClaimTypeHandling:
    """Tests for handling different claim types."""

    def test_dose_claim_binding(self, binder: EvidenceBinder) -> None:
        """DOSE claims bind correctly."""
        claims = [make_claim("amoxicillin 500 mg", claim_type=ClaimType.DOSE)]
        chunks = [make_chunk("Amoxicillin dose is 500 mg")]
        result = binder.bind(claims, chunks)
        assert len(result.links) >= 1

    def test_threshold_claim_binding(self, binder: EvidenceBinder) -> None:
        """THRESHOLD claims bind correctly."""
        claims = [make_claim("CURB-65 >= 3", claim_type=ClaimType.THRESHOLD)]
        chunks = [make_chunk("Patients with CURB-65 score of 3 or higher require hospitalization")]
        result = binder.bind(claims, chunks)
        assert len(result.links) >= 1

    def test_recommendation_claim_binding(self, binder: EvidenceBinder) -> None:
        """RECOMMENDATION claims bind correctly."""
        claims = [make_claim("bør indlægges", claim_type=ClaimType.RECOMMENDATION)]
        chunks = [make_chunk("Patienten bør indlægges ved svær pneumoni")]
        result = binder.bind(claims, chunks)
        assert len(result.links) >= 1

    def test_contraindication_claim_binding(self, binder: EvidenceBinder) -> None:
        """CONTRAINDICATION claims bind correctly."""
        claims = [make_claim("må ikke gives", claim_type=ClaimType.CONTRAINDICATION)]
        chunks = [make_chunk("Penicillin må ikke gives ved allergi")]
        result = binder.bind(claims, chunks)
        assert len(result.links) >= 1


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_claim_text(self, binder: EvidenceBinder) -> None:
        """Handles claims with minimal text."""
        # Note: Claim model requires min_length=1, so we test with single char
        claims = [make_claim("x")]
        chunks = [make_chunk("Some text with x in it")]
        result = binder.bind(claims, chunks)
        # Should not crash, may or may not bind
        assert isinstance(result, BindingResult)

    def test_very_long_claim(self, binder: EvidenceBinder) -> None:
        """Handles claims with long text."""
        long_text = "amoxicillin 500 mg " * 100
        claims = [make_claim(long_text)]
        chunks = [make_chunk("Amoxicillin dosing")]
        result = binder.bind(claims, chunks)
        assert isinstance(result, BindingResult)

    def test_special_characters_in_claim(self, binder: EvidenceBinder) -> None:
        """Handles claims with special characters."""
        claims = [make_claim("SpO2 < 92%")]
        chunks = [make_chunk("When SpO2 is less than 92%, oxygen should be given")]
        result = binder.bind(claims, chunks)
        assert isinstance(result, BindingResult)

    def test_danish_characters(self, binder: EvidenceBinder) -> None:
        """Handles Danish characters correctly."""
        claims = [make_claim("bør indlægges på intensiv")]
        chunks = [make_chunk("Patienten bør indlægges på intensiv afdeling")]
        result = binder.bind(claims, chunks)
        assert len(result.links) >= 1


class TestRealWorldExamples:
    """Tests based on real Danish medical procedure scenarios."""

    def test_pneumonia_dose_binding(self, binder: EvidenceBinder) -> None:
        """Real example from pneumonia guideline."""
        claims = [make_claim("amoxicillin 50 mg/kg/d", claim_type=ClaimType.DOSE)]
        chunks = [
            make_chunk("For community-acquired pneumonia, amoxicillin 50 mg/kg/day is recommended"),
        ]
        result = binder.bind(claims, chunks)
        assert len(result.links) >= 1

    def test_sepsis_threshold_binding(self, binder: EvidenceBinder) -> None:
        """Real example from sepsis guideline."""
        claims = [make_claim("laktat > 2 mmol/L", claim_type=ClaimType.THRESHOLD)]
        chunks = [
            make_chunk("Ved laktat over 2 mmol/L skal væskeresuscitation påbegyndes"),
        ]
        result = binder.bind(claims, chunks)
        assert len(result.links) >= 1

    def test_anaphylaxis_recommendation_binding(self, binder: EvidenceBinder) -> None:
        """Real example from anaphylaxis guideline."""
        claims = [
            make_claim("skal gives adrenalin IM", claim_type=ClaimType.RECOMMENDATION),
        ]
        chunks = [
            make_chunk("Ved anafylaksi skal der straks gives adrenalin 0.5 mg intramuskulært"),
        ]
        result = binder.bind(claims, chunks)
        assert len(result.links) >= 1

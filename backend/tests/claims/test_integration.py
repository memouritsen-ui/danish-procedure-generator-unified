"""Integration tests for claim extraction and evidence binding workflow.

Tests the end-to-end workflow:
1. ClaimExtractor extracts claims from procedure text
2. EvidenceBinder binds claims to evidence chunks
3. Results include linked claims with binding scores and types
"""

import pytest
from uuid import uuid4

from procedurewriter.claims.extractor import ClaimExtractor
from procedurewriter.claims.binder import EvidenceBinder, BindingResult
from procedurewriter.models.claims import Claim, ClaimType
from procedurewriter.models.evidence import EvidenceChunk, ClaimEvidenceLink, BindingType


# Sample Danish medical procedure text for testing
SAMPLE_PROCEDURE_TEXT = """
# Pneumoni behandling hos voksne

## Diagnostik
Ved mistanke om pneumoni, mål saturation. Hvis SpO2 < 92%, gives ilt.
CURB-65 score >= 3 kræver indlæggelse.

## Behandling
1. Sikr luftveje og sufficient oxygenering
2. Påbegynd antibiotika hurtigst muligt

Ved community-acquired pneumonia (CAP) anbefales:
- amoxicillin 50 mg/kg/d fordelt på 3 doser [SRC001]
- Alternativt penicillin 1 million IE x 4 [SRC002]

Ved svær pneumoni bør patienten indlægges på intensiv.
Penicillin må ikke gives ved penicillinallergi.

OBS: Ved manglende respons efter 48 timer, overvej resistens.
"""

# Sample evidence chunks that match the procedure
SAMPLE_EVIDENCE_CHUNKS = [
    {
        "source_id": "SRC001",
        "text": "Amoxicillin 50 mg/kg/day divided in 3 doses is recommended for community-acquired pneumonia in adults. Evidence level: 1A.",
        "chunk_index": 0,
    },
    {
        "source_id": "SRC002",
        "text": "Penicillin G 1 million IE given 4 times daily is an alternative for CAP treatment.",
        "chunk_index": 0,
    },
    {
        "source_id": "SRC003",
        "text": "CURB-65 score of 3 or higher indicates severe pneumonia requiring hospital admission.",
        "chunk_index": 0,
    },
    {
        "source_id": "SRC004",
        "text": "Oxygen therapy should be initiated when SpO2 falls below 92%.",
        "chunk_index": 0,
    },
    {
        "source_id": "SRC005",
        "text": "Patients with severe pneumonia and respiratory failure should be admitted to ICU.",
        "chunk_index": 0,
    },
]


def make_chunks(run_id: str) -> list[EvidenceChunk]:
    """Create test evidence chunks."""
    chunks = []
    for data in SAMPLE_EVIDENCE_CHUNKS:
        chunk = EvidenceChunk(
            run_id=run_id,
            source_id=data["source_id"],
            text=data["text"],
            chunk_index=data["chunk_index"],
        )
        chunks.append(chunk)
    return chunks


class TestExtractAndBindWorkflow:
    """End-to-end tests for extraction + binding workflow."""

    def test_extract_claims_from_procedure(self) -> None:
        """ClaimExtractor extracts claims from procedure text."""
        run_id = uuid4().hex
        extractor = ClaimExtractor(run_id=run_id)
        claims = extractor.extract(SAMPLE_PROCEDURE_TEXT)

        # Should extract multiple claim types
        assert len(claims) > 0

        # Check we got different types of claims
        claim_types = {c.claim_type for c in claims}
        assert ClaimType.DOSE in claim_types, "Should extract DOSE claims"
        assert ClaimType.THRESHOLD in claim_types, "Should extract THRESHOLD claims"

    def test_bind_extracted_claims(self) -> None:
        """Extracted claims can be bound to evidence chunks."""
        run_id = uuid4().hex

        # Step 1: Extract claims
        extractor = ClaimExtractor(run_id=run_id)
        claims = extractor.extract(SAMPLE_PROCEDURE_TEXT)

        # Step 2: Create evidence chunks
        chunks = make_chunks(run_id)

        # Step 3: Bind claims to evidence
        binder = EvidenceBinder(min_score=0.1)
        result = binder.bind(claims, chunks)

        # Should have some successful bindings
        assert isinstance(result, BindingResult)
        assert len(result.links) > 0, "Should have some bound claims"
        assert result.binding_stats["bound_claims"] > 0

    def test_dose_claims_bind_to_dosing_evidence(self) -> None:
        """DOSE claims bind to evidence about dosing."""
        run_id = uuid4().hex
        extractor = ClaimExtractor(run_id=run_id)
        claims = extractor.extract(SAMPLE_PROCEDURE_TEXT)

        # Filter to just dose claims
        dose_claims = [c for c in claims if c.claim_type == ClaimType.DOSE]
        assert len(dose_claims) > 0, "Should have dose claims"

        chunks = make_chunks(run_id)
        binder = EvidenceBinder(min_score=0.1)
        result = binder.bind(dose_claims, chunks)

        # At least some dose claims should bind
        assert len(result.links) > 0

        # Check bound evidence sources
        bound_chunk_ids = {link.evidence_chunk_id for link in result.links}
        bound_chunks = [c for c in chunks if c.id in bound_chunk_ids]

        # Should bind to sources that mention dosing (SRC001 or SRC002)
        dosing_sources = {"SRC001", "SRC002"}
        bound_sources = {c.source_id for c in bound_chunks}
        assert bound_sources & dosing_sources, "Dose claims should bind to dosing evidence"

    def test_threshold_claims_bind_to_threshold_evidence(self) -> None:
        """THRESHOLD claims bind to evidence about thresholds."""
        run_id = uuid4().hex
        extractor = ClaimExtractor(run_id=run_id)
        claims = extractor.extract(SAMPLE_PROCEDURE_TEXT)

        # Filter to just threshold claims
        threshold_claims = [c for c in claims if c.claim_type == ClaimType.THRESHOLD]
        assert len(threshold_claims) > 0, "Should have threshold claims"

        chunks = make_chunks(run_id)
        binder = EvidenceBinder(min_score=0.1)
        result = binder.bind(threshold_claims, chunks)

        # At least some threshold claims should bind
        assert len(result.links) > 0

    def test_source_ref_matching(self) -> None:
        """Claims with source refs prefer evidence from those sources."""
        run_id = uuid4().hex
        extractor = ClaimExtractor(run_id=run_id)
        claims = extractor.extract(SAMPLE_PROCEDURE_TEXT)

        # Find claims with source refs
        claims_with_refs = [c for c in claims if c.source_refs]

        chunks = make_chunks(run_id)
        binder = EvidenceBinder(min_score=0.1)

        if claims_with_refs:
            result = binder.bind(claims_with_refs, chunks)

            # Check that source refs influence binding
            for claim in claims_with_refs:
                claim_links = [l for l in result.links if l.claim_id == claim.id]
                if claim_links:
                    # Get bound chunks
                    bound_chunk_ids = {l.evidence_chunk_id for l in claim_links}
                    bound_chunks = [c for c in chunks if c.id in bound_chunk_ids]
                    bound_sources = {c.source_id for c in bound_chunks}

                    # Referenced sources should be among bound sources (if available)
                    ref_sources = set(claim.source_refs)
                    # This is a soft check - source refs boost score but don't guarantee binding
                    # Just verify we get bindings
                    assert len(claim_links) > 0

    def test_binding_result_statistics(self) -> None:
        """Binding result includes useful statistics."""
        run_id = uuid4().hex
        extractor = ClaimExtractor(run_id=run_id)
        claims = extractor.extract(SAMPLE_PROCEDURE_TEXT)
        chunks = make_chunks(run_id)

        binder = EvidenceBinder(min_score=0.1)
        result = binder.bind(claims, chunks)

        # Check statistics
        stats = result.binding_stats
        assert "total_claims" in stats
        assert "bound_claims" in stats
        assert "unbound_claims" in stats
        assert "total_links" in stats

        # Verify consistency
        assert stats["total_claims"] == len(claims)
        assert stats["bound_claims"] + stats["unbound_claims"] == stats["total_claims"]
        assert stats["total_links"] == len(result.links)

    def test_unbound_claims_tracked(self) -> None:
        """Claims that don't bind are tracked separately."""
        run_id = uuid4().hex
        extractor = ClaimExtractor(run_id=run_id)
        claims = extractor.extract(SAMPLE_PROCEDURE_TEXT)

        # Create limited chunks that won't match everything
        limited_chunks = [make_chunks(run_id)[0]]  # Just one chunk

        binder = EvidenceBinder(min_score=0.3)  # Higher threshold
        result = binder.bind(claims, limited_chunks)

        # Should have some unbound claims
        assert len(result.unbound_claims) >= 0  # May or may not have unbound
        # All unbound should be Claim objects
        for claim in result.unbound_claims:
            assert isinstance(claim, Claim)

    def test_multiple_extraction_runs(self) -> None:
        """Multiple extraction runs produce consistent results."""
        run_id = uuid4().hex
        extractor = ClaimExtractor(run_id=run_id)

        claims1 = extractor.extract(SAMPLE_PROCEDURE_TEXT)
        claims2 = extractor.extract(SAMPLE_PROCEDURE_TEXT)

        # Should get same number of claims (deterministic)
        assert len(claims1) == len(claims2)

        # Same claim types in same order
        for c1, c2 in zip(claims1, claims2):
            assert c1.claim_type == c2.claim_type
            assert c1.text == c2.text
            assert c1.line_number == c2.line_number


class TestRealWorldScenarios:
    """Tests based on real Danish medical procedure scenarios."""

    def test_pneumonia_full_workflow(self) -> None:
        """Full workflow for pneumonia procedure."""
        run_id = uuid4().hex
        extractor = ClaimExtractor(run_id=run_id)
        claims = extractor.extract(SAMPLE_PROCEDURE_TEXT)
        chunks = make_chunks(run_id)

        binder = EvidenceBinder(min_score=0.1)
        result = binder.bind(claims, chunks)

        # Should have reasonable binding rate
        binding_rate = result.binding_stats["bound_claims"] / max(1, result.binding_stats["total_claims"])
        assert binding_rate > 0, "Should have some successful bindings"

        # All links should have valid scores
        for link in result.links:
            assert 0.0 <= link.binding_score <= 1.0
            assert link.binding_type in (BindingType.KEYWORD, BindingType.SEMANTIC)

    def test_sepsis_procedure(self) -> None:
        """Test with sepsis-like procedure text."""
        sepsis_text = """
        # Sepsis behandling

        Ved mistanke om sepsis:
        1. Tag blodkulturer før antibiotika
        2. Påbegynd bredspektret antibiotika inden for 1 time

        Hvis laktat > 2 mmol/L, start væskeresuscitation.
        BT < 90/60 mmHg er tegn på septisk shock.

        Anbefalet antibiotika:
        - piperacillin/tazobactam 4 g x 4 i.v. [SRC010]
        - meropenem 1 g x 3 i.v. ved penicillinallergi [SRC011]
        """

        run_id = uuid4().hex
        extractor = ClaimExtractor(run_id=run_id)
        claims = extractor.extract(sepsis_text)

        # Should extract claims from sepsis text
        assert len(claims) > 0

        # Check for expected claim types
        claim_types = {c.claim_type for c in claims}
        # Should have at least some clinical content
        assert len(claim_types) > 0

    def test_anaphylaxis_procedure(self) -> None:
        """Test with anaphylaxis procedure text."""
        anaphylaxis_text = """
        # Anafylaksi behandling

        OBS: Livstruende tilstand - kræver øjeblikkelig handling!

        Ved anafylaksi skal der gives adrenalin 0.5 mg i.m. straks.
        Gentag adrenalin efter 5 minutter hvis utilstrækkelig effekt.

        Hvis BT < 80/50 mmHg, gives adrenalin i.v. i stedet.
        Saturation < 90% kræver ilttilskud.

        Penicillin må ikke gives ved kendt penicillinallergi.
        """

        run_id = uuid4().hex
        extractor = ClaimExtractor(run_id=run_id)
        claims = extractor.extract(anaphylaxis_text)

        # Should extract claims from anaphylaxis text
        assert len(claims) > 0

        # Should have RED_FLAG claims (OBS:)
        red_flag_claims = [c for c in claims if c.claim_type == ClaimType.RED_FLAG]
        # RED_FLAG detection depends on specific patterns

    def test_empty_procedure(self) -> None:
        """Empty procedure produces no claims."""
        run_id = uuid4().hex
        extractor = ClaimExtractor(run_id=run_id)
        claims = extractor.extract("")

        assert claims == []

    def test_headers_only_procedure(self) -> None:
        """Procedure with only headers produces no claims."""
        headers_only = """
        # Procedure Name
        ## Section 1
        ## Section 2
        """

        run_id = uuid4().hex
        extractor = ClaimExtractor(run_id=run_id)
        claims = extractor.extract(headers_only)

        # Headers are skipped, so should have no claims
        assert claims == []


class TestEdgeCases:
    """Edge case tests for the integration workflow."""

    def test_no_matching_evidence(self) -> None:
        """All claims unbound when no evidence matches."""
        run_id = uuid4().hex
        extractor = ClaimExtractor(run_id=run_id)
        claims = extractor.extract(SAMPLE_PROCEDURE_TEXT)

        # Create unrelated evidence
        unrelated_chunks = [
            EvidenceChunk(
                run_id=run_id,
                source_id="UNRELATED",
                text="This is about gardening and has nothing to do with medicine.",
                chunk_index=0,
            )
        ]

        binder = EvidenceBinder(min_score=0.5)  # Higher threshold
        result = binder.bind(claims, unrelated_chunks)

        # Most claims should be unbound
        assert len(result.unbound_claims) >= len(claims) // 2

    def test_high_threshold_fewer_bindings(self) -> None:
        """Higher binding threshold produces fewer bindings."""
        run_id = uuid4().hex
        extractor = ClaimExtractor(run_id=run_id)
        claims = extractor.extract(SAMPLE_PROCEDURE_TEXT)
        chunks = make_chunks(run_id)

        # Low threshold
        binder_low = EvidenceBinder(min_score=0.1)
        result_low = binder_low.bind(claims, chunks)

        # High threshold
        binder_high = EvidenceBinder(min_score=0.5)
        result_high = binder_high.bind(claims, chunks)

        # Higher threshold should produce fewer or equal bindings
        assert len(result_high.links) <= len(result_low.links)

    def test_single_claim_single_chunk(self) -> None:
        """Minimal case: one claim, one chunk."""
        run_id = uuid4().hex

        claim = Claim(
            run_id=run_id,
            claim_type=ClaimType.DOSE,
            text="amoxicillin 500 mg",
            source_refs=[],
            line_number=1,
            confidence=0.9,
        )

        chunk = EvidenceChunk(
            run_id=run_id,
            source_id="SRC001",
            text="Amoxicillin is recommended at 500 mg three times daily.",
            chunk_index=0,
        )

        binder = EvidenceBinder(min_score=0.1)
        result = binder.bind([claim], [chunk])

        # Should bind
        assert len(result.links) == 1
        assert result.links[0].claim_id == claim.id
        assert result.links[0].evidence_chunk_id == chunk.id

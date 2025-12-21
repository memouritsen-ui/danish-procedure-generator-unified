"""Phase 0 Validation: Test claim extraction on 3 real procedures."""

import json
from pathlib import Path
from phase0_claim_extraction_test import (
    extract_all_claims,
    validate_claim_extraction,
    EXPECTED_DOSES_PNEUMONI,
    EXPECTED_THRESHOLDS_PNEUMONI,
)

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "runs"

PROCEDURES = [
    {
        "run_id": "5e5bbba1790a48d5ae1cf7cc270cfc6f",
        "name": "Pneumoni behandling",
        "expected_dose_count": 10,
        "expected_threshold_count": 12,
    },
    {
        "run_id": "b51eaa3158604f53a71f1e66993fc402",
        "name": "Akut astma",
        "expected_dose_count": 5,  # Estimate
        "expected_threshold_count": 8,
    },
    {
        "run_id": "eca3718653d14a5680ba12ea628b4c65",
        "name": "Thoraxdræn",
        "expected_dose_count": 2,  # Estimate
        "expected_threshold_count": 4,
    },
]


def test_procedure(run_id: str, name: str) -> dict:
    """Test claim extraction on a procedure."""
    procedure_path = DATA_DIR / run_id / "procedure.md"
    sources_path = DATA_DIR / run_id / "sources.jsonl"

    if not procedure_path.exists():
        return {"error": f"procedure.md not found: {procedure_path}"}

    procedure_text = procedure_path.read_text()
    result = validate_claim_extraction(procedure_text)

    # Load sources to check binding potential
    source_ids = set()
    if sources_path.exists():
        for line in sources_path.read_text().strip().split('\n'):
            if line.strip():
                src = json.loads(line)
                source_ids.add(src.get("source_id", ""))

    # Check which claims have resolvable source refs
    resolvable = 0
    unresolvable = 0
    for claim in result["claims"]:
        for ref in claim.source_refs:
            # Extract SRC0023 from [SRC0023]
            src_id = ref.replace('[', '').replace(']', '')
            if src_id in source_ids:
                resolvable += 1
            else:
                unresolvable += 1

    result["source_ids_in_run"] = len(source_ids)
    result["resolvable_refs"] = resolvable
    result["unresolvable_refs"] = unresolvable

    return result


def main():
    print("=" * 70)
    print("PHASE 0 VALIDATION: Claim Extraction on 3 Procedures")
    print("=" * 70)

    total_claims = 0
    total_with_refs = 0
    total_resolvable = 0
    total_unresolvable = 0

    for proc in PROCEDURES:
        print(f"\n## {proc['name']} ({proc['run_id'][:8]}...)")
        print("-" * 50)

        result = test_procedure(proc["run_id"], proc["name"])

        if "error" in result:
            print(f"  ERROR: {result['error']}")
            continue

        print(f"  Total claims extracted: {result['total_claims']}")
        print(f"  By type: {result['by_type']}")
        print(f"  With source refs: {result['with_source_refs']}")
        print(f"  Without source refs: {result['without_source_refs']}")
        print(f"  Avg confidence: {result['avg_confidence']}")
        print(f"  Sources in run: {result['source_ids_in_run']}")
        print(f"  Resolvable refs: {result['resolvable_refs']}")
        print(f"  Unresolvable refs: {result['unresolvable_refs']}")

        total_claims += result['total_claims']
        total_with_refs += result['with_source_refs']
        total_resolvable += result['resolvable_refs']
        total_unresolvable += result['unresolvable_refs']

        # Show sample claims
        print(f"\n  Sample claims (first 5):")
        for claim in result['claims'][:5]:
            print(f"    [{claim.claim_type.value:12}] {claim.text[:60]}")

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total claims across 3 procedures: {total_claims}")
    print(f"Claims with source refs: {total_with_refs}")
    print(f"Resolvable to sources.jsonl: {total_resolvable}")
    print(f"Unresolvable refs: {total_unresolvable}")

    # Calculate binding rate
    if total_with_refs > 0:
        binding_rate = total_resolvable / (total_resolvable + total_unresolvable) * 100
        print(f"\nEvidence binding rate: {binding_rate:.1f}%")

    # Verdict
    print("\n" + "-" * 70)
    if total_claims > 20 and total_with_refs > total_claims * 0.5:
        print("VERDICT: Claim extraction is FEASIBLE")
        print("  - Sufficient claims extracted")
        print("  - Majority have source references")
        print("  - Can proceed to Phase 1")
    else:
        print("VERDICT: Claim extraction needs improvement")
        print("  - Review regex patterns")
        print("  - Add more claim types")


if __name__ == "__main__":
    main()

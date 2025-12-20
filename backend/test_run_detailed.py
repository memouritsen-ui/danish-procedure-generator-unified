#!/usr/bin/env python3
"""Detailed analysis of procedure generation quality."""

from __future__ import annotations

import sys
sys.path.insert(0, '.')

from procedurewriter.pipeline.processor import PipelineProcessor
from procedurewriter.pipeline.anatomical_requirements import AnatomicalValidator

# More complex test with edge cases
PROCEDURE_1_GOOD = """
Positionér patienten i lateral decubitus med syg side opad.
Palpér thoraxvæggen og identificer 5. interkostalrum i midtaksillærlinjen.
Marker punktursted inden for triangle of safety.
Desinficér området grundigt og anlæg steril afdækning.
Infiltrér med lokalbedøvelse fra hud til pleura parietalis.
Indsæt nålen i en vinkel på 45 grader over øvre ribbenrand.
Avancér nålen 2-3 cm indtil pleurahulen gennembrytes.
Bekræft position med aspiration af luft eller væske.
"""

PROCEDURE_2_WORKFLOW_HEAVY = """
Forbered proceduren ifølge afdelingens protokol.
Ring til bagvagt ved behov for assistance.
Aftal rollefordeling med teamet.
Kontakt anæstesi ved sedationsbehov.
Følg lokal retningslinje for sterilteknik.
Indsæt drænet.
Kontakt bagvagt ved komplikationer.
Tjek afdelingens instruks for efterpleje.
"""

PROCEDURE_3_MIXED = """
1. Identificer 5. interkostalrum i midtaksillærlinjen.
2. Ring til bagvagt ved usikkerhed.
3. Marker triangle of safety.
4. Følg lokal retningslinje for huddesinfektion.
5. Indsæt nålen i 45 graders vinkel.
6. Aftal med teamet om patientovervågning.
7. Avancér 2-3 cm til pleuragennembrud.
"""

PROCEDURE_4_ANGLE_VARIATIONS = """
Indsæt nålen i en vinkel på 45 grader.
Før nålen i kranial retning.
Nålen orienteres parallelt med ribbensforløb.
Penetrér pleura over øvre ribbenrand.
Tilgå i en vinkling mod venstre skulder.
"""

PROCEDURE_5_DEPTH_VARIATIONS = """
Avancér nålen 2-3 cm.
Forventet dybde er 4-7 cm hos voksne.
Indsæt ca. 3 centimeter.
Penetrer indtil 5 cm dybde.
Dybdevejledning: 2-4 cm hos normalvægtige.
"""

def analyze_procedure(name: str, content: str, processor: PipelineProcessor):
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"{'='*60}")

    result = processor.process("pleuradræn", content)

    print(f"\nINPUT ({len(content)} chars):")
    for line in content.strip().split('\n')[:5]:
        print(f"  {line.strip()[:70]}")
    if len(content.strip().split('\n')) > 5:
        print(f"  ... ({len(content.strip().split(chr(10)))} lines total)")

    print(f"\nRESULTS:")
    print(f"  Quality Score: {result.quality_score:.2f}")
    print(f"  Validation: {'✓ PASS' if result.anatomical_validation.is_valid else '✗ FAIL'}")
    print(f"  Has Depth: {result.anatomical_validation.has_depth_guidance}")
    print(f"  Has Angle: {result.anatomical_validation.has_angle_guidance}")
    print(f"  Completeness: {result.anatomical_validation.completeness_score:.2f}")

    print(f"\n  Workflow Removed ({len(result.workflow_removed)} items):")
    for item in result.workflow_removed[:3]:
        print(f"    ❌ {item[:60]}...")
    if len(result.workflow_removed) > 3:
        print(f"    ... and {len(result.workflow_removed) - 3} more")

    print(f"\n  Filtered Content ({len(result.filtered_content)} chars):")
    filtered_preview = result.filtered_content[:200]
    print(f"    {filtered_preview}...")

    # Check for issues
    issues = []

    # Check if step numbers are orphaned
    import re
    orphaned = re.findall(r'\b(\d+)\.\s*$', result.filtered_content)
    if orphaned:
        issues.append(f"Orphaned step numbers: {orphaned}")

    # Check if markdown structure is preserved
    if '##' in content and '##' not in result.filtered_content:
        issues.append("Markdown headings lost")

    if '\n' in content and '\n' not in result.filtered_content:
        issues.append("Line breaks lost - content flattened")

    # Check step sequence
    steps_in = re.findall(r'^(\d+)\.', content, re.MULTILINE)
    steps_out = re.findall(r'(\d+)\.', result.filtered_content)
    if steps_in and steps_out:
        if steps_out != sorted(set(steps_out), key=int):
            issues.append(f"Step sequence broken: {steps_out}")

    if issues:
        print(f"\n  ⚠️  ISSUES DETECTED:")
        for issue in issues:
            print(f"    - {issue}")
    else:
        print(f"\n  ✓ No structural issues detected")

    return result

def main():
    print("=" * 60)
    print("DETAILED PROCEDURE QUALITY ANALYSIS")
    print("=" * 60)

    processor = PipelineProcessor()

    results = {}

    # Test each scenario
    results['good'] = analyze_procedure("GOOD CLINICAL CONTENT", PROCEDURE_1_GOOD, processor)
    results['workflow'] = analyze_procedure("WORKFLOW-HEAVY CONTENT", PROCEDURE_2_WORKFLOW_HEAVY, processor)
    results['mixed'] = analyze_procedure("MIXED CONTENT", PROCEDURE_3_MIXED, processor)
    results['angle'] = analyze_procedure("ANGLE VARIATIONS", PROCEDURE_4_ANGLE_VARIATIONS, processor)
    results['depth'] = analyze_procedure("DEPTH VARIATIONS", PROCEDURE_5_DEPTH_VARIATIONS, processor)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    print("\nQuality Scores:")
    for name, result in results.items():
        emoji = "✓" if result.quality_score >= 0.7 else "⚠️" if result.quality_score >= 0.5 else "✗"
        print(f"  {emoji} {name}: {result.quality_score:.2f}")

    print("\nAngle Detection Accuracy:")
    # PROCEDURE_4 should have angle detection = True
    if results['angle'].anatomical_validation.has_angle_guidance:
        print("  ✓ Angle variations correctly detected")
    else:
        print("  ✗ PROBLEM: Angle variations NOT detected")
        print("    Content had: '45 grader', 'kranial retning', 'parallelt med'")

    print("\nDepth Detection Accuracy:")
    if results['depth'].anatomical_validation.has_depth_guidance:
        print("  ✓ Depth variations correctly detected")
    else:
        print("  ✗ PROBLEM: Depth variations NOT detected")

    print("\nWorkflow Filtering:")
    # PROCEDURE_2 should have almost all content removed
    wf_result = results['workflow']
    if len(wf_result.filtered_content.strip()) < 50:
        print("  ✓ Workflow-heavy content correctly minimized")
    else:
        print(f"  ⚠️  {len(wf_result.filtered_content)} chars remain after filtering")

if __name__ == "__main__":
    main()

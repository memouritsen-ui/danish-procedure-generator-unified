#!/usr/bin/env python3
"""Test script to generate a procedure document and analyze quality."""

from __future__ import annotations

import sys
sys.path.insert(0, '.')

from procedurewriter.pipeline.processor import PipelineProcessor
from procedurewriter.pipeline.clinical_prompts import ClinicalPromptBuilder
from procedurewriter.pipeline.anatomical_requirements import AnatomicalValidator
from procedurewriter.pipeline.workflow_filter import WorkflowFilter

# Simulated procedure content (what an LLM might generate)
SIMULATED_PROCEDURE_CONTENT = """
## Indikationer
- Traumatisk pneumothorax
- Spontan pneumothorax >2 cm eller symptomatisk
- Iatrogen pneumothorax efter central venøs kateteranlæggelse
- Pleuraeffusion med respiratorisk kompromittering

## Kontraindikationer
- Relative: koagulationsdefekter, antikoagulationsbehandling
- Overvej ultralydsvejledt adgang ved svær adipositas

## Udstyr
- Thoraxdræn-sæt (typisk 20-28 Fr for voksne)
- Lokalanæstetikum (lidocain 1% med adrenalin)
- Sterilt afdækningskit
- Suturmateriale
- Vandlås eller Heimlich-ventil

## Fremgangsmåde (trin-for-trin)
1. Positionér patienten i lateral decubitus med syg side opad, eller siddende med arm eleveret.
2. Palpér thoraxvæggen og identificer 5. interkostalrum i midtaksillærlinjen.
3. Marker punktursted inden for triangle of safety (anteriort for m. latissimus dorsi, lateralt for m. pectoralis major, over ribben niveau 5-6).
4. Desinficér området grundigt og anlæg steril afdækning.
5. Ring til bagvagt ved usikkerhed om indikation.
6. Infiltrér med lokalbedøvelse fra hud til og med pleura parietalis. Test med aspiration.
7. Udfør hudincision på ca. 2 cm parallelt med ribbensforløb.
8. Brug peang til stump dissektion ned til pleura. Penetrér pleura over øvre ribbenrand for at undgå interkostale kar.
9. Følg lokal retningslinje for drænvalg.
10. Indsæt finger for at bekræfte pleuraadgang og ekskludere adhæsioner.
11. Indsæt dræn og avancér 2-3 cm efter pleuragennembrud. Sørg for at alle drænhuller er intrapleuralt.
12. Tilslut vandlås og verificér oscillation og evt. luftlækage.
13. Suturér drænet fast og anlæg forbinding.
14. Aftal rollefordeling med sygeplejepersonale.
15. Bestil kontrolrøntgen thorax.

## Komplikationer
- Blødning fra interkostale kar
- Lungelæsion
- Infektion
- Reekspansionslungeødem
- Subkutan emfysem

## Sikkerhedsboks
- STOP ved pludselig forværring: overvej spændingspneumothorax
- Ved massiv luftlækage: tjek for bronkieruptur
- Kontakt bagvagt ved usædvanlig modstand eller anatomiske varianter
"""

def main():
    print("=" * 60)
    print("DANISH PROCEDURE GENERATOR - QUALITY ANALYSIS")
    print("=" * 60)
    print()

    # Initialize components
    processor = PipelineProcessor()
    prompt_builder = ClinicalPromptBuilder()

    # Generate the prompt that would guide LLM
    print("1. CLINICAL PROMPT FOR LLM")
    print("-" * 40)
    prompt = prompt_builder.build_system_prompt("pleuradræn")
    print(prompt[:1500] + "..." if len(prompt) > 1500 else prompt)
    print()

    # Process the simulated content through our pipeline
    print("2. PROCESSING SIMULATED PROCEDURE CONTENT")
    print("-" * 40)
    result = processor.process("pleuradræn", SIMULATED_PROCEDURE_CONTENT)

    print(f"Quality Score: {result.quality_score:.2f}/1.00")
    print(f"Anatomical Validation: {'PASSED' if result.anatomical_validation.is_valid else 'FAILED'}")
    print(f"  - Has depth guidance: {result.anatomical_validation.has_depth_guidance}")
    print(f"  - Has angle guidance: {result.anatomical_validation.has_angle_guidance}")
    print(f"  - Completeness: {result.anatomical_validation.completeness_score:.2f}")
    print()

    print("3. WORKFLOW CONTENT REMOVED")
    print("-" * 40)
    if result.workflow_removed:
        for item in result.workflow_removed:
            print(f"  ❌ {item}")
    else:
        print("  (No workflow content detected)")
    print()

    print("4. MISSING ANATOMICAL ELEMENTS")
    print("-" * 40)
    if result.anatomical_validation.missing_landmarks:
        for lm in result.anatomical_validation.missing_landmarks:
            print(f"  ⚠️  {lm}")
    else:
        print("  ✓ All required landmarks present")
    print()

    print("5. SUGGESTIONS FOR IMPROVEMENT")
    print("-" * 40)
    if result.suggestions:
        for i, s in enumerate(result.suggestions, 1):
            print(f"  {i}. {s}")
    else:
        print("  ✓ No suggestions - content meets requirements")
    print()

    print("6. FILTERED CONTENT (after pipeline)")
    print("-" * 40)
    print(result.filtered_content)
    print()

    print("=" * 60)
    print("ANALYSIS COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    main()

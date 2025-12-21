# Workflow Guardrails (Must Follow)

## Always Do
- Read `docs/BUILD_PLAN.md` at session start.
- Use TDD: write or update tests before or alongside behavior changes.
- Keep evidence policy STRICT; never downgrade without explicit approval.
- Verify evidence report uses the final published markdown.
- Preserve audit trails: hashes, manifests, selection reports.

## Evidence Requirements
- Always attempt NICE, Cochrane, and PubMed meta-analyses.
- Always include Danish guideline library results when available.
- Explicitly label evidence strength and limitations.
- Fail fast if minimum evidence tiers are not met.

## Output Requirements
- Chapter must follow canonical structure.
- Every factual claim must have a citation tag.
- Invasive procedures must include anatomy, landmarks, depth/angle guidance, and complications.

## Safety and Quality Gates
- No placeholder text in final outputs.
- No silent fallback to low-quality sources.
- Always log warnings in run manifest.
- Add or update regression tests for any pipeline changes.

## Change Control
- Keep changes small and traceable.
- Update docs and tests with each functional change.
- If a change impacts prompts or structure, update the template config.

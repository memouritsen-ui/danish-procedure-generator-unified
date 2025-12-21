# Build Plan (Gold Standard Procedure Manual)

Intent: evolve Danish Procedure Generator into a gold-standard, evidence-first procedure manual generator that produces consistent chapter outputs from only a procedure name, grounded in Danish guidelines plus top-tier international evidence (NICE, Cochrane, PubMed meta-analyses).

## Non-Negotiable Requirements
- Every factual claim must be cited; evidence policy is STRICT.
- Use local Danish guideline library at `~/guideline_harvester/library`.
- Always attempt NICE + Cochrane + PubMed systematic reviews/meta-analyses before lower tiers.
- Output must follow the canonical chapter structure and be consistent across procedures.
- Meta-analysis results must inform the final chapter (not just be saved as artifacts).

## Phases

### Phase 0: Execution Guardrails
- Add new guardrail docs and agent instructions.
- Archive legacy plans to avoid conflicting instructions.
- Definition of Done (DoD): `docs/WORKFLOW_GUARDRAILS.md` and `AGENTS.md` present; legacy plans archived.

### Phase 1: Evidence Source Pipeline
- Implement unified evidence selection: NICE + Cochrane + PubMed meta-analyses + local Danish guidelines.
- Enforce evidence hierarchy and minimum per-tier requirements.
- Persist a selection report per run.
- DoD: selection report present; strict policy enforces minimum evidence tiers; no silent fallbacks.

### Phase 2: Meta-Analysis Integration
- Run meta-analysis earlier in pipeline.
- Generate structured summary used directly in writing prompts.
- If quantitative data is insufficient, provide explicit narrative synthesis with limitations.
- DoD: meta-analysis summary cited in the final chapter and included in evidence report.

### Phase 3: Canonical Chapter Structure
- Update author guide/template to align with manual-wide structure.
- Enforce required sections and anatomical/technique requirements for invasive procedures.
- DoD: chapter structure is stable across runs and validated by tests.

### Phase 4: Verification and Consistency
- Evidence report must match final published markdown (post-polish/generalization).
- Implement cross-chapter terminology normalization and unit consistency checks.
- DoD: evidence report consistency test passes; terminology consistency test passes.

### Phase 5: QA and Regression
- Add golden procedure fixtures (invasive + non-invasive).
- Add integration tests for library search + external evidence.
- DoD: tests pass locally; outputs meet checklist in `docs/WORKFLOW_GUARDRAILS.md`.

## External Evidence Sources (Required)
- NICE guidelines (API or search)
- Cochrane systematic reviews
- PubMed meta-analyses and RCTs
- Danish national and regional guidelines (local library)

## Run Configuration Defaults
- Evidence policy: STRICT
- LLM model: highest quality available
- Source selection: tiered and explicit
- Max iterations: >=3 for quality loop

## Definition of Done (Global)
- Consistent chapter output from only a procedure name.
- Evidence gating prevents low-grade output.
- Meta-analysis results inform chapter decisions.
- Full audit trail for sources, evidence scores, and iterations.

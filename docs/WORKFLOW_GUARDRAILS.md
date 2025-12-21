# Workflow Guardrails (Must Follow)

## Always Do
- Read `docs/BUILD_PLAN.md` at session start.
- Use TDD: write or update tests before or alongside behavior changes.
- Keep evidence policy STRICT; never downgrade without explicit approval.
- Verify evidence report uses the final published markdown.
- Preserve audit trails: hashes, manifests, selection reports.

## Evidence Policy Requirements (STRICT Mode)

### Model Requirements
- Default LLM model is GPT-5.2 for gold-standard output quality.
- Pricing: $15/MTok input, $60/MTok output.

### Citation Format
- All citations MUST use format: `[S:SRC0001]` (not `[SRC0001]`).
- StyleAgent must preserve all citations during polishing.
- CitationValidationError is raised for unsourced claims in strict mode.

### Evidence Scoring Thresholds
- Minimum token overlap: 3 tokens
- Minimum BM25 score: 1.5
- Minimum overlap ratio: 0.15 (15% of query tokens)
- Minimum verification score: 70%

### Per-Tier Source Requirements
In strict mode, the pipeline enforces:
- At least 1 NICE guideline source (when available)
- At least 1 Cochrane systematic review (when available)
- At least 1 PubMed meta-analysis or systematic review (when available)
- Warning issued if any tier is missing; error raised if all high-evidence tiers fail.

### HTTP Client Requirements
- User-Agent header: `DanishProcedureGenerator/1.0`
- Per-host throttling:
  - PubMed/NCBI: 0.4 seconds minimum
  - NICE: 1.0 second minimum
  - Cochrane: 1.0 second minimum

## Pipeline Stage Order

1. **Source Fetching**: Library + PubMed + International sources
2. **Seed URL Filtering**: Filter by `procedure_keywords` (case-insensitive)
3. **Source Selection**: Rank and select top sources per tier
4. **Writer Stage**: Generate initial markdown
5. **Meta-Analysis**: Synthesize from ALL source types (not just PubMed)
6. **StyleAgent**: Polish markdown while preserving citations and structure
7. **ContentGeneralizer**: Replace hospital-specific content
8. **Evidence Verification**: LLM-based citation verification (required in strict mode)
9. **Structure Validation**: Validate canonical 14-section structure
10. **DOCX Generation**: Final document output

## Document Structure (Canonical 14 Sections)

Required sections from `config/author_guide.yaml`:
1. Formål og Målgruppe
2. Scope og Setting
3. Key Points
4. Indikationer
5. Kontraindikationer
6. Anatomi og orientering
7. Forudsætninger
8. Udstyr og Forberedelse
9. Procedure (trin-for-trin)
10. Monitorering
11. Komplikationer
12. Dokumentation og Kommunikation
13. Kvalitetstjekliste
14. Evidens og Meta-analyse

## Evidence Hierarchy (Priority Order)

| Tier | Source Type | Priority Score |
|------|-------------|----------------|
| 1 | Danish Guidelines (SST, DSAM) | 1000 |
| 2 | Nordic Guidelines | 900 |
| 3 | European Guidelines (ESC, ERS) | 850 |
| 4 | International (NICE, WHO, CDC) | 800 |
| 5 | Systematic Reviews + Cochrane | 700 |
| 6 | Practice Guidelines | 650 |
| 7 | RCTs | 500 |
| 8 | Observational Studies | 300 |
| 9 | Case Reports | 150 |
| 10 | Unclassified | 100 |

## Safety and Quality Gates
- No placeholder text in final outputs.
- No silent fallback to low-quality sources.
- No fallback citation injection in strict mode (raises CitationValidationError).
- Always log warnings in run manifest.
- Add or update regression tests for any pipeline changes.

## Change Control
- Keep changes small and traceable.
- Update docs and tests with each functional change.
- If a change impacts prompts or structure, update the template config.

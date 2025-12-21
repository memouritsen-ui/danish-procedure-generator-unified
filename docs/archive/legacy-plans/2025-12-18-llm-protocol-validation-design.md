# LLM-Based Protocol Validation Design

## Problem

Current validation uses pattern matching that produces noise, not insights. A doctor seeing "Generated procedure mentions 0.5 ml" learns nothing useful.

## Solution

Use Claude Haiku to semantically compare generated procedures against approved hospital protocols, identifying clinically meaningful conflicts with explanations.

## Implementation Tasks

### 1. Add LLM validation function to protocols.py

**File:** `backend/procedurewriter/protocols.py`

Add new async function:
```python
async def validate_run_against_protocol_llm(
    run_markdown: str,
    protocol_text: str,
    protocol_id: str,
    protocol_name: str,
    anthropic_client: anthropic.AsyncAnthropic,
) -> ValidationResult
```

- Build comparison prompt with both texts
- Call Claude Haiku (claude-3-haiku-20240307)
- Parse JSON response
- Return ValidationResult with real conflicts

### 2. Update API endpoint

**File:** `backend/procedurewriter/main.py`

- Make `/api/runs/{run_id}/validate` async
- Initialize Anthropic client from settings
- Call new LLM validation function
- Handle errors gracefully (timeout, invalid JSON, no API key)
- Track validation cost

### 3. Update frontend

**File:** `frontend/src/pages/RunPage.tsx`

- Display `compatibility_score` (0-100%) instead of broken content_similarity
- Show `summary` text from LLM
- Conflicts already display correctly (no change needed)

### 4. Update API types

**File:** `frontend/src/api.ts`

- Add `compatibility_score: number` to ValidationResult
- Add `summary: string` to ValidationResult

## Prompt Structure

```
You are a medical protocol validator. Compare a generated procedure against an approved hospital protocol and identify clinically significant conflicts.

APPROVED PROTOCOL:
{protocol_text}

GENERATED PROCEDURE:
{procedure_text}

Analyze for conflicts in:
1. DOSING - Different doses for same medication/situation
2. TIMING - Different intervals, durations, sequences
3. CONTRAINDICATIONS - Generated allows what protocol forbids
4. OMISSIONS - Critical protocol steps missing from generated
5. ADDITIONS - Generated adds unsupported interventions

Severity levels:
- CRITICAL: Could cause patient harm
- WARNING: Deviation requiring review
- INFO: Minor acceptable variation

Return JSON only:
{
  "has_conflicts": boolean,
  "compatibility_score": 0-100,
  "summary": "1-2 sentence assessment",
  "conflicts": [...]
}

Only flag genuine clinical conflicts. Equivalent medications, acceptable dose ranges, and stylistic differences are NOT conflicts.
```

## Error Handling

- No API key: Show "Validering kræver API-nøgle"
- Invalid JSON: Retry once, then "Validering fejlede"
- Timeout (30s): Show "Validering timeout"
- Protocol too long: Truncate to 8000 chars

## Cost

~$0.008 per validation with Haiku (2000 input + 500 output tokens)

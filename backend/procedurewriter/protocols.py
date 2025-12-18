"""
Hospital protocol management and validation.

Handles:
- Protocol CRUD operations
- Text extraction from PDF/DOCX
- Similarity search
- Conflict detection between generated procedures and approved protocols
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import re
import shutil
import sqlite3
import uuid
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from procedurewriter.db import utc_now_iso

logger = logging.getLogger(__name__)


@dataclass
class Protocol:
    """Hospital protocol record."""

    protocol_id: str
    name: str
    name_normalized: str
    description: str | None
    status: str
    version: str | None
    approved_by: str | None
    approved_at_utc: str | None
    raw_path: str | None
    normalized_path: str | None
    normalized_text: str | None  # Loaded on demand
    raw_sha256: str | None
    created_at_utc: str
    updated_at_utc: str


@dataclass
class ConflictItem:
    """A specific conflict between generated and approved content."""

    section: str
    conflict_type: str  # "dosing", "timing", "procedure", "equipment", "contraindication"
    generated_text: str
    approved_text: str
    severity: str  # "critical", "warning", "info"
    explanation: str


@dataclass
class ValidationResult:
    """Result of validating a run against a protocol."""

    protocol_id: str
    protocol_name: str
    similarity_score: float  # Legacy field, kept for compatibility
    conflicts: list[ConflictItem]
    sections_compared: int
    sections_matched: int
    # New LLM-based fields
    compatibility_score: int | None = None  # 0-100 from LLM
    summary: str | None = None  # LLM assessment summary
    validation_cost_usd: float | None = None  # Cost of LLM call


def normalize_protocol_name(name: str) -> str:
    """Normalize protocol/procedure name for matching."""
    normalized = name.lower().strip()
    # Remove punctuation and special chars, keep only alphanumeric and spaces
    normalized = re.sub(r"[^\w\s]", "", normalized)
    # Collapse whitespace
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def _connect(db_path: Path) -> sqlite3.Connection:
    """Get database connection."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _row_to_protocol(row: sqlite3.Row, normalized_text: str | None = None) -> Protocol:
    """Convert database row to Protocol object."""
    return Protocol(
        protocol_id=row["protocol_id"],
        name=row["name"],
        name_normalized=row["name_normalized"],
        description=row["description"],
        status=row["status"],
        version=row["version"],
        approved_by=row["approved_by"],
        approved_at_utc=row["approved_at_utc"],
        raw_path=row["raw_path"],
        normalized_path=row["normalized_path"],
        normalized_text=normalized_text,
        raw_sha256=row["raw_sha256"],
        created_at_utc=row["created_at_utc"],
        updated_at_utc=row["updated_at_utc"],
    )


# --- Text Extraction ---


def extract_text_from_pdf(file_path: Path) -> str:
    """Extract text from a PDF file."""
    from pypdf import PdfReader

    reader = PdfReader(str(file_path))
    text_parts = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            text_parts.append(text)
    return "\n\n".join(text_parts)


def extract_text_from_docx(file_path: Path) -> str:
    """Extract text from a DOCX file."""
    from docx import Document

    doc = Document(str(file_path))
    text_parts = []
    for para in doc.paragraphs:
        if para.text.strip():
            text_parts.append(para.text)
    return "\n".join(text_parts)


def extract_text(file_path: Path) -> str:
    """Extract text from a file based on its extension."""
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        return extract_text_from_pdf(file_path)
    elif suffix in (".docx", ".doc"):
        return extract_text_from_docx(file_path)
    elif suffix == ".txt":
        return file_path.read_text(encoding="utf-8")
    else:
        raise ValueError(f"Unsupported file type: {suffix}")


# --- Protocol CRUD Operations ---


def list_protocols(db_path: Path, status: str | None = "active") -> list[Protocol]:
    """List all protocols, optionally filtered by status."""
    with _connect(db_path) as conn:
        if status:
            cursor = conn.execute(
                "SELECT * FROM protocols WHERE status = ? ORDER BY name",
                (status,),
            )
        else:
            cursor = conn.execute("SELECT * FROM protocols ORDER BY name")
        rows = cursor.fetchall()
    return [_row_to_protocol(row) for row in rows]


def get_protocol(db_path: Path, protocol_id: str, load_text: bool = False) -> Protocol | None:
    """Get a specific protocol by ID."""
    with _connect(db_path) as conn:
        cursor = conn.execute(
            "SELECT * FROM protocols WHERE protocol_id = ?",
            (protocol_id,),
        )
        row = cursor.fetchone()

    if not row:
        return None

    normalized_text = None
    if load_text and row["normalized_path"]:
        with contextlib.suppress(Exception):
            normalized_text = Path(row["normalized_path"]).read_text(encoding="utf-8")

    return _row_to_protocol(row, normalized_text)


def upload_protocol(
    db_path: Path,
    file_path: Path,
    name: str,
    description: str | None = None,
    version: str | None = None,
    approved_by: str | None = None,
    storage_dir: Path | None = None,
) -> str:
    """
    Upload a protocol file (PDF or DOCX).

    Returns protocol_id.
    """
    protocol_id = str(uuid.uuid4())[:8]
    now = utc_now_iso()

    # Determine storage location
    if storage_dir is None:
        storage_dir = Path("data/protocols")
    storage_dir.mkdir(parents=True, exist_ok=True)

    # Copy raw file
    suffix = file_path.suffix.lower()
    raw_dest = storage_dir / f"{protocol_id}_raw{suffix}"
    shutil.copy(file_path, raw_dest)

    # Calculate raw hash
    raw_sha256 = hashlib.sha256(raw_dest.read_bytes()).hexdigest()

    # Extract text
    text = extract_text(raw_dest)

    # Save normalized text
    norm_dest = storage_dir / f"{protocol_id}_normalized.txt"
    norm_dest.write_text(text, encoding="utf-8")
    normalized_sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()

    # Save to database
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO protocols
            (protocol_id, name, name_normalized, description, created_at_utc, updated_at_utc,
             status, version, approved_by, approved_at_utc, raw_path, normalized_path,
             raw_sha256, normalized_sha256)
            VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                protocol_id,
                name,
                normalize_protocol_name(name),
                description,
                now,
                now,
                version,
                approved_by,
                now if approved_by else None,
                str(raw_dest),
                str(norm_dest),
                raw_sha256,
                normalized_sha256,
            ),
        )

    return protocol_id


def update_protocol(
    db_path: Path,
    protocol_id: str,
    name: str | None = None,
    description: str | None = None,
    status: str | None = None,
    version: str | None = None,
    approved_by: str | None = None,
) -> bool:
    """Update protocol metadata. Returns True if updated."""
    now = utc_now_iso()

    updates = []
    params: list[Any] = []

    if name is not None:
        updates.append("name = ?")
        params.append(name)
        updates.append("name_normalized = ?")
        params.append(normalize_protocol_name(name))

    if description is not None:
        updates.append("description = ?")
        params.append(description)

    if status is not None:
        updates.append("status = ?")
        params.append(status)

    if version is not None:
        updates.append("version = ?")
        params.append(version)

    if approved_by is not None:
        updates.append("approved_by = ?")
        params.append(approved_by)
        updates.append("approved_at_utc = ?")
        params.append(now)

    if not updates:
        return False

    updates.append("updated_at_utc = ?")
    params.append(now)
    params.append(protocol_id)

    with _connect(db_path) as conn:
        result = conn.execute(
            f"UPDATE protocols SET {', '.join(updates)} WHERE protocol_id = ?",
            params,
        )
        return result.rowcount > 0


def delete_protocol(db_path: Path, protocol_id: str) -> bool:
    """Delete a protocol. Returns True if deleted."""
    # Get file paths first
    protocol = get_protocol(db_path, protocol_id)
    if not protocol:
        return False

    # Delete files
    if protocol.raw_path:
        Path(protocol.raw_path).unlink(missing_ok=True)
    if protocol.normalized_path:
        Path(protocol.normalized_path).unlink(missing_ok=True)

    # Delete from database
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM protocols WHERE protocol_id = ?", (protocol_id,))
        # Also delete related validation results
        conn.execute("DELETE FROM validation_results WHERE protocol_id = ?", (protocol_id,))

    return True


# --- Similarity Search ---


def find_similar_protocols(
    db_path: Path,
    procedure_name: str,
    threshold: float = 0.5,
) -> list[tuple[Protocol, float]]:
    """
    Find protocols similar to a procedure name.

    Returns list of (protocol, similarity_score) tuples sorted by similarity.
    """
    normalized = normalize_protocol_name(procedure_name)
    protocols = list_protocols(db_path)

    results = []
    for protocol in protocols:
        similarity = SequenceMatcher(None, normalized, protocol.name_normalized).ratio()
        if similarity >= threshold:
            results.append((protocol, similarity))

    return sorted(results, key=lambda x: x[1], reverse=True)


# --- Protocol Section Parsing ---


def _parse_protocol_sections(text: str) -> dict[str, str]:
    """Parse protocol text into sections."""
    sections: dict[str, str] = {}
    current_section = "general"
    current_content: list[str] = []

    # Common section headers in Danish protocols
    # Note: longer patterns must come first to avoid substring matching issues
    # (e.g., "kontraindikation" contains "indikation")
    section_patterns = [
        "kontraindikation",  # Must be before "indikation"
        "indikation",
        "forberedelse",
        "fremgangsmåde",
        "procedure",
        "udstyr",
        "dosering",
        "komplikation",
        "opfølgning",
        "sikkerhed",
        "observation",
        "monitorering",
        "behandling",
    ]

    for line in text.splitlines():
        line_lower = line.lower().strip()

        # Check if line is a section header
        is_header = False
        for pattern in section_patterns:
            if line_lower.startswith(pattern) or pattern in line_lower[:30]:
                # Save previous section
                if current_content:
                    sections[current_section] = "\n".join(current_content).strip()

                current_section = pattern
                current_content = []
                is_header = True
                break

        if not is_header:
            current_content.append(line)

    # Save last section
    if current_content:
        sections[current_section] = "\n".join(current_content).strip()

    return sections


def _find_matching_section(run_section: str, protocol_sections: dict[str, str]) -> str | None:
    """Find matching protocol section for a run section."""
    run_lower = run_section.lower()

    # Sort keys by length descending to match longer/more specific patterns first
    # This prevents "indikation" from matching "kontraindikationer"
    sorted_keys = sorted(protocol_sections.keys(), key=len, reverse=True)

    # Direct match - check longer keys first
    for key in sorted_keys:
        if key in run_lower or run_lower in key:
            return protocol_sections[key]

    # Mapping common variations
    mappings = {
        "indikationer": ["indikation"],
        "kontraindikationer": ["kontraindikation"],
        "fremgangsmåde": ["procedure", "fremgangsmåde", "dosering", "behandling"],
        "sikkerhedsboks": ["sikkerhed"],
        "komplikationer": ["komplikation"],
        "behandling": ["behandling", "dosering"],
        "disposition": ["opfølgning", "monitorering", "observation"],
    }

    for run_key, protocol_keys in mappings.items():
        if run_key in run_lower:
            for pk in protocol_keys:
                if pk in protocol_sections:
                    return protocol_sections[pk]

    return None


# --- Conflict Detection ---


def _detect_dosing_conflicts(
    section: str,
    run_content: str,
    protocol_content: str,
) -> list[ConflictItem]:
    """Detect dosing-related conflicts."""
    conflicts: list[ConflictItem] = []

    # Pattern for doses: number + unit
    dose_pattern = r"(\d+(?:[.,]\d+)?)\s*(mg|ml|mcg|µg|g|ie|enheder|mmol|l|ml)"

    run_doses = re.findall(dose_pattern, run_content.lower())
    protocol_doses = re.findall(dose_pattern, protocol_content.lower())

    # Normalize decimal separators
    def normalize_dose(d: tuple[str, str]) -> str:
        return f"{d[0].replace(',', '.')} {d[1]}"

    run_dose_strs = {normalize_dose(d) for d in run_doses}
    protocol_dose_strs = {normalize_dose(d) for d in protocol_doses}

    # Doses in run but not in protocol
    for dose in run_dose_strs - protocol_dose_strs:
        conflicts.append(
            ConflictItem(
                section=section,
                conflict_type="dosing",
                generated_text=f"Dose: {dose}",
                approved_text=f"Protocol doses: {', '.join(protocol_dose_strs) or 'none found'}",
                severity="critical",
                explanation=f"Generated procedure mentions {dose} which is not in the approved protocol.",
            )
        )

    return conflicts


def _detect_timing_conflicts(
    section: str,
    run_content: str,
    protocol_content: str,
) -> list[ConflictItem]:
    """Detect timing-related conflicts."""
    conflicts: list[ConflictItem] = []

    # Pattern for times: number + time unit
    time_pattern = r"(\d+(?:[.,]\d+)?)\s*(min|minut|minutter|sek|sekund|sekunder|time|timer|dag|dage)"

    run_times = re.findall(time_pattern, run_content.lower())
    protocol_times = re.findall(time_pattern, protocol_content.lower())

    def normalize_time(t: tuple[str, str]) -> str:
        return f"{t[0].replace(',', '.')} {t[1]}"

    run_time_strs = {normalize_time(t) for t in run_times}
    protocol_time_strs = {normalize_time(t) for t in protocol_times}

    for time_str in run_time_strs - protocol_time_strs:
        conflicts.append(
            ConflictItem(
                section=section,
                conflict_type="timing",
                generated_text=f"Timing: {time_str}",
                approved_text=f"Protocol timings: {', '.join(protocol_time_strs) or 'none found'}",
                severity="warning",
                explanation=f"Generated procedure mentions {time_str} which differs from approved protocol.",
            )
        )

    return conflicts


def _detect_conflicts(
    section: str,
    run_content: str,
    protocol_content: str,
) -> list[ConflictItem]:
    """Detect all types of conflicts between run and protocol content."""
    conflicts: list[ConflictItem] = []

    # Dosing conflict detection
    conflicts.extend(_detect_dosing_conflicts(section, run_content, protocol_content))

    # Timing conflict detection
    conflicts.extend(_detect_timing_conflicts(section, run_content, protocol_content))

    return conflicts


def _parse_markdown_sections(md_text: str) -> dict[str, str]:
    """Parse markdown into sections by headers."""
    sections: dict[str, str] = {}
    current_section = "preamble"
    current_content: list[str] = []

    for line in md_text.splitlines():
        if line.startswith("#"):
            # Save previous section
            if current_content:
                sections[current_section] = "\n".join(current_content).strip()

            # Extract section name (remove # and markdown formatting)
            section_name = line.lstrip("#").strip()
            current_section = section_name
            current_content = []
        else:
            current_content.append(line)

    # Save last section
    if current_content:
        sections[current_section] = "\n".join(current_content).strip()

    return sections


# --- Validation ---


def validate_run_against_protocol(
    run_markdown: str,
    protocol_text: str,
    protocol_id: str,
    protocol_name: str,
) -> ValidationResult:
    """
    Validate generated procedure against an approved protocol.

    Performs:
    1. Section-by-section comparison
    2. Keyword-based conflict detection (dosing, timing, etc.)
    3. Overall similarity scoring
    """
    # Parse sections
    run_sections = _parse_markdown_sections(run_markdown)
    protocol_sections = _parse_protocol_sections(protocol_text)

    conflicts: list[ConflictItem] = []
    sections_compared = 0
    sections_matched = 0

    # Compare each section
    for section_name, run_content in run_sections.items():
        if section_name == "preamble":
            continue

        sections_compared += 1

        # Find matching protocol section
        protocol_content = _find_matching_section(section_name, protocol_sections)

        if protocol_content:
            similarity = SequenceMatcher(None, run_content, protocol_content).ratio()
            if similarity >= 0.7:
                sections_matched += 1
            else:
                # Check for specific conflicts
                section_conflicts = _detect_conflicts(section_name, run_content, protocol_content)
                conflicts.extend(section_conflicts)

    # Calculate overall similarity
    similarity_score = sections_matched / sections_compared if sections_compared > 0 else 0.0

    return ValidationResult(
        protocol_id=protocol_id,
        protocol_name=protocol_name,
        similarity_score=similarity_score,
        conflicts=conflicts,
        sections_compared=sections_compared,
        sections_matched=sections_matched,
    )


# --- Validation Result Storage ---


def save_validation_result(
    db_path: Path,
    run_id: str,
    result: ValidationResult,
) -> str:
    """Save validation result to database. Returns validation_id."""
    validation_id = str(uuid.uuid4())[:8]
    now = utc_now_iso()

    result_json = json.dumps(
        {
            "protocol_name": result.protocol_name,
            "similarity_score": result.similarity_score,
            "sections_compared": result.sections_compared,
            "sections_matched": result.sections_matched,
            "conflicts": [
                {
                    "section": c.section,
                    "conflict_type": c.conflict_type,
                    "generated_text": c.generated_text,
                    "approved_text": c.approved_text,
                    "severity": c.severity,
                    "explanation": c.explanation,
                }
                for c in result.conflicts
            ],
        },
        ensure_ascii=False,
    )

    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO validation_results
            (validation_id, run_id, protocol_id, created_at_utc, similarity_score, conflict_count, result_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                validation_id,
                run_id,
                result.protocol_id,
                now,
                result.similarity_score,
                len(result.conflicts),
                result_json,
            ),
        )

    return validation_id


def get_validation_results(db_path: Path, run_id: str) -> list[dict[str, Any]]:
    """Get all validation results for a run."""
    with _connect(db_path) as conn:
        cursor = conn.execute(
            """
            SELECT v.*, p.name as protocol_name
            FROM validation_results v
            LEFT JOIN protocols p ON v.protocol_id = p.protocol_id
            WHERE v.run_id = ?
            ORDER BY v.created_at_utc DESC
            """,
            (run_id,),
        )
        rows = cursor.fetchall()

    return [
        {
            "validation_id": row["validation_id"],
            "protocol_id": row["protocol_id"],
            "protocol_name": row["protocol_name"] or "Unknown",
            "similarity_score": row["similarity_score"],
            "conflict_count": row["conflict_count"],
            "created_at_utc": row["created_at_utc"],
            "details": json.loads(row["result_json"]),
        }
        for row in rows
    ]


def delete_validation_result(db_path: Path, validation_id: str) -> bool:
    """Delete a validation result. Returns True if deleted."""
    with _connect(db_path) as conn:
        result = conn.execute(
            "DELETE FROM validation_results WHERE validation_id = ?",
            (validation_id,),
        )
        return result.rowcount > 0


# --- LLM-Based Validation ---


def _extract_json_from_llm_response(response_text: str) -> dict[str, Any] | None:
    """
    Robustly extract JSON from LLM response.

    Handles:
    - Pure JSON responses
    - JSON wrapped in markdown code blocks (```json ... ```)
    - JSON embedded in explanatory text
    - Multiple JSON objects (takes first valid one)

    Returns None if no valid JSON found.
    """
    text = response_text.strip()

    # Strategy 1: Try parsing as pure JSON first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strategy 2: Extract from markdown code block
    code_block_pattern = r"```(?:json)?\s*\n?(.*?)\n?```"
    matches = re.findall(code_block_pattern, text, re.DOTALL)
    for match in matches:
        try:
            return json.loads(match.strip())
        except json.JSONDecodeError:
            continue

    # Strategy 3: Find JSON object boundaries (first { to matching })
    first_brace = text.find("{")
    if first_brace != -1:
        # Count braces to find matching closing brace
        depth = 0
        in_string = False
        escape_next = False
        for i, char in enumerate(text[first_brace:], start=first_brace):
            if escape_next:
                escape_next = False
                continue
            if char == "\\":
                escape_next = True
                continue
            if char == '"' and not escape_next:
                in_string = not in_string
                continue
            if in_string:
                continue
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    json_str = text[first_brace : i + 1]
                    try:
                        return json.loads(json_str)
                    except json.JSONDecodeError:
                        break  # Found balanced braces but invalid JSON

    # Log the failed response for debugging
    logger.warning(
        "Failed to extract JSON from LLM response (first 500 chars): %s",
        text[:500],
    )
    return None


_LLM_VALIDATION_PROMPT = """You are a medical protocol validator. Compare a generated procedure against an approved hospital protocol and identify clinically significant conflicts.

APPROVED PROTOCOL:
{protocol_text}

GENERATED PROCEDURE:
{procedure_text}

Analyze for conflicts in:
1. DOSING - Different doses for the same medication/situation
2. TIMING - Different intervals, durations, or sequences
3. CONTRAINDICATIONS - Generated procedure allows what protocol forbids
4. OMISSIONS - Critical steps in protocol missing from generated
5. ADDITIONS - Generated adds interventions protocol doesn't support

For each conflict found, assess severity:
- critical: Could cause patient harm (wrong dose, missed contraindication)
- warning: Deviation that should be reviewed (different timing, alternative drug)
- info: Minor difference, likely acceptable variation

Return ONLY valid JSON (no markdown, no explanation outside JSON):
{{
  "has_conflicts": boolean,
  "compatibility_score": integer 0-100,
  "summary": "1-2 sentence overall assessment in Danish",
  "conflicts": [
    {{
      "type": "dosing|timing|contraindication|omission|addition",
      "severity": "critical|warning|info",
      "section": "which section of procedure this relates to",
      "explanation": "clinical reasoning in Danish for why this is a conflict",
      "generated_text": "relevant excerpt from generated procedure",
      "approved_text": "relevant excerpt from approved protocol"
    }}
  ]
}}

IMPORTANT:
- Only flag genuine clinical conflicts
- Equivalent medications, acceptable dose ranges, and stylistic differences are NOT conflicts
- If procedures are compatible, return empty conflicts array and high compatibility_score
- Write summary and explanations in Danish"""


async def validate_run_against_protocol_llm(
    run_markdown: str,
    protocol_text: str,
    protocol_id: str,
    protocol_name: str,
    anthropic_client: Any,  # anthropic.AsyncAnthropic
) -> ValidationResult:
    """
    Validate generated procedure against protocol using LLM semantic comparison.

    Returns ValidationResult with LLM-assessed conflicts and compatibility score.
    """
    import anthropic

    # Truncate if too long (keep under 8000 chars each to stay within context)
    max_chars = 8000
    if len(protocol_text) > max_chars:
        protocol_text = protocol_text[:max_chars] + "\n\n[... tekst afkortet ...]"
    if len(run_markdown) > max_chars:
        run_markdown = run_markdown[:max_chars] + "\n\n[... tekst afkortet ...]"

    prompt = _LLM_VALIDATION_PROMPT.format(
        protocol_text=protocol_text,
        procedure_text=run_markdown,
    )

    # Call Claude Haiku
    input_tokens = 0
    output_tokens = 0

    try:
        response = await anthropic_client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )

        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens

        # Parse response using robust JSON extraction
        response_text = response.content[0].text.strip()
        result_data = _extract_json_from_llm_response(response_text)

        if result_data is None:
            # Log the full response for debugging
            logger.error(
                "Protocol validation failed to parse LLM response for %s. "
                "Full response:\n%s",
                protocol_id,
                response_text,
            )
            return ValidationResult(
                protocol_id=protocol_id,
                protocol_name=protocol_name,
                similarity_score=0.0,
                conflicts=[],
                sections_compared=0,
                sections_matched=0,
                compatibility_score=None,
                summary="Validering fejlede - kunne ikke parse LLM-svar. Se server log for detaljer.",
                validation_cost_usd=_calculate_haiku_cost(input_tokens, output_tokens),
            )
    except anthropic.APIError as e:
        return ValidationResult(
            protocol_id=protocol_id,
            protocol_name=protocol_name,
            similarity_score=0.0,
            conflicts=[],
            sections_compared=0,
            sections_matched=0,
            compatibility_score=None,
            summary=f"Validering fejlede - API fejl: {str(e)[:100]}",
            validation_cost_usd=_calculate_haiku_cost(input_tokens, output_tokens),
        )

    # Convert LLM conflicts to ConflictItem
    conflicts = []
    for c in result_data.get("conflicts", []):
        conflicts.append(
            ConflictItem(
                section=c.get("section", "ukendt"),
                conflict_type=c.get("type", "unknown"),
                generated_text=c.get("generated_text", ""),
                approved_text=c.get("approved_text", ""),
                severity=c.get("severity", "info"),
                explanation=c.get("explanation", ""),
            )
        )

    return ValidationResult(
        protocol_id=protocol_id,
        protocol_name=protocol_name,
        similarity_score=result_data.get("compatibility_score", 0) / 100.0,
        conflicts=conflicts,
        sections_compared=1,  # LLM compares entire document
        sections_matched=1 if result_data.get("compatibility_score", 0) >= 70 else 0,
        compatibility_score=result_data.get("compatibility_score", 0),
        summary=result_data.get("summary", ""),
        validation_cost_usd=_calculate_haiku_cost(input_tokens, output_tokens),
    )


def _calculate_haiku_cost(input_tokens: int, output_tokens: int) -> float:
    """Calculate cost for Claude Haiku API call."""
    # Haiku pricing: $0.25/MTok input, $1.25/MTok output
    input_cost = (input_tokens / 1_000_000) * 0.25
    output_cost = (output_tokens / 1_000_000) * 1.25
    return input_cost + output_cost

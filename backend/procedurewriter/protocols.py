"""
Hospital protocol management and validation.

Handles:
- Protocol CRUD operations
- Text extraction from PDF/DOCX
- Similarity search
- Conflict detection between generated procedures and approved protocols
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import sqlite3
import uuid
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from procedurewriter.db import utc_now_iso


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
    similarity_score: float
    conflicts: list[ConflictItem]
    sections_compared: int
    sections_matched: int


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
        try:
            normalized_text = Path(row["normalized_path"]).read_text(encoding="utf-8")
        except Exception:
            pass

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
    section_patterns = [
        "indikation",
        "kontraindikation",
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

    # Direct match
    for key, content in protocol_sections.items():
        if key in run_lower or run_lower in key:
            return content

    # Mapping common variations
    mappings = {
        "indikationer": ["indikation"],
        "kontraindikationer": ["kontraindikation"],
        "fremgangsmåde": ["procedure", "fremgangsmåde"],
        "sikkerhedsboks": ["sikkerhed"],
        "komplikationer": ["komplikation"],
        "behandling": ["behandling", "dosering"],
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
    if sections_compared > 0:
        similarity_score = sections_matched / sections_compared
    else:
        similarity_score = 0.0

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

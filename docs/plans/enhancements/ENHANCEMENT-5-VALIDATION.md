# Enhancement 5: Procedure Validation Against Existing Hospital Protocols

## Status: NOT STARTED

**Priority**: 5
**Estimated Effort**: 4-5 days
**Dependencies**: Enhancement 3 (Versioning) recommended but not required

---

## SESSION START CHECKLIST

Before implementing ANY part of this enhancement, execute:

```
Skill(superpowers:using-superpowers)
Skill(superpowers:test-driven-development)
Skill(superpowers:verification-before-completion)
```

**REMINDER**: NO DUMMY/MOCK IMPLEMENTATIONS. All code must be production-ready.

---

## Problem Statement

Hospitals have existing approved protocols. Generating new procedures without checking against existing protocols creates risk:

1. New procedure may contradict approved protocol
2. Different dosing, timing, or steps could harm patients
3. No mechanism to detect conflicts before deployment
4. Regulatory compliance requires consistency

**Critical Safety Example:**
- Hospital has approved "Anafylaksi" protocol: Adrenalin 0.5mg IM
- Generated procedure says: Adrenalin 0.3mg IM
- **Contradiction must be caught before deployment**

---

## Solution Overview

Create a protocol library and validation system:

```
Protocol Library
├── Uploaded hospital protocols (PDF/DOCX)
├── Searchable by procedure name
└── Used for pre/post-generation validation

Validation Flow:
1. Pre-generation: "Similar protocols exist: [A, B, C]"
2. Post-generation: "Conflicts detected in: [dosing, steps]"
3. Diff report: Side-by-side comparison
```

Features:
1. **Protocol Library**: Upload and manage approved protocols
2. **Similarity Search**: Find related protocols by name/content
3. **Conflict Detection**: Compare generated vs. approved
4. **Diff Report**: Highlight specific differences

---

## Technical Specification

### Database Changes

#### Schema Addition

```sql
-- Hospital protocol library
CREATE TABLE protocols (
    protocol_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    name_normalized TEXT NOT NULL,  -- Lowercased for matching
    description TEXT,
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    status TEXT DEFAULT 'active',   -- active, archived, draft
    version TEXT,                    -- Protocol version (e.g., "2.1")
    approved_by TEXT,               -- Who approved this protocol
    approved_at_utc TEXT,           -- When approved
    raw_path TEXT,                  -- Original file path
    normalized_path TEXT,           -- Extracted text path
    raw_sha256 TEXT,                -- Audit trail
    normalized_sha256 TEXT,
    meta_json TEXT                  -- Extra metadata (JSON)
);

-- Index for name-based lookup
CREATE INDEX idx_protocols_name ON protocols(name_normalized);

-- Validation results
CREATE TABLE validation_results (
    validation_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    protocol_id TEXT NOT NULL REFERENCES protocols(protocol_id),
    created_at_utc TEXT NOT NULL,
    similarity_score REAL,          -- 0-1 overall similarity
    conflict_count INTEGER,         -- Number of conflicts detected
    result_json TEXT NOT NULL       -- Full validation result
);

-- Index for run lookups
CREATE INDEX idx_validation_run ON validation_results(run_id);
```

#### Migration Script (`backend/scripts/migrate_protocols.py`)

```python
"""
Database migration for protocol validation system.
"""
import sqlite3
from pathlib import Path

def migrate(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)

    # Create protocols table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS protocols (
            protocol_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            name_normalized TEXT NOT NULL,
            description TEXT,
            created_at_utc TEXT NOT NULL,
            updated_at_utc TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            version TEXT,
            approved_by TEXT,
            approved_at_utc TEXT,
            raw_path TEXT,
            normalized_path TEXT,
            raw_sha256 TEXT,
            normalized_sha256 TEXT,
            meta_json TEXT
        )
    """)

    # Create validation_results table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS validation_results (
            validation_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            protocol_id TEXT NOT NULL,
            created_at_utc TEXT NOT NULL,
            similarity_score REAL,
            conflict_count INTEGER,
            result_json TEXT NOT NULL
        )
    """)

    # Create indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_protocols_name ON protocols(name_normalized)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_validation_run ON validation_results(run_id)")

    conn.commit()
    conn.close()
    print("Migration complete")

if __name__ == "__main__":
    import sys
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/index/runs.sqlite3")
    migrate(db_path)
```

### Backend Changes

#### File: `backend/procedurewriter/protocols.py` (NEW)

```python
"""
Hospital protocol management and validation.

NO MOCKS - All operations use real files and database.
"""
from dataclasses import dataclass
from pathlib import Path
import sqlite3
import json
import hashlib
from datetime import datetime
from typing import Any
from difflib import SequenceMatcher

from procedurewriter.pipeline.normalize import extract_text_from_pdf, extract_text_from_docx

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
    normalized_text: str | None  # Loaded on demand
    raw_sha256: str | None
    created_at_utc: str

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

def normalize_name(name: str) -> str:
    """Normalize protocol/procedure name for matching."""
    return name.lower().strip()

def list_protocols(db_path: Path, status: str | None = "active") -> list[Protocol]:
    """List all protocols, optionally filtered by status."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    if status:
        cursor = conn.execute(
            "SELECT * FROM protocols WHERE status = ? ORDER BY name",
            (status,),
        )
    else:
        cursor = conn.execute("SELECT * FROM protocols ORDER BY name")

    rows = cursor.fetchall()
    conn.close()

    return [
        Protocol(
            protocol_id=row["protocol_id"],
            name=row["name"],
            name_normalized=row["name_normalized"],
            description=row["description"],
            status=row["status"],
            version=row["version"],
            approved_by=row["approved_by"],
            approved_at_utc=row["approved_at_utc"],
            raw_path=row["raw_path"],
            normalized_text=None,  # Load on demand
            raw_sha256=row["raw_sha256"],
            created_at_utc=row["created_at_utc"],
        )
        for row in rows
    ]

def get_protocol(db_path: Path, protocol_id: str, load_text: bool = False) -> Protocol | None:
    """Get a specific protocol."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        "SELECT * FROM protocols WHERE protocol_id = ?",
        (protocol_id,),
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    normalized_text = None
    if load_text and row["normalized_path"]:
        try:
            normalized_text = Path(row["normalized_path"]).read_text()
        except Exception:
            pass

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
        normalized_text=normalized_text,
        raw_sha256=row["raw_sha256"],
        created_at_utc=row["created_at_utc"],
    )

def find_similar_protocols(
    db_path: Path,
    procedure_name: str,
    threshold: float = 0.5,
) -> list[tuple[Protocol, float]]:
    """
    Find protocols similar to a procedure name.

    Returns list of (protocol, similarity_score) tuples.
    """
    normalized = normalize_name(procedure_name)
    protocols = list_protocols(db_path)

    results = []
    for protocol in protocols:
        similarity = SequenceMatcher(None, normalized, protocol.name_normalized).ratio()
        if similarity >= threshold:
            results.append((protocol, similarity))

    return sorted(results, key=lambda x: x[1], reverse=True)

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
    import uuid
    import shutil

    protocol_id = str(uuid.uuid4())[:8]
    now = datetime.utcnow().isoformat() + "Z"

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
    if suffix == ".pdf":
        text = extract_text_from_pdf(raw_dest)
    elif suffix in (".docx", ".doc"):
        text = extract_text_from_docx(raw_dest)
    else:
        text = file_path.read_text()

    # Save normalized text
    norm_dest = storage_dir / f"{protocol_id}_normalized.txt"
    norm_dest.write_text(text)
    normalized_sha256 = hashlib.sha256(text.encode()).hexdigest()

    # Save to database
    conn = sqlite3.connect(db_path)
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
            normalize_name(name),
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
    conn.commit()
    conn.close()

    return protocol_id

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
    from procedurewriter.pipeline.versioning import parse_markdown_sections

    # Parse sections
    run_sections = parse_markdown_sections(run_markdown)
    protocol_sections = _parse_protocol_sections(protocol_text)

    conflicts: list[ConflictItem] = []
    sections_compared = 0
    sections_matched = 0

    # Compare each section
    for section_name, run_content in run_sections.items():
        if section_name in ("preamble",):
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
                section_conflicts = _detect_conflicts(
                    section_name, run_content, protocol_content
                )
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

def _parse_protocol_sections(text: str) -> dict[str, str]:
    """Parse protocol text into sections."""
    sections: dict[str, str] = {}
    current_section = "general"
    current_content: list[str] = []

    # Common section headers in Danish protocols
    section_patterns = [
        "indikation", "kontraindikation", "forberedelse", "fremgangsmåde",
        "procedure", "udstyr", "dosering", "komplikation", "opfølgning",
        "sikkerhed", "observation", "monitorering",
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
    }

    for run_key, protocol_keys in mappings.items():
        if run_key in run_lower:
            for pk in protocol_keys:
                if pk in protocol_sections:
                    return protocol_sections[pk]

    return None

def _detect_conflicts(
    section: str,
    run_content: str,
    protocol_content: str,
) -> list[ConflictItem]:
    """Detect specific conflicts between run and protocol content."""
    conflicts: list[ConflictItem] = []

    # Dosing conflict detection
    dosing_conflicts = _detect_dosing_conflicts(section, run_content, protocol_content)
    conflicts.extend(dosing_conflicts)

    # Timing conflict detection
    timing_conflicts = _detect_timing_conflicts(section, run_content, protocol_content)
    conflicts.extend(timing_conflicts)

    return conflicts

def _detect_dosing_conflicts(
    section: str,
    run_content: str,
    protocol_content: str,
) -> list[ConflictItem]:
    """Detect dosing-related conflicts."""
    import re

    conflicts: list[ConflictItem] = []

    # Pattern for doses: number + unit
    dose_pattern = r"(\d+(?:\.\d+)?)\s*(mg|ml|mcg|g|ie|enheder|mmol)"

    run_doses = re.findall(dose_pattern, run_content.lower())
    protocol_doses = re.findall(dose_pattern, protocol_content.lower())

    # Simple comparison - look for mismatched doses
    run_dose_strs = {f"{d[0]} {d[1]}" for d in run_doses}
    protocol_dose_strs = {f"{d[0]} {d[1]}" for d in protocol_doses}

    # Doses in run but not in protocol
    for dose in run_dose_strs - protocol_dose_strs:
        conflicts.append(ConflictItem(
            section=section,
            conflict_type="dosing",
            generated_text=f"Dose: {dose}",
            approved_text=f"Protocol doses: {', '.join(protocol_dose_strs) or 'none found'}",
            severity="critical",
            explanation=f"Generated procedure mentions {dose} which is not in the approved protocol.",
        ))

    return conflicts

def _detect_timing_conflicts(
    section: str,
    run_content: str,
    protocol_content: str,
) -> list[ConflictItem]:
    """Detect timing-related conflicts."""
    import re

    conflicts: list[ConflictItem] = []

    # Pattern for times: number + time unit
    time_pattern = r"(\d+(?:\.\d+)?)\s*(min|minut|sek|sekund|time|timer|dag|dage)"

    run_times = re.findall(time_pattern, run_content.lower())
    protocol_times = re.findall(time_pattern, protocol_content.lower())

    run_time_strs = {f"{t[0]} {t[1]}" for t in run_times}
    protocol_time_strs = {f"{t[0]} {t[1]}" for t in protocol_times}

    for time in run_time_strs - protocol_time_strs:
        conflicts.append(ConflictItem(
            section=section,
            conflict_type="timing",
            generated_text=f"Timing: {time}",
            approved_text=f"Protocol timings: {', '.join(protocol_time_strs) or 'none found'}",
            severity="warning",
            explanation=f"Generated procedure mentions {time} which differs from approved protocol.",
        ))

    return conflicts

def save_validation_result(
    db_path: Path,
    run_id: str,
    result: ValidationResult,
) -> str:
    """Save validation result to database."""
    import uuid

    validation_id = str(uuid.uuid4())[:8]
    now = datetime.utcnow().isoformat() + "Z"

    result_json = json.dumps({
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
    })

    conn = sqlite3.connect(db_path)
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
    conn.commit()
    conn.close()

    return validation_id

def get_validation_results(db_path: Path, run_id: str) -> list[dict[str, Any]]:
    """Get all validation results for a run."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        """
        SELECT v.*, p.name as protocol_name
        FROM validation_results v
        JOIN protocols p ON v.protocol_id = p.protocol_id
        WHERE v.run_id = ?
        """,
        (run_id,),
    )
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "validation_id": row["validation_id"],
            "protocol_id": row["protocol_id"],
            "protocol_name": row["protocol_name"],
            "similarity_score": row["similarity_score"],
            "conflict_count": row["conflict_count"],
            "details": json.loads(row["result_json"]),
        }
        for row in rows
    ]
```

#### File: `backend/procedurewriter/main.py` (MODIFY)

Add protocol endpoints:

```python
from procedurewriter.protocols import (
    list_protocols,
    get_protocol,
    upload_protocol,
    find_similar_protocols,
    validate_run_against_protocol,
    save_validation_result,
    get_validation_results,
)

# --- Protocol Endpoints ---

@app.get("/api/protocols")
def api_list_protocols(status: str = "active") -> dict:
    """List all protocols."""
    protocols = list_protocols(settings.db_path, status if status != "all" else None)
    return {
        "protocols": [
            {
                "protocol_id": p.protocol_id,
                "name": p.name,
                "description": p.description,
                "status": p.status,
                "version": p.version,
                "approved_by": p.approved_by,
                "created_at_utc": p.created_at_utc,
            }
            for p in protocols
        ]
    }

@app.get("/api/protocols/{protocol_id}")
def api_get_protocol(protocol_id: str) -> dict:
    """Get a specific protocol."""
    protocol = get_protocol(settings.db_path, protocol_id, load_text=True)
    if not protocol:
        raise HTTPException(404, "Protocol not found")

    return {
        "protocol_id": protocol.protocol_id,
        "name": protocol.name,
        "description": protocol.description,
        "status": protocol.status,
        "version": protocol.version,
        "approved_by": protocol.approved_by,
        "approved_at_utc": protocol.approved_at_utc,
        "created_at_utc": protocol.created_at_utc,
        "has_text": protocol.normalized_text is not None,
    }

@app.post("/api/protocols/upload")
async def api_upload_protocol(
    file: UploadFile,
    name: str = Form(...),
    description: str = Form(None),
    version: str = Form(None),
    approved_by: str = Form(None),
) -> dict:
    """Upload a new protocol."""
    # Save uploaded file
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in (".pdf", ".docx", ".doc", ".txt"):
        raise HTTPException(400, "Unsupported file type")

    upload_dir = Path("data/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    temp_path = upload_dir / f"temp_{file.filename}"

    with open(temp_path, "wb") as f:
        content = await file.read()
        f.write(content)

    try:
        protocol_id = upload_protocol(
            settings.db_path,
            temp_path,
            name=name,
            description=description,
            version=version,
            approved_by=approved_by,
        )
    finally:
        temp_path.unlink(missing_ok=True)

    return {"protocol_id": protocol_id}

@app.get("/api/protocols/search")
def api_search_protocols(q: str, threshold: float = 0.5) -> dict:
    """Search for similar protocols."""
    results = find_similar_protocols(settings.db_path, q, threshold)
    return {
        "query": q,
        "results": [
            {
                "protocol_id": p.protocol_id,
                "name": p.name,
                "similarity": score,
            }
            for p, score in results
        ]
    }

@app.post("/api/runs/{run_id}/validate")
def api_validate_run(run_id: str, protocol_id: str | None = None) -> dict:
    """
    Validate a run against protocols.

    If protocol_id is provided, validates against that protocol.
    Otherwise, finds similar protocols automatically.
    """
    run = get_run(settings.db_path, run_id)
    if not run:
        raise HTTPException(404, "Run not found")

    run_md = Path(run.run_dir) / "procedure.md"
    if not run_md.exists():
        raise HTTPException(400, "Run has no procedure output")

    run_markdown = run_md.read_text()

    # Find protocols to validate against
    if protocol_id:
        protocols = [(get_protocol(settings.db_path, protocol_id, load_text=True), 1.0)]
        if protocols[0][0] is None:
            raise HTTPException(404, "Protocol not found")
    else:
        protocols = find_similar_protocols(settings.db_path, run.procedure)
        # Load text for each
        protocols = [
            (get_protocol(settings.db_path, p.protocol_id, load_text=True), score)
            for p, score in protocols[:5]  # Limit to top 5
        ]

    results = []
    for protocol, name_similarity in protocols:
        if not protocol or not protocol.normalized_text:
            continue

        result = validate_run_against_protocol(
            run_markdown=run_markdown,
            protocol_text=protocol.normalized_text,
            protocol_id=protocol.protocol_id,
            protocol_name=protocol.name,
        )

        validation_id = save_validation_result(settings.db_path, run_id, result)

        results.append({
            "validation_id": validation_id,
            "protocol_id": protocol.protocol_id,
            "protocol_name": protocol.name,
            "name_similarity": name_similarity,
            "content_similarity": result.similarity_score,
            "conflict_count": len(result.conflicts),
            "conflicts": [
                {
                    "section": c.section,
                    "type": c.conflict_type,
                    "severity": c.severity,
                    "explanation": c.explanation,
                }
                for c in result.conflicts
            ],
        })

    return {"run_id": run_id, "validations": results}

@app.get("/api/runs/{run_id}/validations")
def api_get_validations(run_id: str) -> dict:
    """Get validation results for a run."""
    results = get_validation_results(settings.db_path, run_id)
    return {"run_id": run_id, "validations": results}
```

### Frontend Changes

#### File: `frontend/src/pages/ProtocolsPage.tsx` (NEW)

```typescript
import { useEffect, useState, useRef } from "react";

interface Protocol {
  protocol_id: string;
  name: string;
  description: string | null;
  status: string;
  version: string | null;
  approved_by: string | null;
  created_at_utc: string;
}

export default function ProtocolsPage() {
  const [protocols, setProtocols] = useState<Protocol[]>([]);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Upload form state
  const [uploadName, setUploadName] = useState("");
  const [uploadDescription, setUploadDescription] = useState("");
  const [uploadVersion, setUploadVersion] = useState("");
  const [uploadApprovedBy, setUploadApprovedBy] = useState("");
  const [uploading, setUploading] = useState(false);

  async function loadProtocols() {
    try {
      const r = await fetch("/api/protocols");
      const data = await r.json();
      setProtocols(data.protocols);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  useEffect(() => {
    void loadProtocols();
  }, []);

  async function handleUpload() {
    const file = fileInputRef.current?.files?.[0];
    if (!file || !uploadName) {
      setError("Please select a file and enter a name");
      return;
    }

    setUploading(true);
    setError(null);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("name", uploadName);
    if (uploadDescription) formData.append("description", uploadDescription);
    if (uploadVersion) formData.append("version", uploadVersion);
    if (uploadApprovedBy) formData.append("approved_by", uploadApprovedBy);

    try {
      const r = await fetch("/api/protocols/upload", {
        method: "POST",
        body: formData,
      });

      if (!r.ok) {
        const data = await r.json();
        throw new Error(data.detail || "Upload failed");
      }

      // Reset form
      setUploadName("");
      setUploadDescription("");
      setUploadVersion("");
      setUploadApprovedBy("");
      if (fileInputRef.current) fileInputRef.current.value = "";

      await loadProtocols();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="split">
      <div className="card">
        <h2>Protokol-bibliotek</h2>
        <p className="muted">
          Upload godkendte hospitalsprotkoller for validering mod genererede procedurer.
        </p>

        {error && <p className="error">{error}</p>}

        <div className="protocol-list">
          {protocols.length === 0 ? (
            <p className="muted">Ingen protokoller endnu.</p>
          ) : (
            protocols.map(p => (
              <div key={p.protocol_id} className="protocol-item">
                <div className="protocol-header">
                  <strong>{p.name}</strong>
                  {p.version && <span className="badge">v{p.version}</span>}
                  <span className={`status-badge status-${p.status}`}>{p.status}</span>
                </div>
                {p.description && <p className="muted">{p.description}</p>}
                <div className="protocol-meta muted">
                  {p.approved_by && <span>Godkendt af: {p.approved_by}</span>}
                  <span>{p.created_at_utc}</span>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      <div className="card">
        <h2>Upload protokol</h2>

        <div className="form-group">
          <label>Fil (PDF eller DOCX)</label>
          <input type="file" ref={fileInputRef} accept=".pdf,.docx,.doc,.txt" />
        </div>

        <div className="form-group">
          <label>Protokol-navn *</label>
          <input
            value={uploadName}
            onChange={e => setUploadName(e.target.value)}
            placeholder="Fx: Akut anafylaksi behandling"
          />
        </div>

        <div className="form-group">
          <label>Beskrivelse</label>
          <textarea
            value={uploadDescription}
            onChange={e => setUploadDescription(e.target.value)}
            rows={2}
          />
        </div>

        <div className="row">
          <div className="form-group" style={{ flex: 1 }}>
            <label>Version</label>
            <input
              value={uploadVersion}
              onChange={e => setUploadVersion(e.target.value)}
              placeholder="2.0"
            />
          </div>
          <div className="form-group" style={{ flex: 1 }}>
            <label>Godkendt af</label>
            <input
              value={uploadApprovedBy}
              onChange={e => setUploadApprovedBy(e.target.value)}
              placeholder="Navn eller afdeling"
            />
          </div>
        </div>

        <button onClick={handleUpload} disabled={uploading}>
          {uploading ? "Uploader..." : "Upload protokol"}
        </button>
      </div>
    </div>
  );
}
```

#### File: `frontend/src/components/ValidationResults.tsx` (NEW)

```typescript
interface Conflict {
  section: string;
  type: string;
  severity: "critical" | "warning" | "info";
  explanation: string;
}

interface ValidationResult {
  validation_id: string;
  protocol_id: string;
  protocol_name: string;
  name_similarity: number;
  content_similarity: number;
  conflict_count: number;
  conflicts: Conflict[];
}

interface ValidationResultsProps {
  validations: ValidationResult[];
}

export function ValidationResults({ validations }: ValidationResultsProps) {
  if (validations.length === 0) {
    return <p className="muted">Ingen valideringer foretaget.</p>;
  }

  return (
    <div className="validation-results">
      {validations.map(v => (
        <div key={v.validation_id} className="validation-item">
          <div className="validation-header">
            <strong>vs. {v.protocol_name}</strong>
            <span
              className={`similarity-badge ${
                v.content_similarity >= 0.8 ? 'high' :
                v.content_similarity >= 0.5 ? 'medium' : 'low'
              }`}
            >
              {(v.content_similarity * 100).toFixed(0)}% match
            </span>
          </div>

          {v.conflict_count > 0 ? (
            <div className="conflicts">
              <strong className="warning">
                {v.conflict_count} konflikt{v.conflict_count !== 1 ? "er" : ""} fundet
              </strong>
              <ul>
                {v.conflicts.map((c, i) => (
                  <li key={i} className={`conflict conflict-${c.severity}`}>
                    <span className="conflict-type">[{c.type}]</span>
                    <span className="conflict-section">{c.section}:</span>
                    {c.explanation}
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <p className="success">Ingen konflikter fundet</p>
          )}
        </div>
      ))}
    </div>
  );
}
```

#### File: `frontend/src/pages/RunPage.tsx` (MODIFY)

Add validation section:

```typescript
import { ValidationResults } from "../components/ValidationResults";

// Add state
const [validations, setValidations] = useState<ValidationResult[]>([]);
const [validating, setValidating] = useState(false);

// Load existing validations
useEffect(() => {
  if (!runId) return;
  fetch(`/api/runs/${runId}/validations`)
    .then(r => r.json())
    .then(data => setValidations(data.validations))
    .catch(() => {});
}, [runId]);

// Validate function
async function validateAgainstProtocols() {
  if (!runId) return;
  setValidating(true);
  try {
    const r = await fetch(`/api/runs/${runId}/validate`, { method: "POST" });
    const data = await r.json();
    setValidations(data.validations);
  } catch (e) {
    setError(e instanceof Error ? e.message : String(e));
  } finally {
    setValidating(false);
  }
}

// Add to JSX
<div className="card" style={{ marginTop: 20 }}>
  <h3>Protokol-validering</h3>
  {validations.length === 0 ? (
    <div>
      <p className="muted">Ingen validering foretaget.</p>
      <button onClick={validateAgainstProtocols} disabled={validating}>
        {validating ? "Validerer..." : "Valider mod protokoller"}
      </button>
    </div>
  ) : (
    <ValidationResults validations={validations} />
  )}
</div>
```

---

## Test Requirements

### Backend Tests

#### File: `backend/tests/test_protocols.py` (NEW)

```python
"""
Protocol Validation Tests

IMPORTANT: Tests use REAL files and database.
NO MOCKS for file operations or text extraction.
"""
import pytest
from pathlib import Path
import tempfile

from procedurewriter.protocols import (
    normalize_name,
    list_protocols,
    get_protocol,
    upload_protocol,
    find_similar_protocols,
    validate_run_against_protocol,
    _detect_dosing_conflicts,
    _detect_timing_conflicts,
)

@pytest.fixture
def temp_db():
    """Create temporary database with protocols table."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"

        # Run migration
        import subprocess
        subprocess.run([
            "python", "scripts/migrate_protocols.py", str(db_path)
        ], check=True)

        yield db_path, Path(tmpdir)


class TestNameNormalization:
    """Test protocol name normalization."""

    def test_lowercase(self):
        assert normalize_name("Akut Astma") == "akut astma"

    def test_trim(self):
        assert normalize_name("  test  ") == "test"


class TestProtocolUpload:
    """Test protocol upload functionality."""

    def test_upload_text_file(self, temp_db):
        """Can upload a simple text file as protocol."""
        db_path, tmpdir = temp_db

        # Create test file
        test_file = tmpdir / "test_protocol.txt"
        test_file.write_text("""
Protokol: Akut Astma

Indikation:
- Akut astmaanfald
- Åndenød

Behandling:
- Salbutamol 2.5 mg nebulisator
- Prednisolon 37.5 mg p.o.
        """)

        protocol_id = upload_protocol(
            db_path,
            test_file,
            name="Akut Astma",
            description="Test protocol",
            storage_dir=tmpdir / "protocols",
        )

        protocol = get_protocol(db_path, protocol_id, load_text=True)
        assert protocol is not None
        assert protocol.name == "Akut Astma"
        assert protocol.normalized_text is not None
        assert "Salbutamol" in protocol.normalized_text


class TestSimilaritySearch:
    """Test protocol similarity search."""

    def test_find_similar_by_name(self, temp_db):
        """Finds protocols with similar names."""
        db_path, tmpdir = temp_db

        # Upload a protocol
        test_file = tmpdir / "test.txt"
        test_file.write_text("Test protocol content")
        upload_protocol(db_path, test_file, name="Akut Astma Behandling", storage_dir=tmpdir / "protocols")

        # Search
        results = find_similar_protocols(db_path, "akut astma", threshold=0.3)

        assert len(results) > 0
        assert results[0][1] > 0.3  # Similarity score


class TestConflictDetection:
    """Test conflict detection algorithms."""

    def test_detect_dosing_conflict(self):
        """Detects different doses."""
        run = "Administrer adrenalin 0.5 mg intramuskulært."
        protocol = "Giv adrenalin 0.3 mg i.m."

        conflicts = _detect_dosing_conflicts("Behandling", run, protocol)

        # Should detect the dose difference
        assert len(conflicts) > 0
        assert any(c.conflict_type == "dosing" for c in conflicts)

    def test_detect_timing_conflict(self):
        """Detects different timings."""
        run = "Gentag efter 5 minutter."
        protocol = "Gentag efter 10 minutter."

        conflicts = _detect_timing_conflicts("Behandling", run, protocol)

        assert len(conflicts) > 0
        assert any(c.conflict_type == "timing" for c in conflicts)

    def test_no_conflict_when_matching(self):
        """No conflicts when content matches."""
        run = "Administrer adrenalin 0.5 mg."
        protocol = "Giv adrenalin 0.5 mg."

        dosing = _detect_dosing_conflicts("Behandling", run, protocol)

        # Same dose should not trigger conflict
        assert len(dosing) == 0


class TestFullValidation:
    """Test complete validation workflow."""

    def test_validate_matching_content(self):
        """Validation with matching content has high similarity."""
        run_md = """
# Procedure: Akut Astma

## Indikationer
- Akut astmaanfald med åndenød

## Behandling
- Salbutamol 2.5 mg nebulisator
"""

        protocol_text = """
Indikation:
Akut astmaanfald med åndenød

Behandling:
Salbutamol 2.5 mg via nebulisator
"""

        result = validate_run_against_protocol(
            run_md, protocol_text, "P001", "Test Protocol"
        )

        assert result.similarity_score > 0.5
        assert len(result.conflicts) == 0

    def test_validate_conflicting_content(self):
        """Validation detects conflicts in different content."""
        run_md = """
# Procedure: Akut Astma

## Behandling
- Salbutamol 5 mg nebulisator
- Gentag efter 20 minutter
"""

        protocol_text = """
Behandling:
Salbutamol 2.5 mg via nebulisator
Gentag efter 10 minutter
"""

        result = validate_run_against_protocol(
            run_md, protocol_text, "P001", "Test Protocol"
        )

        # Should find dosing and timing conflicts
        assert len(result.conflicts) > 0
```

---

## Implementation Checklist

### Phase 1: Database & Migration (Day 1)

- [ ] Create migration script `backend/scripts/migrate_protocols.py`
- [ ] Add protocols table schema
- [ ] Add validation_results table schema
- [ ] Run migration on dev database
- [ ] Verify tables with SQL queries

### Phase 2: Protocol Management (Day 1-2)

- [ ] Create `backend/procedurewriter/protocols.py`
- [ ] Implement list/get/upload functions
- [ ] Implement find_similar_protocols
- [ ] Implement text extraction integration
- [ ] Write unit tests for CRUD operations
- [ ] Run tests: `pytest backend/tests/test_protocols.py -v`

### Phase 3: Validation Logic (Day 2-3)

- [ ] Implement validate_run_against_protocol
- [ ] Implement _detect_dosing_conflicts
- [ ] Implement _detect_timing_conflicts
- [ ] Implement section parsing for protocols
- [ ] Write validation tests
- [ ] Test with real protocol files

### Phase 4: API Endpoints (Day 3)

- [ ] Add protocol CRUD endpoints
- [ ] Add upload endpoint with file handling
- [ ] Add search endpoint
- [ ] Add validation endpoint
- [ ] Test API with curl

### Phase 5: Frontend - Protocols (Day 4)

- [ ] Create `ProtocolsPage.tsx`
- [ ] Implement upload form
- [ ] Implement protocol list
- [ ] Add routes and navigation

### Phase 6: Frontend - Validation Integration (Day 4-5)

- [ ] Create `ValidationResults.tsx` component
- [ ] Modify `RunPage.tsx` with validation section
- [ ] Add validation trigger button
- [ ] Style conflict display

### Phase 7: Polish (Day 5)

- [ ] Handle PDF/DOCX upload errors gracefully
- [ ] Improve conflict severity classification
- [ ] Run full test suite
- [ ] Manual E2E testing
- [ ] Documentation

---

## Current Status

**Status**: NOT STARTED

**Last Updated**: 2024-12-18

**Checkpoints Completed**:
- [ ] Phase 1: Database & Migration
- [ ] Phase 2: Protocol Management
- [ ] Phase 3: Validation Logic
- [ ] Phase 4: API Endpoints
- [ ] Phase 5: Frontend - Protocols
- [ ] Phase 6: Frontend - Validation Integration
- [ ] Phase 7: Polish

**Blockers**: None

**Notes**: Ready to begin. This is the most complex enhancement due to conflict detection logic.

---

## Session Handoff Notes

When continuing this enhancement in a new session:

1. Read this document first
2. Check "Current Status" above
3. Load skills: `Skill(superpowers:test-driven-development)`
4. Check if migration has been run
5. Run existing tests: `pytest`
6. Continue from last incomplete checkbox

**REMEMBER**: No dummy/mock implementations. All file operations use real PDFs/DOCX files.

**CRITICAL SAFETY NOTE**: This enhancement is about patient safety. Conflict detection MUST be thorough. Missed conflicts could lead to harm.

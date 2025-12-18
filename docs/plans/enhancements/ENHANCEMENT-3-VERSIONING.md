# Enhancement 3: Structured Procedure Versioning & Diff System

## Status: COMPLETED (2024-12-18)

**Priority**: 3
**Estimated Effort**: 2-3 days
**Dependencies**: None

### Implementation Summary

Implemented full versioning and diff system:

**Database (`db.py`)**:
- Added `parent_run_id`, `version_number`, `version_note`, `procedure_normalized` columns
- Auto-migration for existing databases
- `normalize_procedure_name()` for matching versions across runs
- `list_procedure_versions()`, `get_latest_version()`, `list_unique_procedures()`, `get_version_chain()`
- Indexes for efficient version queries

**Versioning Module (`pipeline/versioning.py`)**:
- `parse_markdown_sections()` - parse procedure into sections
- `diff_sections()` - compare sections between versions
- `diff_sources()` - track added/removed sources
- `create_version_diff()` - generate complete diff
- `diff_to_dict()` - JSON serialization for API

**API Endpoints (`main.py`)**:
- `GET /api/procedures` - list all unique procedures
- `GET /api/procedures/{procedure}/versions` - list versions
- `GET /api/runs/{run_id}/version-chain` - get ancestry chain
- `GET /api/runs/{run_id}/diff/{other_run_id}` - generate diff

**Frontend**:
- `VersionHistoryPage.tsx` - browse procedures and versions
- `DiffPage.tsx` - visual diff with section comparison
- Navigation link in Layout
- API types in `api.ts`

**Tests**: 35 tests for versioning module

---

## IMPORTANT: Orchestrator Integration Context

**As of 2024-12-18**, the pipeline uses a multi-agent orchestrator that returns:
- `quality_score`: 1-10 from QualityAgent
- `iterations_used`: Number of quality loop iterations (1-3)
- `total_cost_usd`: Combined cost from all agents

**Versioning considerations**:
- Version diffs should track `iterations_used` (more iterations = more refinement)
- Quality scores can be compared across versions
- Cost tracking per version helps identify expensive regenerations

**No conflicts**: The orchestrator doesn't affect versioning logic - versions are still based on run_id linkage. The orchestrator provides additional metadata to track per version.

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

Currently, each procedure generation creates an independent run:

1. No way to track procedure evolution over time
2. Cannot compare versions to see what changed
3. No audit trail for WHY a procedure was updated
4. Hospitals need version history for regulatory compliance

Example scenario:
- User generates "Akut astma" in January 2024
- Danish guidelines update in March 2024
- User regenerates "Akut astma" in April 2024
- **Need**: Compare versions, see guideline caused change

---

## Solution Overview

Add version tracking and diff capabilities:

```
Procedure: "Akut astma"
├── Version 1 (2024-01-15) - Initial
├── Version 2 (2024-04-20) - Updated per new SST guidelines
│   └── Diff: +3 sources, -1 source, 5 sections changed
└── Version 3 (2024-06-10) - Minor correction
    └── Diff: 1 section changed, same sources
```

Features:
1. **Version Linking**: Connect runs of the same procedure
2. **Structural Diff**: Section-by-section comparison
3. **Source Diff**: Track added/removed/changed sources
4. **Version History UI**: View all versions of a procedure

---

## Technical Specification

### Database Changes

#### File: `backend/procedurewriter/db.py` (MODIFY)

Add version tracking columns:

```python
def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
    -- Add version tracking to runs table
    ALTER TABLE runs ADD COLUMN parent_run_id TEXT REFERENCES runs(run_id);
    ALTER TABLE runs ADD COLUMN version_number INTEGER DEFAULT 1;
    ALTER TABLE runs ADD COLUMN version_note TEXT;
    ALTER TABLE runs ADD COLUMN procedure_normalized TEXT;  -- Lowercased for matching

    -- Index for finding procedure versions
    CREATE INDEX IF NOT EXISTS idx_runs_procedure_normalized
        ON runs(procedure_normalized);

    -- Index for version chains
    CREATE INDEX IF NOT EXISTS idx_runs_parent
        ON runs(parent_run_id);
    """)
```

**Migration Script** (`backend/scripts/migrate_versioning.py`):

```python
"""
Database migration for procedure versioning.

Run this ONCE to add new columns to existing database.
"""
import sqlite3
from pathlib import Path

def migrate(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)

    # Check if columns already exist
    cursor = conn.execute("PRAGMA table_info(runs)")
    columns = {row[1] for row in cursor.fetchall()}

    if "parent_run_id" not in columns:
        conn.execute("ALTER TABLE runs ADD COLUMN parent_run_id TEXT")
        print("Added parent_run_id column")

    if "version_number" not in columns:
        conn.execute("ALTER TABLE runs ADD COLUMN version_number INTEGER DEFAULT 1")
        print("Added version_number column")

    if "version_note" not in columns:
        conn.execute("ALTER TABLE runs ADD COLUMN version_note TEXT")
        print("Added version_note column")

    if "procedure_normalized" not in columns:
        conn.execute("ALTER TABLE runs ADD COLUMN procedure_normalized TEXT")
        # Backfill existing rows
        conn.execute("""
            UPDATE runs
            SET procedure_normalized = LOWER(TRIM(procedure))
            WHERE procedure_normalized IS NULL
        """)
        print("Added and backfilled procedure_normalized column")

    # Create indexes
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_runs_procedure_normalized
        ON runs(procedure_normalized)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_runs_parent
        ON runs(parent_run_id)
    """)

    conn.commit()
    conn.close()
    print("Migration complete")

if __name__ == "__main__":
    import sys
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/index/runs.sqlite3")
    migrate(db_path)
```

### Backend Changes

#### File: `backend/procedurewriter/pipeline/versioning.py` (NEW)

```python
"""
Procedure versioning and diff system.

NO MOCKS - All operations use real database and file system.
"""
from dataclasses import dataclass
from pathlib import Path
from difflib import unified_diff, SequenceMatcher
import json
from typing import Any

from procedurewriter.db import get_run, list_runs_for_procedure

@dataclass
class SectionDiff:
    """Diff for a single section."""
    section_name: str
    change_type: str  # "added", "removed", "modified", "unchanged"
    old_content: str | None
    new_content: str | None
    similarity: float  # 0-1 for modified sections

@dataclass
class SourceDiff:
    """Diff for sources between versions."""
    added: list[str]      # source_ids added
    removed: list[str]    # source_ids removed
    unchanged: list[str]  # source_ids in both

@dataclass
class VersionDiff:
    """Complete diff between two procedure versions."""
    old_run_id: str
    new_run_id: str
    old_version: int
    new_version: int
    section_diffs: list[SectionDiff]
    source_diff: SourceDiff
    overall_similarity: float  # 0-1

def normalize_procedure_name(name: str) -> str:
    """Normalize procedure name for matching."""
    return name.lower().strip()

def find_previous_version(db_path: Path, procedure: str, current_run_id: str) -> str | None:
    """
    Find the most recent successful run of the same procedure.

    Returns run_id of previous version, or None if this is first version.
    """
    normalized = normalize_procedure_name(procedure)

    runs = list_runs_for_procedure(db_path, normalized)

    # Filter to successful runs before current
    previous_runs = [
        r for r in runs
        if r.run_id != current_run_id
        and r.status == "DONE"
    ]

    if not previous_runs:
        return None

    # Return most recent
    return sorted(previous_runs, key=lambda r: r.created_at_utc, reverse=True)[0].run_id

def calculate_next_version_number(db_path: Path, procedure: str) -> int:
    """Calculate the next version number for a procedure."""
    normalized = normalize_procedure_name(procedure)
    runs = list_runs_for_procedure(db_path, normalized)

    if not runs:
        return 1

    max_version = max(r.version_number or 1 for r in runs)
    return max_version + 1

def parse_markdown_sections(markdown: str) -> dict[str, str]:
    """Parse markdown into sections by heading."""
    sections: dict[str, str] = {}
    current_section = "preamble"
    current_content: list[str] = []

    for line in markdown.splitlines():
        if line.startswith("## "):
            # Save previous section
            if current_content:
                sections[current_section] = "\n".join(current_content).strip()
            # Start new section
            current_section = line[3:].strip()
            current_content = []
        else:
            current_content.append(line)

    # Save last section
    if current_content:
        sections[current_section] = "\n".join(current_content).strip()

    return sections

def diff_sections(old_sections: dict[str, str], new_sections: dict[str, str]) -> list[SectionDiff]:
    """Calculate section-by-section diff."""
    diffs: list[SectionDiff] = []

    all_sections = set(old_sections.keys()) | set(new_sections.keys())

    for section in sorted(all_sections):
        old_content = old_sections.get(section)
        new_content = new_sections.get(section)

        if old_content is None:
            diffs.append(SectionDiff(
                section_name=section,
                change_type="added",
                old_content=None,
                new_content=new_content,
                similarity=0.0,
            ))
        elif new_content is None:
            diffs.append(SectionDiff(
                section_name=section,
                change_type="removed",
                old_content=old_content,
                new_content=None,
                similarity=0.0,
            ))
        elif old_content == new_content:
            diffs.append(SectionDiff(
                section_name=section,
                change_type="unchanged",
                old_content=old_content,
                new_content=new_content,
                similarity=1.0,
            ))
        else:
            similarity = SequenceMatcher(None, old_content, new_content).ratio()
            diffs.append(SectionDiff(
                section_name=section,
                change_type="modified",
                old_content=old_content,
                new_content=new_content,
                similarity=similarity,
            ))

    return diffs

def diff_sources(old_sources: list[str], new_sources: list[str]) -> SourceDiff:
    """Calculate source diff."""
    old_set = set(old_sources)
    new_set = set(new_sources)

    return SourceDiff(
        added=sorted(new_set - old_set),
        removed=sorted(old_set - new_set),
        unchanged=sorted(old_set & new_set),
    )

def create_version_diff(
    old_run_dir: Path,
    new_run_dir: Path,
    old_run_id: str,
    new_run_id: str,
    old_version: int,
    new_version: int,
) -> VersionDiff:
    """
    Create complete diff between two versions.

    Reads REAL files from run directories.
    """
    # Load markdown
    old_md = (old_run_dir / "procedure.md").read_text()
    new_md = (new_run_dir / "procedure.md").read_text()

    # Load sources
    old_sources_file = old_run_dir / "sources.jsonl"
    new_sources_file = new_run_dir / "sources.jsonl"

    old_source_ids = []
    new_source_ids = []

    if old_sources_file.exists():
        for line in old_sources_file.read_text().splitlines():
            if line.strip():
                old_source_ids.append(json.loads(line)["source_id"])

    if new_sources_file.exists():
        for line in new_sources_file.read_text().splitlines():
            if line.strip():
                new_source_ids.append(json.loads(line)["source_id"])

    # Parse sections
    old_sections = parse_markdown_sections(old_md)
    new_sections = parse_markdown_sections(new_md)

    # Calculate diffs
    section_diffs = diff_sections(old_sections, new_sections)
    source_diff = diff_sources(old_source_ids, new_source_ids)

    # Calculate overall similarity
    changed_sections = [d for d in section_diffs if d.change_type == "modified"]
    if changed_sections:
        overall_similarity = sum(d.similarity for d in section_diffs) / len(section_diffs)
    elif any(d.change_type in ("added", "removed") for d in section_diffs):
        overall_similarity = 0.5
    else:
        overall_similarity = 1.0

    return VersionDiff(
        old_run_id=old_run_id,
        new_run_id=new_run_id,
        old_version=old_version,
        new_version=new_version,
        section_diffs=section_diffs,
        source_diff=source_diff,
        overall_similarity=overall_similarity,
    )

def get_version_history(db_path: Path, procedure: str) -> list[dict[str, Any]]:
    """
    Get complete version history for a procedure.

    Returns list of versions with metadata and diffs to previous.
    """
    normalized = normalize_procedure_name(procedure)
    runs = list_runs_for_procedure(db_path, normalized)

    # Filter to successful runs
    successful = [r for r in runs if r.status == "DONE"]

    # Sort by creation time
    successful.sort(key=lambda r: r.created_at_utc)

    history = []
    for i, run in enumerate(successful):
        entry = {
            "run_id": run.run_id,
            "version": run.version_number or (i + 1),
            "created_at_utc": run.created_at_utc,
            "version_note": run.version_note,
            "quality_score": run.quality_score,
            "source_count": run.source_count,
        }

        # Add diff to previous if exists
        if i > 0:
            prev_run = successful[i - 1]
            try:
                diff = create_version_diff(
                    old_run_dir=Path(prev_run.run_dir),
                    new_run_dir=Path(run.run_dir),
                    old_run_id=prev_run.run_id,
                    new_run_id=run.run_id,
                    old_version=prev_run.version_number or i,
                    new_version=run.version_number or (i + 1),
                )
                entry["diff_from_previous"] = {
                    "sections_changed": sum(1 for d in diff.section_diffs if d.change_type != "unchanged"),
                    "sources_added": len(diff.source_diff.added),
                    "sources_removed": len(diff.source_diff.removed),
                    "overall_similarity": diff.overall_similarity,
                }
            except Exception:
                entry["diff_from_previous"] = None

        history.append(entry)

    return history
```

#### File: `backend/procedurewriter/db.py` (MODIFY)

Add version-aware functions:

```python
def list_runs_for_procedure(db_path: Path, procedure_normalized: str) -> list[Run]:
    """List all runs for a specific procedure (normalized name)."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        """
        SELECT * FROM runs
        WHERE procedure_normalized = ?
        ORDER BY created_at_utc DESC
        """,
        (procedure_normalized,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [Run(**dict(row)) for row in rows]

def update_run_version(
    db_path: Path,
    run_id: str,
    version_number: int,
    parent_run_id: str | None = None,
    version_note: str | None = None,
) -> None:
    """Update version information for a run."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        UPDATE runs
        SET version_number = ?,
            parent_run_id = ?,
            version_note = ?
        WHERE run_id = ?
        """,
        (version_number, parent_run_id, version_note, run_id)
    )
    conn.commit()
    conn.close()
```

#### File: `backend/procedurewriter/main.py` (MODIFY)

Add version endpoints:

```python
from procedurewriter.pipeline.versioning import (
    get_version_history,
    create_version_diff,
    normalize_procedure_name,
)

@app.get("/api/procedures/{procedure}/versions")
def api_procedure_versions(procedure: str) -> dict:
    """Get version history for a procedure."""
    history = get_version_history(settings.db_path, procedure)
    return {"procedure": procedure, "versions": history}

@app.get("/api/runs/{run_id}/diff/{other_run_id}")
def api_run_diff(run_id: str, other_run_id: str) -> dict:
    """Get diff between two runs."""
    run1 = get_run(settings.db_path, run_id)
    run2 = get_run(settings.db_path, other_run_id)

    if not run1 or not run2:
        raise HTTPException(404, "Run not found")

    diff = create_version_diff(
        old_run_dir=Path(run1.run_dir),
        new_run_dir=Path(run2.run_dir),
        old_run_id=run1.run_id,
        new_run_id=run2.run_id,
        old_version=run1.version_number or 1,
        new_version=run2.version_number or 1,
    )

    return {
        "old_run_id": diff.old_run_id,
        "new_run_id": diff.new_run_id,
        "old_version": diff.old_version,
        "new_version": diff.new_version,
        "overall_similarity": diff.overall_similarity,
        "section_diffs": [
            {
                "section": d.section_name,
                "change_type": d.change_type,
                "similarity": d.similarity,
            }
            for d in diff.section_diffs
        ],
        "source_diff": {
            "added": diff.source_diff.added,
            "removed": diff.source_diff.removed,
            "unchanged_count": len(diff.source_diff.unchanged),
        },
    }

@app.post("/api/write")
def api_write(request: WriteRequest) -> dict:
    # ... existing code ...

    # Add version tracking
    procedure_normalized = normalize_procedure_name(request.procedure)
    version_number = calculate_next_version_number(settings.db_path, request.procedure)
    parent_run_id = find_previous_version(settings.db_path, request.procedure, run_id)

    # Store in database
    update_run_version(
        settings.db_path,
        run_id,
        version_number=version_number,
        parent_run_id=parent_run_id,
        version_note=request.version_note,  # Add to WriteRequest
    )

    return {"run_id": run_id, "version": version_number}
```

### Frontend Changes

#### File: `frontend/src/pages/VersionHistoryPage.tsx` (NEW)

```typescript
import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";

interface VersionEntry {
  run_id: string;
  version: number;
  created_at_utc: string;
  version_note: string | null;
  quality_score: number | null;
  source_count: number | null;
  diff_from_previous?: {
    sections_changed: number;
    sources_added: number;
    sources_removed: number;
    overall_similarity: number;
  };
}

interface VersionHistory {
  procedure: string;
  versions: VersionEntry[];
}

export default function VersionHistoryPage() {
  const { procedure } = useParams();
  const [history, setHistory] = useState<VersionHistory | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!procedure) return;

    fetch(`/api/procedures/${encodeURIComponent(procedure)}/versions`)
      .then(r => r.json())
      .then(setHistory)
      .catch(e => setError(e.message));
  }, [procedure]);

  if (!procedure) return <div>Missing procedure</div>;
  if (error) return <div className="card">Error: {error}</div>;
  if (!history) return <div className="card">Loading...</div>;

  return (
    <div className="card">
      <h2>Version History: {history.procedure}</h2>

      <div className="version-timeline">
        {history.versions.map((v, i) => (
          <div key={v.run_id} className="version-entry">
            <div className="version-header">
              <strong>Version {v.version}</strong>
              <span className="muted">{v.created_at_utc}</span>
              {v.quality_score && (
                <span className={`quality-badge quality-${v.quality_score >= 8 ? 'high' : 'low'}`}>
                  {v.quality_score}/10
                </span>
              )}
            </div>

            {v.version_note && (
              <p className="version-note">{v.version_note}</p>
            )}

            {v.diff_from_previous && (
              <div className="diff-summary muted">
                {v.diff_from_previous.sections_changed} sections changed,
                +{v.diff_from_previous.sources_added} / -{v.diff_from_previous.sources_removed} sources,
                {(v.diff_from_previous.overall_similarity * 100).toFixed(0)}% similar
              </div>
            )}

            <div className="version-actions">
              <Link to={`/runs/${v.run_id}`}>View</Link>
              {i > 0 && (
                <Link to={`/runs/${v.run_id}/diff/${history.versions[i-1].run_id}`}>
                  Compare to previous
                </Link>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

#### File: `frontend/src/pages/DiffPage.tsx` (NEW)

```typescript
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

interface SectionDiff {
  section: string;
  change_type: "added" | "removed" | "modified" | "unchanged";
  similarity: number;
}

interface DiffResult {
  old_run_id: string;
  new_run_id: string;
  old_version: number;
  new_version: number;
  overall_similarity: number;
  section_diffs: SectionDiff[];
  source_diff: {
    added: string[];
    removed: string[];
    unchanged_count: number;
  };
}

export default function DiffPage() {
  const { runId, otherRunId } = useParams();
  const [diff, setDiff] = useState<DiffResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!runId || !otherRunId) return;

    fetch(`/api/runs/${runId}/diff/${otherRunId}`)
      .then(r => r.json())
      .then(setDiff)
      .catch(e => setError(e.message));
  }, [runId, otherRunId]);

  if (error) return <div className="card">Error: {error}</div>;
  if (!diff) return <div className="card">Loading...</div>;

  return (
    <div className="card">
      <h2>Diff: Version {diff.old_version} → {diff.new_version}</h2>

      <div className="diff-overview">
        <strong>Overall Similarity:</strong> {(diff.overall_similarity * 100).toFixed(0)}%
      </div>

      <h3>Section Changes</h3>
      <table className="diff-table">
        <thead>
          <tr>
            <th>Section</th>
            <th>Change</th>
            <th>Similarity</th>
          </tr>
        </thead>
        <tbody>
          {diff.section_diffs.map(s => (
            <tr key={s.section} className={`diff-${s.change_type}`}>
              <td>{s.section}</td>
              <td>{s.change_type}</td>
              <td>{s.change_type === "modified" ? `${(s.similarity * 100).toFixed(0)}%` : "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3>Source Changes</h3>
      <div className="source-diff">
        {diff.source_diff.added.length > 0 && (
          <div className="sources-added">
            <strong>Added ({diff.source_diff.added.length}):</strong>
            <ul>
              {diff.source_diff.added.map(s => <li key={s}>{s}</li>)}
            </ul>
          </div>
        )}
        {diff.source_diff.removed.length > 0 && (
          <div className="sources-removed">
            <strong>Removed ({diff.source_diff.removed.length}):</strong>
            <ul>
              {diff.source_diff.removed.map(s => <li key={s}>{s}</li>)}
            </ul>
          </div>
        )}
        <div className="muted">
          {diff.source_diff.unchanged_count} sources unchanged
        </div>
      </div>
    </div>
  );
}
```

---

## Test Requirements

### Backend Tests

#### File: `backend/tests/test_versioning.py` (NEW)

```python
"""
Versioning Tests

IMPORTANT: Tests use REAL database and file operations.
NO MOCKS for storage - test with actual SQLite and files.
"""
import pytest
from pathlib import Path
import tempfile
import json

from procedurewriter.pipeline.versioning import (
    normalize_procedure_name,
    parse_markdown_sections,
    diff_sections,
    diff_sources,
    create_version_diff,
    get_version_history,
)
from procedurewriter.db import create_run, update_run_version

class TestNormalization:
    """Test procedure name normalization."""

    def test_lowercase(self):
        assert normalize_procedure_name("Akut Astma") == "akut astma"

    def test_trim_whitespace(self):
        assert normalize_procedure_name("  test  ") == "test"

    def test_combined(self):
        assert normalize_procedure_name("  AKUT Astma  ") == "akut astma"


class TestMarkdownParsing:
    """Test markdown section parsing."""

    def test_parse_sections(self):
        md = """# Title

## Indikationer
Content for indikationer

## Kontraindikationer
Content for kontra
"""
        sections = parse_markdown_sections(md)
        assert "Indikationer" in sections
        assert "Kontraindikationer" in sections
        assert "Content for indikationer" in sections["Indikationer"]

    def test_preamble_captured(self):
        md = """Some intro text

## Section One
Content
"""
        sections = parse_markdown_sections(md)
        assert "preamble" in sections
        assert "intro" in sections["preamble"]


class TestSectionDiff:
    """Test section diffing."""

    def test_unchanged_section(self):
        old = {"Section A": "Same content"}
        new = {"Section A": "Same content"}
        diffs = diff_sections(old, new)

        assert len(diffs) == 1
        assert diffs[0].change_type == "unchanged"
        assert diffs[0].similarity == 1.0

    def test_added_section(self):
        old = {"A": "content"}
        new = {"A": "content", "B": "new content"}
        diffs = diff_sections(old, new)

        added = [d for d in diffs if d.change_type == "added"]
        assert len(added) == 1
        assert added[0].section_name == "B"

    def test_removed_section(self):
        old = {"A": "content", "B": "old content"}
        new = {"A": "content"}
        diffs = diff_sections(old, new)

        removed = [d for d in diffs if d.change_type == "removed"]
        assert len(removed) == 1
        assert removed[0].section_name == "B"

    def test_modified_section(self):
        old = {"A": "original content here"}
        new = {"A": "modified content here"}
        diffs = diff_sections(old, new)

        assert diffs[0].change_type == "modified"
        assert 0 < diffs[0].similarity < 1


class TestSourceDiff:
    """Test source diffing."""

    def test_source_diff(self):
        old = ["SRC001", "SRC002", "SRC003"]
        new = ["SRC002", "SRC003", "SRC004"]
        diff = diff_sources(old, new)

        assert diff.added == ["SRC004"]
        assert diff.removed == ["SRC001"]
        assert set(diff.unchanged) == {"SRC002", "SRC003"}


class TestVersionDiff:
    """Test complete version diff creation."""

    def test_create_version_diff(self):
        """Test with real files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            old_dir = Path(tmpdir) / "old"
            new_dir = Path(tmpdir) / "new"
            old_dir.mkdir()
            new_dir.mkdir()

            # Create old version
            (old_dir / "procedure.md").write_text("""# Procedure

## Section One
Old content
""")
            (old_dir / "sources.jsonl").write_text(
                '{"source_id": "SRC001"}\n{"source_id": "SRC002"}\n'
            )

            # Create new version
            (new_dir / "procedure.md").write_text("""# Procedure

## Section One
Modified content

## Section Two
New section
""")
            (new_dir / "sources.jsonl").write_text(
                '{"source_id": "SRC002"}\n{"source_id": "SRC003"}\n'
            )

            diff = create_version_diff(
                old_run_dir=old_dir,
                new_run_dir=new_dir,
                old_run_id="run1",
                new_run_id="run2",
                old_version=1,
                new_version=2,
            )

            assert diff.old_version == 1
            assert diff.new_version == 2
            assert len(diff.source_diff.added) == 1
            assert len(diff.source_diff.removed) == 1
            assert any(d.change_type == "added" for d in diff.section_diffs)


class TestVersionHistory:
    """Test version history retrieval."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database with test runs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            # Initialize database and create test runs
            # ... setup code ...
            yield db_path

    def test_version_history_ordering(self, temp_db):
        """Versions are ordered by creation time."""
        # Test implementation
        pass
```

---

## Implementation Checklist

### Phase 1: Database Migration (Day 1)

- [ ] Create migration script `backend/scripts/migrate_versioning.py`
- [ ] Add version columns to runs table
- [ ] Add normalized procedure column
- [ ] Create indexes for version queries
- [ ] Test migration on copy of production DB
- [ ] Run migration

### Phase 2: Versioning Logic (Day 1-2)

- [ ] Create `backend/procedurewriter/pipeline/versioning.py`
- [ ] Implement `normalize_procedure_name()`
- [ ] Implement `parse_markdown_sections()`
- [ ] Implement `diff_sections()`
- [ ] Implement `diff_sources()`
- [ ] Implement `create_version_diff()`
- [ ] Write unit tests
- [ ] Run tests: `pytest backend/tests/test_versioning.py -v`

### Phase 3: API Integration (Day 2)

- [ ] Modify `db.py` with version-aware functions
- [ ] Add `/api/procedures/{procedure}/versions` endpoint
- [ ] Add `/api/runs/{run_id}/diff/{other_run_id}` endpoint
- [ ] Modify `/api/write` to track versions
- [ ] Test API endpoints with curl

### Phase 4: Frontend (Day 2-3)

- [ ] Create `VersionHistoryPage.tsx`
- [ ] Create `DiffPage.tsx`
- [ ] Add routes to router
- [ ] Add version navigation from RunPage
- [ ] Add "View History" link from RunsPage
- [ ] Style diff visualization

### Phase 5: Polish (Day 3)

- [ ] Add version_note field to WriteRequest
- [ ] Add version note UI to WritePage
- [ ] Run full test suite
- [ ] Manual E2E testing
- [ ] Update documentation

---

## Current Status

**Status**: NOT STARTED

**Last Updated**: 2024-12-18

**Checkpoints Completed**:
- [ ] Phase 1: Database Migration
- [ ] Phase 2: Versioning Logic
- [ ] Phase 3: API Integration
- [ ] Phase 4: Frontend
- [ ] Phase 5: Polish

**Blockers**: None

**Notes**: Ready to begin. Run migration script before coding.

---

## Session Handoff Notes

When continuing this enhancement in a new session:

1. Read this document first
2. Check "Current Status" above
3. Load skills: `Skill(superpowers:test-driven-development)`
4. Check if migration has been run
5. Run existing tests to verify baseline: `pytest`
6. Continue from last incomplete checkbox

**REMEMBER**: No dummy/mock implementations. All operations use real database.

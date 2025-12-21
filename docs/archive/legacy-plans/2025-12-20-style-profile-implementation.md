# Style Profile DOCX Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implementer LLM-styret stilprofil system der transformerer rå markdown til professionel medicinsk faglitteratur.

**Architecture:** Post-processing med StyleAgent der polerer markdown baseret på brugerdefinerbare stilprofiler. Profiler oprettes via naturligt sprog og gemmes i SQLite. Forbedret DOCX writer genererer professionelt formaterede dokumenter.

**Tech Stack:** Python 3.11+, SQLite, python-docx, FastAPI, React/TypeScript

---

## Task 1: Database Schema for StyleProfile

**Files:**
- Modify: `backend/procedurewriter/db.py`
- Test: `backend/tests/test_style_profiles_db.py`

**Step 1: Write the failing test**

Create `backend/tests/test_style_profiles_db.py`:

```python
"""Tests for style_profiles database operations."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from procedurewriter.db import (
    init_db,
    create_style_profile,
    get_style_profile,
    list_style_profiles,
    update_style_profile,
    delete_style_profile,
    get_default_style_profile,
    set_default_style_profile,
)


@pytest.fixture
def db_path() -> Path:
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.db"
        init_db(path)
        yield path


def test_create_and_get_style_profile(db_path: Path) -> None:
    """Create a style profile and retrieve it."""
    profile_id = create_style_profile(
        db_path=db_path,
        name="Lærebog Formel",
        description="Akademisk stil til medicinstuderende",
        tone_config={
            "tone_description": "Formel akademisk tone med passiv form",
            "target_audience": "Medicinstuderende",
            "detail_level": "comprehensive",
        },
        structure_config={
            "section_order": ["indikation", "kontraindikation", "procedure"],
            "include_clinical_pearls": True,
            "include_evidence_badges": True,
        },
        formatting_config={
            "heading_style": "numbered",
            "list_style": "bullets",
            "citation_style": "superscript",
        },
        visual_config={
            "color_scheme": "professional_blue",
            "safety_box_style": "yellow_background",
        },
        original_prompt="Skriv som en dansk medicinsk lærebog",
    )

    assert profile_id is not None

    profile = get_style_profile(db_path, profile_id)
    assert profile is not None
    assert profile["name"] == "Lærebog Formel"
    assert profile["tone_config"]["target_audience"] == "Medicinstuderende"


def test_list_style_profiles(db_path: Path) -> None:
    """List all style profiles."""
    create_style_profile(
        db_path=db_path,
        name="Style 1",
        tone_config={},
        structure_config={},
        formatting_config={},
        visual_config={},
    )
    create_style_profile(
        db_path=db_path,
        name="Style 2",
        tone_config={},
        structure_config={},
        formatting_config={},
        visual_config={},
    )

    profiles = list_style_profiles(db_path)
    assert len(profiles) == 2


def test_set_default_style_profile(db_path: Path) -> None:
    """Set a profile as default."""
    id1 = create_style_profile(
        db_path=db_path,
        name="Style 1",
        tone_config={},
        structure_config={},
        formatting_config={},
        visual_config={},
    )
    id2 = create_style_profile(
        db_path=db_path,
        name="Style 2",
        tone_config={},
        structure_config={},
        formatting_config={},
        visual_config={},
    )

    set_default_style_profile(db_path, id1)
    default = get_default_style_profile(db_path)
    assert default is not None
    assert default["id"] == id1

    # Setting new default should unset old one
    set_default_style_profile(db_path, id2)
    default = get_default_style_profile(db_path)
    assert default["id"] == id2


def test_delete_style_profile(db_path: Path) -> None:
    """Delete a style profile."""
    profile_id = create_style_profile(
        db_path=db_path,
        name="To Delete",
        tone_config={},
        structure_config={},
        formatting_config={},
        visual_config={},
    )

    delete_style_profile(db_path, profile_id)
    profile = get_style_profile(db_path, profile_id)
    assert profile is None
```

**Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_style_profiles_db.py -v`
Expected: FAIL with "cannot import name 'create_style_profile'"

**Step 3: Write implementation in db.py**

Add to `backend/procedurewriter/db.py` after the existing tables in `init_db()`:

```python
        # Style profiles table for LLM-powered document formatting
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS style_profiles (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                is_default BOOLEAN DEFAULT FALSE,
                created_at_utc TEXT NOT NULL,
                updated_at_utc TEXT NOT NULL,
                tone_config TEXT NOT NULL,
                structure_config TEXT NOT NULL,
                formatting_config TEXT NOT NULL,
                visual_config TEXT NOT NULL,
                original_prompt TEXT
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_style_profiles_default ON style_profiles(is_default)")
```

Add these functions after the existing database functions:

```python
# =============================================================================
# Style Profile Functions
# =============================================================================


def create_style_profile(
    db_path: Path,
    *,
    name: str,
    tone_config: dict[str, Any],
    structure_config: dict[str, Any],
    formatting_config: dict[str, Any],
    visual_config: dict[str, Any],
    description: str | None = None,
    original_prompt: str | None = None,
) -> str:
    """Create a new style profile."""
    import uuid
    profile_id = str(uuid.uuid4())
    now = utc_now_iso()

    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO style_profiles
            (id, name, description, is_default, created_at_utc, updated_at_utc,
             tone_config, structure_config, formatting_config, visual_config, original_prompt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                profile_id,
                name,
                description,
                False,
                now,
                now,
                json.dumps(tone_config),
                json.dumps(structure_config),
                json.dumps(formatting_config),
                json.dumps(visual_config),
                original_prompt,
            ),
        )
        conn.commit()
    return profile_id


def get_style_profile(db_path: Path, profile_id: str) -> dict[str, Any] | None:
    """Get a style profile by ID."""
    with _connect(db_path) as conn:
        cursor = conn.execute(
            "SELECT * FROM style_profiles WHERE id = ?",
            (profile_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return _row_to_style_profile(row)


def _row_to_style_profile(row: sqlite3.Row) -> dict[str, Any]:
    """Convert a database row to a style profile dict."""
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "is_default": bool(row["is_default"]),
        "created_at_utc": row["created_at_utc"],
        "updated_at_utc": row["updated_at_utc"],
        "tone_config": json.loads(row["tone_config"]),
        "structure_config": json.loads(row["structure_config"]),
        "formatting_config": json.loads(row["formatting_config"]),
        "visual_config": json.loads(row["visual_config"]),
        "original_prompt": row["original_prompt"],
    }


def list_style_profiles(db_path: Path) -> list[dict[str, Any]]:
    """List all style profiles."""
    with _connect(db_path) as conn:
        cursor = conn.execute(
            "SELECT * FROM style_profiles ORDER BY name"
        )
        return [_row_to_style_profile(row) for row in cursor.fetchall()]


def update_style_profile(
    db_path: Path,
    profile_id: str,
    **updates: Any,
) -> bool:
    """Update a style profile. Returns True if updated."""
    allowed_fields = {
        "name", "description", "tone_config", "structure_config",
        "formatting_config", "visual_config", "original_prompt"
    }
    updates = {k: v for k, v in updates.items() if k in allowed_fields}
    if not updates:
        return False

    # JSON-encode dict fields
    for key in ["tone_config", "structure_config", "formatting_config", "visual_config"]:
        if key in updates and isinstance(updates[key], dict):
            updates[key] = json.dumps(updates[key])

    updates["updated_at_utc"] = utc_now_iso()

    set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
    values = list(updates.values()) + [profile_id]

    with _connect(db_path) as conn:
        cursor = conn.execute(
            f"UPDATE style_profiles SET {set_clause} WHERE id = ?",
            values,
        )
        conn.commit()
        return cursor.rowcount > 0


def delete_style_profile(db_path: Path, profile_id: str) -> bool:
    """Delete a style profile. Returns True if deleted."""
    with _connect(db_path) as conn:
        cursor = conn.execute(
            "DELETE FROM style_profiles WHERE id = ?",
            (profile_id,),
        )
        conn.commit()
        return cursor.rowcount > 0


def get_default_style_profile(db_path: Path) -> dict[str, Any] | None:
    """Get the default style profile."""
    with _connect(db_path) as conn:
        cursor = conn.execute(
            "SELECT * FROM style_profiles WHERE is_default = 1 LIMIT 1"
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return _row_to_style_profile(row)


def set_default_style_profile(db_path: Path, profile_id: str) -> None:
    """Set a profile as the default (unsets any existing default)."""
    with _connect(db_path) as conn:
        conn.execute("UPDATE style_profiles SET is_default = 0")
        conn.execute(
            "UPDATE style_profiles SET is_default = 1 WHERE id = ?",
            (profile_id,),
        )
        conn.commit()
```

**Step 4: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_style_profiles_db.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/procedurewriter/db.py backend/tests/test_style_profiles_db.py
git commit -m "feat: add style_profiles database schema and CRUD operations"
```

---

## Task 2: StyleProfile Dataclass

**Files:**
- Create: `backend/procedurewriter/models/style_profile.py`
- Modify: `backend/procedurewriter/models/__init__.py` (create if needed)
- Test: `backend/tests/test_style_profile_model.py`

**Step 1: Write the failing test**

Create `backend/tests/test_style_profile_model.py`:

```python
"""Tests for StyleProfile model."""
from __future__ import annotations

import pytest

from procedurewriter.models.style_profile import StyleProfile, StyleProfileCreate


def test_style_profile_from_db_dict() -> None:
    """Create StyleProfile from database dict."""
    db_dict = {
        "id": "abc-123",
        "name": "Test Style",
        "description": "A test style",
        "is_default": True,
        "created_at_utc": "2025-01-01T00:00:00+00:00",
        "updated_at_utc": "2025-01-01T00:00:00+00:00",
        "tone_config": {
            "tone_description": "Formal",
            "target_audience": "Doctors",
            "detail_level": "comprehensive",
        },
        "structure_config": {
            "section_order": ["a", "b"],
            "include_clinical_pearls": True,
            "include_evidence_badges": False,
        },
        "formatting_config": {
            "heading_style": "numbered",
            "list_style": "bullets",
            "citation_style": "superscript",
        },
        "visual_config": {
            "color_scheme": "blue",
            "safety_box_style": "yellow",
        },
        "original_prompt": "Write formally",
    }

    profile = StyleProfile.from_db_dict(db_dict)

    assert profile.id == "abc-123"
    assert profile.name == "Test Style"
    assert profile.tone_description == "Formal"
    assert profile.target_audience == "Doctors"
    assert profile.include_clinical_pearls is True
    assert profile.heading_style == "numbered"


def test_style_profile_to_db_dict() -> None:
    """Convert StyleProfile to database dict."""
    profile = StyleProfile(
        id="abc-123",
        name="Test",
        description=None,
        is_default=False,
        tone_description="Casual",
        target_audience="Students",
        detail_level="concise",
        section_order=["x"],
        include_clinical_pearls=False,
        include_evidence_badges=True,
        heading_style="unnumbered",
        list_style="prose",
        citation_style="inline",
        color_scheme="gray",
        safety_box_style="red",
        original_prompt=None,
    )

    db_dict = profile.to_db_dict()

    assert db_dict["name"] == "Test"
    assert db_dict["tone_config"]["tone_description"] == "Casual"
    assert db_dict["structure_config"]["section_order"] == ["x"]


def test_style_profile_create_validation() -> None:
    """StyleProfileCreate validates required fields."""
    # Valid creation
    create = StyleProfileCreate(
        name="Valid",
        tone_description="Tone",
        target_audience="Audience",
        detail_level="moderate",
    )
    assert create.name == "Valid"

    # Missing required field should raise
    with pytest.raises(ValueError):
        StyleProfileCreate(name="")  # Empty name
```

**Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_style_profile_model.py -v`
Expected: FAIL with "No module named 'procedurewriter.models'"

**Step 3: Write implementation**

Create `backend/procedurewriter/models/__init__.py`:

```python
"""Data models for procedurewriter."""
from procedurewriter.models.style_profile import (
    StyleProfile,
    StyleProfileCreate,
    StyleProfileSummary,
)

__all__ = ["StyleProfile", "StyleProfileCreate", "StyleProfileSummary"]
```

Create `backend/procedurewriter/models/style_profile.py`:

```python
"""StyleProfile model for LLM-powered document formatting."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class StyleProfile:
    """Complete style profile for document generation."""

    id: str
    name: str
    description: str | None
    is_default: bool

    # Tone & Content
    tone_description: str
    target_audience: str
    detail_level: str  # "concise" | "moderate" | "comprehensive"

    # Structure
    section_order: list[str] = field(default_factory=list)
    include_clinical_pearls: bool = False
    include_evidence_badges: bool = True

    # Formatting
    heading_style: str = "numbered"  # "numbered" | "unnumbered"
    list_style: str = "bullets"  # "bullets" | "numbered" | "prose"
    citation_style: str = "superscript"  # "superscript" | "inline"

    # Visual
    color_scheme: str = "professional_blue"
    safety_box_style: str = "yellow_background"

    # Meta
    original_prompt: str | None = None

    @classmethod
    def from_db_dict(cls, data: dict[str, Any]) -> StyleProfile:
        """Create from database dictionary."""
        tone = data.get("tone_config", {})
        structure = data.get("structure_config", {})
        formatting = data.get("formatting_config", {})
        visual = data.get("visual_config", {})

        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description"),
            is_default=data.get("is_default", False),
            tone_description=tone.get("tone_description", ""),
            target_audience=tone.get("target_audience", ""),
            detail_level=tone.get("detail_level", "moderate"),
            section_order=structure.get("section_order", []),
            include_clinical_pearls=structure.get("include_clinical_pearls", False),
            include_evidence_badges=structure.get("include_evidence_badges", True),
            heading_style=formatting.get("heading_style", "numbered"),
            list_style=formatting.get("list_style", "bullets"),
            citation_style=formatting.get("citation_style", "superscript"),
            color_scheme=visual.get("color_scheme", "professional_blue"),
            safety_box_style=visual.get("safety_box_style", "yellow_background"),
            original_prompt=data.get("original_prompt"),
        )

    def to_db_dict(self) -> dict[str, Any]:
        """Convert to database dictionary format."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "is_default": self.is_default,
            "tone_config": {
                "tone_description": self.tone_description,
                "target_audience": self.target_audience,
                "detail_level": self.detail_level,
            },
            "structure_config": {
                "section_order": self.section_order,
                "include_clinical_pearls": self.include_clinical_pearls,
                "include_evidence_badges": self.include_evidence_badges,
            },
            "formatting_config": {
                "heading_style": self.heading_style,
                "list_style": self.list_style,
                "citation_style": self.citation_style,
            },
            "visual_config": {
                "color_scheme": self.color_scheme,
                "safety_box_style": self.safety_box_style,
            },
            "original_prompt": self.original_prompt,
        }


@dataclass
class StyleProfileSummary:
    """Summary view of a style profile for listing."""

    id: str
    name: str
    description: str | None
    is_default: bool

    @classmethod
    def from_db_dict(cls, data: dict[str, Any]) -> StyleProfileSummary:
        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description"),
            is_default=data.get("is_default", False),
        )


@dataclass
class StyleProfileCreate:
    """Input for creating a new style profile."""

    name: str
    tone_description: str = ""
    target_audience: str = ""
    detail_level: str = "moderate"
    description: str | None = None
    section_order: list[str] = field(default_factory=list)
    include_clinical_pearls: bool = False
    include_evidence_badges: bool = True
    heading_style: str = "numbered"
    list_style: str = "bullets"
    citation_style: str = "superscript"
    color_scheme: str = "professional_blue"
    safety_box_style: str = "yellow_background"
    original_prompt: str | None = None

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("name is required")
```

**Step 4: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_style_profile_model.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/procedurewriter/models/
git add backend/tests/test_style_profile_model.py
git commit -m "feat: add StyleProfile dataclass with DB conversion methods"
```

---

## Task 3: StyleAgent with Citation Validation

**Files:**
- Create: `backend/procedurewriter/agents/style_agent.py`
- Test: `backend/tests/agents/test_style_agent.py`

**Step 1: Write the failing test**

Create `backend/tests/agents/test_style_agent.py`:

```python
"""Tests for StyleAgent."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from procedurewriter.agents.style_agent import (
    StyleAgent,
    StyleInput,
    StyleOutput,
    StyleValidationError,
)
from procedurewriter.models.style_profile import StyleProfile
from procedurewriter.llm.providers import LLMResponse


def make_test_profile() -> StyleProfile:
    return StyleProfile(
        id="test-id",
        name="Test",
        description=None,
        is_default=False,
        tone_description="Formel akademisk tone",
        target_audience="Læger",
        detail_level="comprehensive",
        section_order=[],
        include_clinical_pearls=False,
        include_evidence_badges=True,
        heading_style="numbered",
        list_style="bullets",
        citation_style="superscript",
        color_scheme="blue",
        safety_box_style="yellow",
        original_prompt=None,
    )


def test_style_agent_preserves_citations() -> None:
    """StyleAgent must preserve all citations."""
    mock_llm = MagicMock()
    mock_llm.chat_completion.return_value = LLMResponse(
        content="Poleret tekst med [SRC0001] og [SRC0002] bevaret.",
        input_tokens=100,
        output_tokens=50,
        total_tokens=150,
        model="test",
    )

    agent = StyleAgent(llm=mock_llm, model="test")
    input_data = StyleInput(
        procedure_title="Test",
        raw_markdown="Original tekst med [SRC0001] og [SRC0002].",
        sources=[],
        style_profile=make_test_profile(),
    )

    result = agent.execute(input_data)

    assert result.output.success is True
    assert "[SRC0001]" in result.output.polished_markdown
    assert "[SRC0002]" in result.output.polished_markdown


def test_style_agent_fails_on_missing_citations() -> None:
    """StyleAgent should fail if LLM drops citations."""
    mock_llm = MagicMock()
    # LLM response is missing [SRC0002]
    mock_llm.chat_completion.return_value = LLMResponse(
        content="Poleret tekst med [SRC0001] men mangler den anden.",
        input_tokens=100,
        output_tokens=50,
        total_tokens=150,
        model="test",
    )

    agent = StyleAgent(llm=mock_llm, model="test")
    input_data = StyleInput(
        procedure_title="Test",
        raw_markdown="Original tekst med [SRC0001] og [SRC0002].",
        sources=[],
        style_profile=make_test_profile(),
    )

    result = agent.execute(input_data)

    # Should indicate failure or retry
    assert result.output.success is False or "[SRC0002]" in result.output.polished_markdown


def test_style_agent_applies_tone() -> None:
    """StyleAgent should include tone in prompt."""
    mock_llm = MagicMock()
    mock_llm.chat_completion.return_value = LLMResponse(
        content="Poleret output",
        input_tokens=100,
        output_tokens=50,
        total_tokens=150,
        model="test",
    )

    agent = StyleAgent(llm=mock_llm, model="test")
    profile = make_test_profile()
    profile.tone_description = "VERY_SPECIFIC_TONE"

    input_data = StyleInput(
        procedure_title="Test",
        raw_markdown="Text",
        sources=[],
        style_profile=profile,
    )

    agent.execute(input_data)

    # Check that LLM was called with tone in prompt
    call_args = mock_llm.chat_completion.call_args
    messages = call_args.kwargs.get("messages", call_args.args[0] if call_args.args else [])
    prompt_content = str(messages)
    assert "VERY_SPECIFIC_TONE" in prompt_content
```

**Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/agents/test_style_agent.py -v`
Expected: FAIL with "No module named 'procedurewriter.agents.style_agent'"

**Step 3: Write implementation**

Create `backend/procedurewriter/agents/style_agent.py`:

```python
"""StyleAgent for LLM-powered markdown polishing.

Transforms raw procedure markdown into professionally-written medical text
while preserving all citations and factual content.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from pydantic import BaseModel

from procedurewriter.agents.base import AgentInput, AgentOutput, AgentResult, BaseAgent
from procedurewriter.models.style_profile import StyleProfile
from procedurewriter.pipeline.types import SourceRecord


class StyleValidationError(Exception):
    """Raised when polished output fails validation."""

    def __init__(self, message: str, missing_citations: set[str] | None = None):
        super().__init__(message)
        self.missing_citations = missing_citations or set()


class StyleInput(AgentInput):
    """Input for StyleAgent."""

    raw_markdown: str
    sources: list[SourceRecord] = []
    style_profile: StyleProfile

    class Config:
        arbitrary_types_allowed = True


class StyleOutput(AgentOutput):
    """Output from StyleAgent."""

    polished_markdown: str = ""
    applied_rules: list[str] = []
    warnings: list[str] = []


STYLE_SYSTEM_PROMPT = """Du er en erfaren medicinsk redaktør og forfatter af kliniske lærebøger.

Din opgave er at omskrive procedurer til professionel bogkvalitet.

ABSOLUTTE REGLER (må ALDRIG brydes):
1. BEVAR alle citations [SRC0001], [SRC0002] osv. PRÆCIST som de er
2. BEVAR alle fakta og medicinsk indhold - omskriv KUN formuleringen
3. Fjern markdown-syntaks (**bold**, *italic*) - brug ren tekst
4. Bevar alle sektionsoverskrifter

STIL-PROFIL:
{tone_description}

MÅLGRUPPE: {target_audience}

DETALJENIVEAU: {detail_level}

FORMATERINGSINSTRUKTIONER:
- Overskriftsstil: {heading_style}
- Listestil: {list_style}
- Citationsstil: {citation_style}

Omskriv teksten så den:
- Har flydende, professionelle overgange mellem afsnit
- Bruger korrekt medicinsk terminologi
- Er klar og præcis
- Passer til målgruppen"""


class StyleAgent(BaseAgent[StyleInput, StyleOutput]):
    """Agent that polishes markdown to professional medical writing style."""

    @property
    def name(self) -> str:
        return "StyleAgent"

    def execute(
        self,
        input_data: StyleInput,
        max_retries: int = 2,
    ) -> AgentResult[StyleOutput]:
        """Execute style polishing with citation validation."""
        self.reset_stats()

        profile = input_data.style_profile
        original_citations = self._extract_citations(input_data.raw_markdown)

        system_prompt = STYLE_SYSTEM_PROMPT.format(
            tone_description=profile.tone_description,
            target_audience=profile.target_audience,
            detail_level=profile.detail_level,
            heading_style=profile.heading_style,
            list_style=profile.list_style,
            citation_style=profile.citation_style,
        )

        user_prompt = f"""Omskriv følgende procedure til bogkvalitet:

{input_data.raw_markdown}

HUSK: Alle citations [SRC0001] osv. SKAL bevares præcist!"""

        for attempt in range(max_retries + 1):
            response = self.llm_call(
                messages=[
                    self._make_system_message(system_prompt),
                    self._make_user_message(user_prompt),
                ],
                temperature=0.3,
            )

            polished = response.content
            polished_citations = self._extract_citations(polished)

            missing = original_citations - polished_citations
            if not missing:
                return AgentResult(
                    output=StyleOutput(
                        success=True,
                        polished_markdown=polished,
                        applied_rules=[
                            f"tone: {profile.tone_description}",
                            f"audience: {profile.target_audience}",
                            f"detail: {profile.detail_level}",
                        ],
                        warnings=[],
                    ),
                    stats=self.get_stats(),
                )

            # Retry with stronger prompt
            user_prompt = f"""FEJL: Du manglede disse citations: {missing}

Du SKAL inkludere ALLE citations fra originalen. Prøv igen:

{input_data.raw_markdown}

KRITISK: Hver eneste [SRC0001], [SRC0002] osv. SKAL være i dit output!"""

        # All retries failed
        return AgentResult(
            output=StyleOutput(
                success=False,
                polished_markdown=input_data.raw_markdown,  # Fallback to original
                applied_rules=[],
                warnings=[f"Citation validation failed after {max_retries + 1} attempts. Missing: {missing}"],
                error=f"Manglende citations: {missing}",
            ),
            stats=self.get_stats(),
        )

    def _extract_citations(self, text: str) -> set[str]:
        """Extract all [SRC0001] style citations from text."""
        return set(re.findall(r'\[SRC\d+\]', text))
```

**Step 4: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/agents/test_style_agent.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/procedurewriter/agents/style_agent.py
git add backend/tests/agents/test_style_agent.py
git commit -m "feat: add StyleAgent with citation validation and retry logic"
```

---

## Task 4: NL→Profile Parser Agent

**Files:**
- Create: `backend/procedurewriter/agents/style_parser_agent.py`
- Test: `backend/tests/agents/test_style_parser_agent.py`

**Step 1: Write the failing test**

Create `backend/tests/agents/test_style_parser_agent.py`:

```python
"""Tests for StyleParserAgent."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from procedurewriter.agents.style_parser_agent import (
    StyleParserAgent,
    StyleParserInput,
)
from procedurewriter.llm.providers import LLMResponse


def test_parse_natural_language_to_profile() -> None:
    """Parse natural language description to structured profile."""
    mock_llm = MagicMock()
    mock_llm.chat_completion.return_value = LLMResponse(
        content=json.dumps({
            "name": "Lærebog Stil",
            "tone_description": "Formel akademisk tone med passiv form",
            "target_audience": "Medicinstuderende",
            "detail_level": "comprehensive",
            "include_clinical_pearls": True,
            "include_evidence_badges": True,
            "heading_style": "numbered",
            "list_style": "bullets",
            "citation_style": "superscript",
            "color_scheme": "professional_blue",
            "safety_box_style": "yellow_background",
        }),
        input_tokens=100,
        output_tokens=200,
        total_tokens=300,
        model="test",
    )

    agent = StyleParserAgent(llm=mock_llm, model="test")
    input_data = StyleParserInput(
        procedure_title="",
        natural_language_prompt="Skriv som en dansk medicinsk lærebog til medicinstuderende. Formel tone.",
    )

    result = agent.execute(input_data)

    assert result.output.success is True
    assert result.output.parsed_profile is not None
    assert result.output.parsed_profile.tone_description == "Formel akademisk tone med passiv form"


def test_parse_handles_invalid_json() -> None:
    """Parser should handle invalid JSON from LLM."""
    mock_llm = MagicMock()
    mock_llm.chat_completion.return_value = LLMResponse(
        content="This is not valid JSON at all",
        input_tokens=100,
        output_tokens=50,
        total_tokens=150,
        model="test",
    )

    agent = StyleParserAgent(llm=mock_llm, model="test")
    input_data = StyleParserInput(
        procedure_title="",
        natural_language_prompt="Invalid prompt",
    )

    result = agent.execute(input_data)

    assert result.output.success is False
    assert result.output.error is not None
```

**Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/agents/test_style_parser_agent.py -v`
Expected: FAIL with "No module named 'procedurewriter.agents.style_parser_agent'"

**Step 3: Write implementation**

Create `backend/procedurewriter/agents/style_parser_agent.py`:

```python
"""StyleParserAgent for converting natural language to StyleProfile.

Transforms user's natural language description into a structured StyleProfile
that can be used for document generation.
"""
from __future__ import annotations

import json
import re

from pydantic import BaseModel

from procedurewriter.agents.base import AgentInput, AgentOutput, AgentResult, BaseAgent
from procedurewriter.models.style_profile import StyleProfile, StyleProfileCreate


class StyleParserInput(AgentInput):
    """Input for StyleParserAgent."""

    natural_language_prompt: str


class StyleParserOutput(AgentOutput):
    """Output from StyleParserAgent."""

    parsed_profile: StyleProfile | None = None

    class Config:
        arbitrary_types_allowed = True


PARSER_SYSTEM_PROMPT = """Du er en ekspert i at konvertere naturlige sprogbeskrivelser til strukturerede stilprofiler for medicinske dokumenter.

Givet en beskrivelse af ønsket stil, skal du returnere et JSON-objekt med følgende felter:

{
  "name": "Kort navn til profilen (max 50 tegn)",
  "tone_description": "Detaljeret beskrivelse af tonen (formel/uformel, aktiv/passiv form, osv.)",
  "target_audience": "Målgruppe (f.eks. 'Medicinstuderende', 'Speciallæger', 'Sygeplejersker')",
  "detail_level": "concise" | "moderate" | "comprehensive",
  "include_clinical_pearls": true | false,
  "include_evidence_badges": true | false,
  "heading_style": "numbered" | "unnumbered",
  "list_style": "bullets" | "numbered" | "prose",
  "citation_style": "superscript" | "inline",
  "color_scheme": "professional_blue" | "neutral_gray" | "clinical_red",
  "safety_box_style": "yellow_background" | "red_border" | "icon_based"
}

RETURNER KUN VALID JSON - ingen forklaringer eller andet tekst."""


class StyleParserAgent(BaseAgent[StyleParserInput, StyleParserOutput]):
    """Agent that parses natural language into StyleProfile."""

    @property
    def name(self) -> str:
        return "StyleParserAgent"

    def execute(self, input_data: StyleParserInput) -> AgentResult[StyleParserOutput]:
        """Parse natural language description to StyleProfile."""
        self.reset_stats()

        user_prompt = f"""Konverter denne stilbeskrivelse til en struktureret profil:

"{input_data.natural_language_prompt}"

Returnér kun JSON-objektet."""

        response = self.llm_call(
            messages=[
                self._make_system_message(PARSER_SYSTEM_PROMPT),
                self._make_user_message(user_prompt),
            ],
            temperature=0.2,
        )

        try:
            # Extract JSON from response (handle code blocks)
            content = response.content.strip()
            if "```json" in content:
                content = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
                if content:
                    content = content.group(1)
                else:
                    content = response.content
            elif "```" in content:
                content = re.search(r'```\s*(.*?)\s*```', content, re.DOTALL)
                if content:
                    content = content.group(1)
                else:
                    content = response.content

            data = json.loads(content)

            profile = StyleProfile(
                id="",  # Will be assigned on save
                name=data.get("name", "Ny Stil"),
                description=None,
                is_default=False,
                tone_description=data.get("tone_description", ""),
                target_audience=data.get("target_audience", ""),
                detail_level=data.get("detail_level", "moderate"),
                section_order=data.get("section_order", []),
                include_clinical_pearls=data.get("include_clinical_pearls", False),
                include_evidence_badges=data.get("include_evidence_badges", True),
                heading_style=data.get("heading_style", "numbered"),
                list_style=data.get("list_style", "bullets"),
                citation_style=data.get("citation_style", "superscript"),
                color_scheme=data.get("color_scheme", "professional_blue"),
                safety_box_style=data.get("safety_box_style", "yellow_background"),
                original_prompt=input_data.natural_language_prompt,
            )

            return AgentResult(
                output=StyleParserOutput(
                    success=True,
                    parsed_profile=profile,
                ),
                stats=self.get_stats(),
            )

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            return AgentResult(
                output=StyleParserOutput(
                    success=False,
                    error=f"Kunne ikke parse LLM-svar: {e}",
                ),
                stats=self.get_stats(),
            )
```

**Step 4: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/agents/test_style_parser_agent.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/procedurewriter/agents/style_parser_agent.py
git add backend/tests/agents/test_style_parser_agent.py
git commit -m "feat: add StyleParserAgent for NL to profile conversion"
```

---

## Task 5: API Endpoints for Style Profiles

**Files:**
- Modify: `backend/procedurewriter/main.py`
- Test: `backend/tests/api/test_styles_api.py`

**Step 1: Write the failing test**

Create `backend/tests/api/test_styles_api.py`:

```python
"""Tests for style profile API endpoints."""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from procedurewriter.main import app
from procedurewriter.db import init_db
from procedurewriter.settings import Settings


@pytest.fixture
def test_client():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        init_db(db_path)

        with patch.object(Settings, "db_path", db_path):
            with TestClient(app) as client:
                yield client


def test_list_styles_empty(test_client) -> None:
    """List styles when none exist."""
    response = test_client.get("/api/styles")
    assert response.status_code == 200
    assert response.json() == []


def test_create_style(test_client) -> None:
    """Create a new style profile."""
    response = test_client.post(
        "/api/styles",
        json={
            "name": "Test Style",
            "tone_description": "Formal",
            "target_audience": "Doctors",
            "detail_level": "comprehensive",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Style"
    assert "id" in data


def test_get_style(test_client) -> None:
    """Get a specific style profile."""
    # Create first
    create_response = test_client.post(
        "/api/styles",
        json={"name": "Get Test", "tone_description": "Test"},
    )
    style_id = create_response.json()["id"]

    # Get it
    response = test_client.get(f"/api/styles/{style_id}")
    assert response.status_code == 200
    assert response.json()["name"] == "Get Test"


def test_set_default_style(test_client) -> None:
    """Set a style as default."""
    # Create a style
    create_response = test_client.post(
        "/api/styles",
        json={"name": "Default Test", "tone_description": "Test"},
    )
    style_id = create_response.json()["id"]

    # Set as default
    response = test_client.post(f"/api/styles/{style_id}/set-default")
    assert response.status_code == 200

    # Verify it's default
    get_response = test_client.get(f"/api/styles/{style_id}")
    assert get_response.json()["is_default"] is True


def test_delete_style(test_client) -> None:
    """Delete a style profile."""
    # Create first
    create_response = test_client.post(
        "/api/styles",
        json={"name": "Delete Test", "tone_description": "Test"},
    )
    style_id = create_response.json()["id"]

    # Delete it
    response = test_client.delete(f"/api/styles/{style_id}")
    assert response.status_code == 200

    # Verify it's gone
    get_response = test_client.get(f"/api/styles/{style_id}")
    assert get_response.status_code == 404
```

**Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/api/test_styles_api.py -v`
Expected: FAIL with 404 for /api/styles

**Step 3: Write implementation**

Add to `backend/procedurewriter/main.py` (after existing endpoints):

```python
# =============================================================================
# Style Profile API Endpoints
# =============================================================================

from procedurewriter.db import (
    create_style_profile,
    get_style_profile,
    list_style_profiles,
    update_style_profile,
    delete_style_profile,
    get_default_style_profile,
    set_default_style_profile,
)
from procedurewriter.models.style_profile import StyleProfile, StyleProfileSummary


class CreateStyleRequest(BaseModel):
    name: str
    description: str | None = None
    tone_description: str = ""
    target_audience: str = ""
    detail_level: str = "moderate"
    section_order: list[str] = []
    include_clinical_pearls: bool = False
    include_evidence_badges: bool = True
    heading_style: str = "numbered"
    list_style: str = "bullets"
    citation_style: str = "superscript"
    color_scheme: str = "professional_blue"
    safety_box_style: str = "yellow_background"
    original_prompt: str | None = None


class UpdateStyleRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    tone_description: str | None = None
    target_audience: str | None = None
    detail_level: str | None = None
    section_order: list[str] | None = None
    include_clinical_pearls: bool | None = None
    include_evidence_badges: bool | None = None
    heading_style: str | None = None
    list_style: str | None = None
    citation_style: str | None = None
    color_scheme: str | None = None
    safety_box_style: str | None = None
    original_prompt: str | None = None


@app.get("/api/styles")
def api_list_styles() -> list[dict[str, Any]]:
    """List all style profiles."""
    profiles = list_style_profiles(settings.db_path)
    return [
        {
            "id": p["id"],
            "name": p["name"],
            "description": p["description"],
            "is_default": p["is_default"],
        }
        for p in profiles
    ]


@app.get("/api/styles/{style_id}")
def api_get_style(style_id: str) -> dict[str, Any]:
    """Get a specific style profile."""
    profile = get_style_profile(settings.db_path, style_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Style profile not found")
    return StyleProfile.from_db_dict(profile).__dict__


@app.post("/api/styles")
def api_create_style(request: CreateStyleRequest) -> dict[str, Any]:
    """Create a new style profile."""
    profile_id = create_style_profile(
        db_path=settings.db_path,
        name=request.name,
        description=request.description,
        tone_config={
            "tone_description": request.tone_description,
            "target_audience": request.target_audience,
            "detail_level": request.detail_level,
        },
        structure_config={
            "section_order": request.section_order,
            "include_clinical_pearls": request.include_clinical_pearls,
            "include_evidence_badges": request.include_evidence_badges,
        },
        formatting_config={
            "heading_style": request.heading_style,
            "list_style": request.list_style,
            "citation_style": request.citation_style,
        },
        visual_config={
            "color_scheme": request.color_scheme,
            "safety_box_style": request.safety_box_style,
        },
        original_prompt=request.original_prompt,
    )

    profile = get_style_profile(settings.db_path, profile_id)
    return StyleProfile.from_db_dict(profile).__dict__


@app.put("/api/styles/{style_id}")
def api_update_style(style_id: str, request: UpdateStyleRequest) -> dict[str, Any]:
    """Update a style profile."""
    existing = get_style_profile(settings.db_path, style_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Style profile not found")

    updates = {}
    if request.name is not None:
        updates["name"] = request.name
    if request.description is not None:
        updates["description"] = request.description
    if request.original_prompt is not None:
        updates["original_prompt"] = request.original_prompt

    # Build config updates
    tone_updates = {}
    if request.tone_description is not None:
        tone_updates["tone_description"] = request.tone_description
    if request.target_audience is not None:
        tone_updates["target_audience"] = request.target_audience
    if request.detail_level is not None:
        tone_updates["detail_level"] = request.detail_level
    if tone_updates:
        existing_tone = existing.get("tone_config", {})
        existing_tone.update(tone_updates)
        updates["tone_config"] = existing_tone

    structure_updates = {}
    if request.section_order is not None:
        structure_updates["section_order"] = request.section_order
    if request.include_clinical_pearls is not None:
        structure_updates["include_clinical_pearls"] = request.include_clinical_pearls
    if request.include_evidence_badges is not None:
        structure_updates["include_evidence_badges"] = request.include_evidence_badges
    if structure_updates:
        existing_structure = existing.get("structure_config", {})
        existing_structure.update(structure_updates)
        updates["structure_config"] = existing_structure

    formatting_updates = {}
    if request.heading_style is not None:
        formatting_updates["heading_style"] = request.heading_style
    if request.list_style is not None:
        formatting_updates["list_style"] = request.list_style
    if request.citation_style is not None:
        formatting_updates["citation_style"] = request.citation_style
    if formatting_updates:
        existing_formatting = existing.get("formatting_config", {})
        existing_formatting.update(formatting_updates)
        updates["formatting_config"] = existing_formatting

    visual_updates = {}
    if request.color_scheme is not None:
        visual_updates["color_scheme"] = request.color_scheme
    if request.safety_box_style is not None:
        visual_updates["safety_box_style"] = request.safety_box_style
    if visual_updates:
        existing_visual = existing.get("visual_config", {})
        existing_visual.update(visual_updates)
        updates["visual_config"] = existing_visual

    if updates:
        update_style_profile(settings.db_path, style_id, **updates)

    profile = get_style_profile(settings.db_path, style_id)
    return StyleProfile.from_db_dict(profile).__dict__


@app.delete("/api/styles/{style_id}")
def api_delete_style(style_id: str) -> dict[str, str]:
    """Delete a style profile."""
    existing = get_style_profile(settings.db_path, style_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Style profile not found")

    delete_style_profile(settings.db_path, style_id)
    return {"status": "deleted"}


@app.post("/api/styles/{style_id}/set-default")
def api_set_default_style(style_id: str) -> dict[str, str]:
    """Set a style profile as the default."""
    existing = get_style_profile(settings.db_path, style_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Style profile not found")

    set_default_style_profile(settings.db_path, style_id)
    return {"status": "ok"}


@app.get("/api/styles/default")
def api_get_default_style() -> dict[str, Any] | None:
    """Get the default style profile."""
    profile = get_default_style_profile(settings.db_path)
    if profile is None:
        return None
    return StyleProfile.from_db_dict(profile).__dict__
```

**Step 4: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/api/test_styles_api.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/procedurewriter/main.py
git add backend/tests/api/test_styles_api.py
git commit -m "feat: add style profile API endpoints"
```

---

## Task 6: Pipeline Integration

**Files:**
- Modify: `backend/procedurewriter/pipeline/run.py`
- Test: `backend/tests/pipeline/test_style_integration.py`

**Step 1: Write the failing test**

Create `backend/tests/pipeline/test_style_integration.py`:

```python
"""Tests for style profile integration in pipeline."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from procedurewriter.models.style_profile import StyleProfile


def make_test_profile() -> StyleProfile:
    return StyleProfile(
        id="test-id",
        name="Test",
        description=None,
        is_default=True,
        tone_description="Formel",
        target_audience="Læger",
        detail_level="comprehensive",
    )


def test_pipeline_uses_style_agent_when_profile_exists() -> None:
    """Pipeline should use StyleAgent when a default profile exists."""
    # This test verifies the integration point exists
    from procedurewriter.pipeline.run import _apply_style_profile

    mock_llm = MagicMock()
    mock_llm.chat_completion.return_value = MagicMock(
        content="Polished [SRC0001] text",
        input_tokens=10,
        output_tokens=10,
        total_tokens=20,
    )

    result = _apply_style_profile(
        raw_markdown="Original [SRC0001] text",
        sources=[],
        procedure_name="Test",
        style_profile=make_test_profile(),
        llm=mock_llm,
        model="test",
    )

    assert result is not None
    assert "[SRC0001]" in result


def test_pipeline_returns_original_when_no_profile() -> None:
    """Pipeline should return original markdown when no profile."""
    from procedurewriter.pipeline.run import _apply_style_profile

    result = _apply_style_profile(
        raw_markdown="Original text",
        sources=[],
        procedure_name="Test",
        style_profile=None,
        llm=None,
        model=None,
    )

    assert result == "Original text"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/pipeline/test_style_integration.py -v`
Expected: FAIL with "cannot import name '_apply_style_profile'"

**Step 3: Write implementation**

Add to `backend/procedurewriter/pipeline/run.py`:

```python
# Add imports at top
from procedurewriter.agents.style_agent import StyleAgent, StyleInput
from procedurewriter.models.style_profile import StyleProfile
from procedurewriter.db import get_default_style_profile


def _apply_style_profile(
    *,
    raw_markdown: str,
    sources: list[SourceRecord],
    procedure_name: str,
    style_profile: StyleProfile | None,
    llm: LLMProvider | None,
    model: str | None,
) -> str:
    """Apply style profile to markdown using StyleAgent.

    Returns original markdown if no profile or LLM available.
    """
    if style_profile is None or llm is None:
        return raw_markdown

    try:
        agent = StyleAgent(llm=llm, model=model or "gpt-4")
        result = agent.execute(
            StyleInput(
                procedure_title=procedure_name,
                raw_markdown=raw_markdown,
                sources=sources,
                style_profile=style_profile,
            )
        )

        if result.output.success:
            return result.output.polished_markdown
        else:
            # Log warning and return original
            import logging
            logging.warning(f"StyleAgent failed: {result.output.error}")
            return raw_markdown

    except Exception as e:
        import logging
        logging.warning(f"StyleAgent error: {e}")
        return raw_markdown
```

Then modify the main `run_pipeline` function to use it (around line 770, after `write_procedure_markdown`):

```python
        # After: md = write_procedure_markdown(...)

        # Apply style profile if available
        style_profile_data = get_default_style_profile(settings.db_path)
        style_profile = None
        if style_profile_data:
            style_profile = StyleProfile.from_db_dict(style_profile_data)

        if style_profile and settings.use_llm and not settings.dummy_mode:
            polished_md = _apply_style_profile(
                raw_markdown=md,
                sources=sources,
                procedure_name=procedure,
                style_profile=style_profile,
                llm=llm,
                model=settings.model,
            )
        else:
            polished_md = md

        # Use polished_md for DOCX generation
        # Change: write_procedure_docx(markdown_text=md, ...) to:
        # write_procedure_docx(markdown_text=polished_md, ...)
```

**Step 4: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/pipeline/test_style_integration.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/procedurewriter/pipeline/run.py
git add backend/tests/pipeline/test_style_integration.py
git commit -m "feat: integrate StyleAgent into pipeline with fallback"
```

---

## Task 7: Frontend StylesPage (Basic)

**Files:**
- Create: `frontend/src/pages/StylesPage.tsx`
- Modify: `frontend/src/App.tsx`

**Step 1: Create basic page structure**

Create `frontend/src/pages/StylesPage.tsx`:

```tsx
import { useState, useEffect, useCallback } from "react";

interface StyleProfile {
  id: string;
  name: string;
  description: string | null;
  is_default: boolean;
  tone_description?: string;
  target_audience?: string;
  detail_level?: string;
  original_prompt?: string;
}

export function StylesPage() {
  const [styles, setStyles] = useState<StyleProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingStyle, setEditingStyle] = useState<StyleProfile | null>(null);
  const [newPrompt, setNewPrompt] = useState("");
  const [creating, setCreating] = useState(false);

  const fetchStyles = useCallback(async () => {
    try {
      const response = await fetch("/api/styles");
      if (!response.ok) throw new Error("Failed to fetch styles");
      const data = await response.json();
      setStyles(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStyles();
  }, [fetchStyles]);

  const handleCreate = async () => {
    if (!newPrompt.trim()) return;
    setCreating(true);

    try {
      // First parse the prompt
      const parseResponse = await fetch("/api/styles/parse", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: newPrompt }),
      });

      if (!parseResponse.ok) {
        // Fallback to simple creation
        const createResponse = await fetch("/api/styles", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: "Ny Stil",
            tone_description: newPrompt,
            original_prompt: newPrompt,
          }),
        });
        if (!createResponse.ok) throw new Error("Failed to create style");
      }

      setNewPrompt("");
      fetchStyles();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Creation failed");
    } finally {
      setCreating(false);
    }
  };

  const handleSetDefault = async (styleId: string) => {
    try {
      await fetch(`/api/styles/${styleId}/set-default`, { method: "POST" });
      fetchStyles();
    } catch (err) {
      setError("Failed to set default");
    }
  };

  const handleDelete = async (styleId: string) => {
    if (!confirm("Er du sikker på at du vil slette denne stil?")) return;
    try {
      await fetch(`/api/styles/${styleId}`, { method: "DELETE" });
      fetchStyles();
    } catch (err) {
      setError("Failed to delete");
    }
  };

  if (loading) return <div className="card">Indlæser stilprofiler...</div>;
  if (error) return <div className="card error">{error}</div>;

  return (
    <div>
      <h1>Stilprofiler</h1>

      <div className="card">
        <h2>Opret ny stil</h2>
        <p className="muted">
          Beskriv din ønskede stil med naturligt sprog. F.eks.: "Skriv som en
          dansk medicinsk lærebog til medicinstuderende. Formel tone, brug
          passiv form."
        </p>
        <textarea
          value={newPrompt}
          onChange={(e) => setNewPrompt(e.target.value)}
          placeholder="Beskriv din ønskede stil..."
          rows={4}
          style={{ width: "100%", marginBottom: 12 }}
        />
        <button onClick={handleCreate} disabled={creating || !newPrompt.trim()}>
          {creating ? "Opretter..." : "Opret Stil"}
        </button>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <h2>Gemte stilprofiler</h2>
        {styles.length === 0 ? (
          <p className="muted">Ingen stilprofiler endnu.</p>
        ) : (
          <div>
            {styles.map((style) => (
              <div
                key={style.id}
                style={{
                  padding: 12,
                  border: "1px solid #ddd",
                  marginBottom: 8,
                  borderRadius: 4,
                  background: style.is_default ? "#f0f7ff" : "white",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <div>
                    <strong>{style.name}</strong>
                    {style.is_default && (
                      <span
                        style={{
                          marginLeft: 8,
                          background: "#0066cc",
                          color: "white",
                          padding: "2px 6px",
                          borderRadius: 3,
                          fontSize: 12,
                        }}
                      >
                        Standard
                      </span>
                    )}
                  </div>
                  <div>
                    {!style.is_default && (
                      <button
                        onClick={() => handleSetDefault(style.id)}
                        style={{ marginRight: 8 }}
                      >
                        Sæt som standard
                      </button>
                    )}
                    <button
                      onClick={() => handleDelete(style.id)}
                      style={{ background: "#cc0000", color: "white" }}
                    >
                      Slet
                    </button>
                  </div>
                </div>
                {style.description && (
                  <p className="muted" style={{ marginTop: 8 }}>
                    {style.description}
                  </p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
```

**Step 2: Add route to App.tsx**

Add import and route:

```tsx
import { StylesPage } from "./pages/StylesPage";

// In routes:
<Route path="/styles" element={<StylesPage />} />
```

Add navigation link (in navbar):

```tsx
<Link to="/styles">Stilprofiler</Link>
```

**Step 3: Build and verify**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 4: Commit**

```bash
git add frontend/src/pages/StylesPage.tsx frontend/src/App.tsx
git commit -m "feat: add basic StylesPage UI for managing style profiles"
```

---

## Summary

| Task | Component | Files |
|------|-----------|-------|
| 1 | Database Schema | db.py, test_style_profiles_db.py |
| 2 | StyleProfile Model | models/style_profile.py |
| 3 | StyleAgent | agents/style_agent.py |
| 4 | StyleParserAgent | agents/style_parser_agent.py |
| 5 | API Endpoints | main.py |
| 6 | Pipeline Integration | pipeline/run.py |
| 7 | Frontend UI | StylesPage.tsx |

Total: 7 tasks with full TDD approach.

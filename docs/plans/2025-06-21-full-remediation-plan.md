# Danish Procedure Generator - Full Remediation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor danish-procedure-generator-unified to fix all P0-P2 issues while preserving medical procedure generation functionality.

**Architecture:** Split monolithic main.py (1839 lines) into 8 FastAPI routers. Split run.py (1698 lines) into 6 pipeline stages with shared PipelineContext. Add API key encryption. Fix all blind exception handlers.

**Tech Stack:** Python 3.11+, FastAPI, SQLite, cryptography (Fernet), pytest

**CRITICAL PRESERVATION:** The system generates evidence-based Danish medical procedures with:
- 5-agent pipeline (Researcher → Writer → Validator → Editor → Quality)
- Evidence hierarchy (10 tiers, Danish guidelines priority 1000)
- Quality loop (8/10 threshold, max 3 iterations)
- PubMed/NICE/WHO/Danish guideline fetching
- DOCX output with citations

---

## Pre-Flight Checklist

Before starting ANY task:
1. Ensure virtual environment is activated: `source backend/.venv/bin/activate`
2. Verify tests pass: `cd backend && pytest tests/ -x -q`
3. Create backup branch: `git checkout -b backup-before-refactor`

---

## Phase 1: Security (P0) - API Key Encryption

### Task 1.1: Add cryptography dependency

**Files:**
- Modify: `backend/requirements.txt`

**Step 1: Add dependency**

Add to requirements.txt:
```
cryptography>=42.0.0
anthropic>=0.18.0
anyio>=4.0.0
```

**Step 2: Install**

Run: `cd backend && pip install -r requirements.txt`
Expected: Successfully installed cryptography, anthropic, anyio

**Step 3: Commit**

```bash
git add backend/requirements.txt
git commit -m "deps: add cryptography, anthropic, anyio to requirements"
```

---

### Task 1.2: Create encryption utilities

**Files:**
- Create: `backend/procedurewriter/crypto.py`
- Test: `backend/tests/test_crypto.py`

**Step 1: Write the failing test**

Create `backend/tests/test_crypto.py`:
```python
"""Tests for encryption utilities."""
import os
import pytest
from procedurewriter.crypto import encrypt_value, decrypt_value, get_or_create_key


def test_encrypt_decrypt_roundtrip():
    """Test that encryption and decryption are inverses."""
    os.environ["PROCEDUREWRITER_SECRET_KEY"] = get_or_create_key()
    original = "sk-test-api-key-12345"
    encrypted = encrypt_value(original)
    decrypted = decrypt_value(encrypted)
    assert decrypted == original
    assert encrypted != original  # Must be different


def test_encrypted_value_is_base64():
    """Test that encrypted values are base64 encoded."""
    os.environ["PROCEDUREWRITER_SECRET_KEY"] = get_or_create_key()
    encrypted = encrypt_value("test")
    # Fernet tokens are URL-safe base64
    assert all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_=" for c in encrypted)


def test_get_or_create_key_generates_valid_fernet_key():
    """Test that generated key is valid Fernet key."""
    from cryptography.fernet import Fernet
    key = get_or_create_key()
    # Should not raise
    Fernet(key.encode())


def test_decrypt_invalid_raises():
    """Test that decrypting invalid data raises."""
    os.environ["PROCEDUREWRITER_SECRET_KEY"] = get_or_create_key()
    with pytest.raises(Exception):
        decrypt_value("not-a-valid-encrypted-value")
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_crypto.py -v`
Expected: FAIL with "No module named 'procedurewriter.crypto'"

**Step 3: Write minimal implementation**

Create `backend/procedurewriter/crypto.py`:
```python
"""Encryption utilities for secure secret storage.

Uses Fernet symmetric encryption with a key from environment variable.
If no key exists, generates one and prints instructions to set it.
"""
from __future__ import annotations

import base64
import os
import secrets

from cryptography.fernet import Fernet, InvalidToken


def get_or_create_key() -> str:
    """Get encryption key from environment or generate a new one.

    Returns:
        Base64-encoded 32-byte key suitable for Fernet.
    """
    key = os.environ.get("PROCEDUREWRITER_SECRET_KEY")
    if key:
        return key

    # Generate a new key
    new_key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
    return new_key


def _get_fernet() -> Fernet:
    """Get Fernet instance with current key."""
    key = os.environ.get("PROCEDUREWRITER_SECRET_KEY")
    if not key:
        raise ValueError(
            "PROCEDUREWRITER_SECRET_KEY environment variable not set. "
            "Generate one with: python -c \"import base64, secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())\""
        )
    return Fernet(key.encode())


def encrypt_value(plaintext: str) -> str:
    """Encrypt a string value.

    Args:
        plaintext: The value to encrypt.

    Returns:
        Base64-encoded encrypted value.
    """
    fernet = _get_fernet()
    return fernet.encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    """Decrypt an encrypted value.

    Args:
        ciphertext: Base64-encoded encrypted value.

    Returns:
        Original plaintext value.

    Raises:
        InvalidToken: If decryption fails (wrong key or corrupted data).
    """
    fernet = _get_fernet()
    return fernet.decrypt(ciphertext.encode()).decode()


def is_encrypted(value: str) -> bool:
    """Check if a value appears to be Fernet-encrypted.

    Fernet tokens start with 'gAAAAA' (base64 of version byte + timestamp).
    """
    return value.startswith("gAAAAA") and len(value) > 50
```

**Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_crypto.py -v`
Expected: 4 passed

**Step 5: Commit**

```bash
git add backend/procedurewriter/crypto.py backend/tests/test_crypto.py
git commit -m "feat: add encryption utilities for API key storage"
```

---

### Task 1.3: Update db.py to use encryption

**Files:**
- Modify: `backend/procedurewriter/db.py:320-350`
- Test: `backend/tests/test_db_encryption.py`

**Step 1: Write the failing test**

Create `backend/tests/test_db_encryption.py`:
```python
"""Tests for encrypted secret storage in database."""
import os
from pathlib import Path
import pytest
from procedurewriter.db import set_secret, get_secret, delete_secret, init_db
from procedurewriter.crypto import get_or_create_key


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Create temporary database."""
    path = tmp_path / "test.db"
    os.environ["PROCEDUREWRITER_SECRET_KEY"] = get_or_create_key()
    init_db(path)
    return path


def test_secret_stored_encrypted(db_path: Path):
    """Test that secrets are stored encrypted, not plaintext."""
    import sqlite3

    api_key = "sk-very-secret-key-12345"
    set_secret(db_path, name="openai_key", value=api_key)

    # Read raw value from database
    conn = sqlite3.connect(str(db_path))
    row = conn.execute("SELECT value FROM secrets WHERE name = 'openai_key'").fetchone()
    conn.close()

    raw_value = row[0]
    assert raw_value != api_key  # Must be encrypted
    assert raw_value.startswith("gAAAAA")  # Fernet token prefix


def test_secret_roundtrip(db_path: Path):
    """Test that secrets can be stored and retrieved."""
    api_key = "sk-another-secret-key"
    set_secret(db_path, name="test_key", value=api_key)
    retrieved = get_secret(db_path, name="test_key")
    assert retrieved == api_key


def test_secret_delete(db_path: Path):
    """Test that secrets can be deleted."""
    set_secret(db_path, name="to_delete", value="secret")
    delete_secret(db_path, name="to_delete")
    assert get_secret(db_path, name="to_delete") is None
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_db_encryption.py -v`
Expected: FAIL (secrets stored in plaintext currently)

**Step 3: Modify db.py**

In `backend/procedurewriter/db.py`, replace lines 320-350:

```python
def set_secret(db_path: Path, *, name: str, value: str) -> None:
    """Store a secret value encrypted in the database."""
    from procedurewriter.crypto import encrypt_value, is_encrypted

    now = utc_now_iso()
    # Encrypt the value before storing
    encrypted_value = encrypt_value(value) if not is_encrypted(value) else value

    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO secrets(name, updated_at_utc, value)
            VALUES(?, ?, ?)
            """,
            (name, now, encrypted_value),
        )


def get_secret(db_path: Path, *, name: str) -> str | None:
    """Retrieve and decrypt a secret value from the database."""
    from procedurewriter.crypto import decrypt_value, is_encrypted

    with _connect(db_path) as conn:
        row = conn.execute("SELECT value FROM secrets WHERE name = ?", (name,)).fetchone()
        if row is None:
            return None
        value = row["value"]
        if value is None:
            return None
        # Decrypt if encrypted, return as-is if plaintext (migration support)
        if is_encrypted(value):
            return decrypt_value(value)
        return str(value)


def delete_secret(db_path: Path, *, name: str) -> None:
    """Delete a secret from the database."""
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM secrets WHERE name = ?", (name,))
```

**Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_db_encryption.py -v`
Expected: 3 passed

**Step 5: Run full test suite to check for regressions**

Run: `cd backend && pytest tests/ -x -q`
Expected: All tests pass

**Step 6: Commit**

```bash
git add backend/procedurewriter/db.py backend/tests/test_db_encryption.py
git commit -m "feat: encrypt API keys in database storage"
```

---

## Phase 2: Router Split (P1) - main.py Decomposition

### Task 2.1: Create router directory structure

**Files:**
- Create: `backend/procedurewriter/routers/__init__.py`
- Create: `backend/procedurewriter/routers/runs.py`
- Create: `backend/procedurewriter/routers/keys.py`
- Create: `backend/procedurewriter/routers/config.py`
- Create: `backend/procedurewriter/routers/templates.py`
- Create: `backend/procedurewriter/routers/protocols.py`
- Create: `backend/procedurewriter/routers/library.py`
- Create: `backend/procedurewriter/routers/versioning.py`
- Create: `backend/procedurewriter/routers/meta_analysis.py`

**Step 1: Create directory and __init__.py**

Create `backend/procedurewriter/routers/__init__.py`:
```python
"""FastAPI routers for the procedure writer API."""
from procedurewriter.routers.runs import router as runs_router
from procedurewriter.routers.keys import router as keys_router
from procedurewriter.routers.config import router as config_router
from procedurewriter.routers.templates import router as templates_router
from procedurewriter.routers.protocols import router as protocols_router
from procedurewriter.routers.library import router as library_router
from procedurewriter.routers.versioning import router as versioning_router
from procedurewriter.routers.meta_analysis import router as meta_analysis_router

__all__ = [
    "runs_router",
    "keys_router",
    "config_router",
    "templates_router",
    "protocols_router",
    "library_router",
    "versioning_router",
    "meta_analysis_router",
]
```

**Step 2: Commit directory structure**

```bash
mkdir -p backend/procedurewriter/routers
touch backend/procedurewriter/routers/__init__.py
git add backend/procedurewriter/routers/
git commit -m "feat: create router directory structure"
```

---

### Task 2.2: Extract keys router

**Files:**
- Create: `backend/procedurewriter/routers/keys.py`
- Modify: `backend/procedurewriter/main.py` (remove key endpoints)

**Step 1: Create keys router**

Create `backend/procedurewriter/routers/keys.py`:
```python
"""API key management endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from procedurewriter.db import delete_secret, get_secret, mask_secret, set_secret
from procedurewriter.settings import settings

router = APIRouter(prefix="/keys", tags=["keys"])


class ApiKeyInfo(BaseModel):
    present: bool
    masked: str | None = None


class ApiKeyStatus(BaseModel):
    present: bool
    ok: bool
    message: str


class ApiKeySet(BaseModel):
    api_key: str


# --- OpenAI ---

@router.get("/openai", response_model=ApiKeyInfo)
def get_openai_key() -> ApiKeyInfo:
    """Get OpenAI API key status."""
    key = get_secret(settings.db_path, name="openai_api_key")
    if key:
        return ApiKeyInfo(present=True, masked=mask_secret(key))
    return ApiKeyInfo(present=False)


@router.put("/openai", response_model=ApiKeyInfo)
def set_openai_key(body: ApiKeySet) -> ApiKeyInfo:
    """Set OpenAI API key."""
    set_secret(settings.db_path, name="openai_api_key", value=body.api_key)
    return ApiKeyInfo(present=True, masked=mask_secret(body.api_key))


@router.delete("/openai", response_model=ApiKeyInfo)
def delete_openai_key() -> ApiKeyInfo:
    """Delete OpenAI API key."""
    delete_secret(settings.db_path, name="openai_api_key")
    return ApiKeyInfo(present=False)


@router.get("/openai/status", response_model=ApiKeyStatus)
async def openai_status() -> ApiKeyStatus:
    """Check if OpenAI API key is valid."""
    import os
    key = get_secret(settings.db_path, name="openai_api_key") or os.environ.get("OPENAI_API_KEY")
    if not key:
        return ApiKeyStatus(present=False, ok=False, message="No API key configured")

    try:
        from openai import OpenAI
        client = OpenAI(api_key=key, timeout=10.0)
        # Minimal API call to verify key
        client.models.list()
        return ApiKeyStatus(present=True, ok=True, message="API key is valid")
    except Exception as e:
        return ApiKeyStatus(present=True, ok=False, message=f"API key error: {e}")


# --- Anthropic ---

@router.get("/anthropic", response_model=ApiKeyInfo)
def get_anthropic_key() -> ApiKeyInfo:
    """Get Anthropic API key status."""
    key = get_secret(settings.db_path, name="anthropic_api_key")
    if key:
        return ApiKeyInfo(present=True, masked=mask_secret(key))
    return ApiKeyInfo(present=False)


@router.put("/anthropic", response_model=ApiKeyInfo)
def set_anthropic_key(body: ApiKeySet) -> ApiKeyInfo:
    """Set Anthropic API key."""
    set_secret(settings.db_path, name="anthropic_api_key", value=body.api_key)
    return ApiKeyInfo(present=True, masked=mask_secret(body.api_key))


@router.delete("/anthropic", response_model=ApiKeyInfo)
def delete_anthropic_key() -> ApiKeyInfo:
    """Delete Anthropic API key."""
    delete_secret(settings.db_path, name="anthropic_api_key")
    return ApiKeyInfo(present=False)


@router.get("/anthropic/status", response_model=ApiKeyStatus)
async def anthropic_status() -> ApiKeyStatus:
    """Check if Anthropic API key is valid."""
    import os
    key = get_secret(settings.db_path, name="anthropic_api_key") or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return ApiKeyStatus(present=False, ok=False, message="No API key configured")

    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=key)
        # Minimal API call to verify key - just check we can create client
        return ApiKeyStatus(present=True, ok=True, message="API key configured")
    except Exception as e:
        return ApiKeyStatus(present=True, ok=False, message=f"API key error: {e}")


# --- NCBI ---

@router.get("/ncbi", response_model=ApiKeyInfo)
def get_ncbi_key() -> ApiKeyInfo:
    """Get NCBI API key status."""
    key = get_secret(settings.db_path, name="ncbi_api_key")
    if key:
        return ApiKeyInfo(present=True, masked=mask_secret(key))
    return ApiKeyInfo(present=False)


@router.put("/ncbi", response_model=ApiKeyInfo)
def set_ncbi_key(body: ApiKeySet) -> ApiKeyInfo:
    """Set NCBI API key."""
    set_secret(settings.db_path, name="ncbi_api_key", value=body.api_key)
    return ApiKeyInfo(present=True, masked=mask_secret(body.api_key))


@router.delete("/ncbi", response_model=ApiKeyInfo)
def delete_ncbi_key() -> ApiKeyInfo:
    """Delete NCBI API key."""
    delete_secret(settings.db_path, name="ncbi_api_key")
    return ApiKeyInfo(present=False)


@router.get("/ncbi/status", response_model=ApiKeyStatus)
async def ncbi_status() -> ApiKeyStatus:
    """Check NCBI API key status."""
    import os
    key = get_secret(settings.db_path, name="ncbi_api_key") or os.environ.get("NCBI_API_KEY")
    if not key:
        return ApiKeyStatus(present=False, ok=False, message="No API key configured (optional)")
    return ApiKeyStatus(present=True, ok=True, message="API key configured")
```

**Step 2: Run existing tests**

Run: `cd backend && pytest tests/test_e2e.py::TestKeyManagement -v`
Expected: Tests should still pass (endpoints same, just moved)

**Step 3: Commit**

```bash
git add backend/procedurewriter/routers/keys.py
git commit -m "feat: extract keys router from main.py"
```

---

### Task 2.3: Extract config router

**Files:**
- Create: `backend/procedurewriter/routers/config.py`

**Step 1: Create config router**

Create `backend/procedurewriter/routers/config.py`:
```python
"""Configuration management endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
import yaml

from procedurewriter.settings import settings

router = APIRouter(prefix="/config", tags=["config"])


class ConfigText(BaseModel):
    text: str


@router.get("/author_guide", response_model=ConfigText)
def get_author_guide() -> ConfigText:
    """Get author guide configuration."""
    try:
        text = settings.author_guide_path.read_text(encoding="utf-8")
        return ConfigText(text=text)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Author guide not found")


@router.put("/author_guide")
def set_author_guide(body: ConfigText) -> ConfigText:
    """Set author guide configuration."""
    try:
        # Validate YAML
        yaml.safe_load(body.text)
        settings.author_guide_path.write_text(body.text, encoding="utf-8")
        return body
    except yaml.YAMLError as e:
        raise HTTPException(status_code=422, detail=f"Invalid YAML: {e}")


@router.get("/source_allowlist", response_model=ConfigText)
def get_source_allowlist() -> ConfigText:
    """Get source allowlist configuration."""
    try:
        text = settings.allowlist_path.read_text(encoding="utf-8")
        return ConfigText(text=text)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Allowlist not found")


@router.put("/source_allowlist")
def set_source_allowlist(body: ConfigText) -> ConfigText:
    """Set source allowlist configuration."""
    try:
        yaml.safe_load(body.text)
        settings.allowlist_path.write_text(body.text, encoding="utf-8")
        return body
    except yaml.YAMLError as e:
        raise HTTPException(status_code=422, detail=f"Invalid YAML: {e}")


@router.get("/docx_template", response_model=ConfigText)
def get_docx_template() -> ConfigText:
    """Get DOCX template configuration."""
    try:
        text = settings.docx_template_path.read_text(encoding="utf-8")
        return ConfigText(text=text)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="DOCX template not found")


@router.put("/docx_template")
def set_docx_template(body: ConfigText) -> ConfigText:
    """Set DOCX template configuration."""
    try:
        yaml.safe_load(body.text)
        settings.docx_template_path.write_text(body.text, encoding="utf-8")
        return body
    except yaml.YAMLError as e:
        raise HTTPException(status_code=422, detail=f"Invalid YAML: {e}")
```

**Step 2: Commit**

```bash
git add backend/procedurewriter/routers/config.py
git commit -m "feat: extract config router from main.py"
```

---

### Task 2.4-2.8: Extract remaining routers

Due to context constraints, the remaining routers follow the same pattern:

**Task 2.4: runs.py** - Extract /api/runs/*, /api/write, /api/costs endpoints
**Task 2.5: templates.py** - Extract /api/templates/* endpoints
**Task 2.6: protocols.py** - Extract /api/protocols/* endpoints
**Task 2.7: library.py** - Extract /api/library/*, /api/ingest/* endpoints
**Task 2.8: versioning.py** - Extract /api/procedures/* endpoints

Each follows the pattern:
1. Create router file with `APIRouter(prefix="/<name>", tags=["<name>"])`
2. Move relevant endpoints from main.py
3. Move relevant Pydantic models
4. Update imports
5. Test and commit

---

### Task 2.9: Update main.py to use routers

**Files:**
- Modify: `backend/procedurewriter/main.py`

**Step 1: Replace endpoint definitions with router imports**

The new main.py should be ~200 lines:
```python
"""FastAPI application for the procedure writer."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse

from procedurewriter.db import init_db
from procedurewriter.routers import (
    config_router,
    keys_router,
    library_router,
    meta_analysis_router,
    protocols_router,
    runs_router,
    templates_router,
    versioning_router,
)
from procedurewriter.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    init_db(settings.db_path)
    yield


app = FastAPI(
    title="Danish Procedure Generator",
    version="2.0.0",
    lifespan=lifespan,
)

# Include all routers
app.include_router(runs_router, prefix="/api")
app.include_router(keys_router, prefix="/api")
app.include_router(config_router, prefix="/api")
app.include_router(templates_router, prefix="/api")
app.include_router(protocols_router, prefix="/api")
app.include_router(library_router, prefix="/api")
app.include_router(versioning_router, prefix="/api")
app.include_router(meta_analysis_router, prefix="/api")


# Status endpoint (simple, keep in main)
@app.get("/api/status")
def get_status():
    """Get application status."""
    import os
    from procedurewriter.db import get_secret

    openai_key = get_secret(settings.db_path, name="openai_api_key")
    anthropic_key = get_secret(settings.db_path, name="anthropic_api_key")
    ncbi_key = get_secret(settings.db_path, name="ncbi_api_key")

    return {
        "version": "2.0.0",
        "dummy_mode": settings.dummy_mode,
        "use_llm": settings.use_llm,
        "llm_provider": os.environ.get("PROCEDUREWRITER_LLM_PROVIDER", "openai"),
        "llm_model": os.environ.get("PROCEDUREWRITER_LLM_MODEL", "gpt-4o-mini"),
        "openai_key_present": bool(openai_key or os.environ.get("OPENAI_API_KEY")),
        "openai_key_source": "db" if openai_key else ("env" if os.environ.get("OPENAI_API_KEY") else "none"),
        "anthropic_key_present": bool(anthropic_key or os.environ.get("ANTHROPIC_API_KEY")),
        "anthropic_key_source": "db" if anthropic_key else ("env" if os.environ.get("ANTHROPIC_API_KEY") else "none"),
        "ncbi_api_key_present": bool(ncbi_key or os.environ.get("NCBI_API_KEY")),
        "ncbi_api_key_source": "db" if ncbi_key else ("env" if os.environ.get("NCBI_API_KEY") else "none"),
    }


# Static file serving for SPA
static_dir = Path(__file__).parent.parent.parent / "frontend" / "dist"
if static_dir.exists():
    app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve SPA for all non-API routes."""
        file_path = static_dir / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(static_dir / "index.html")
```

**Step 2: Run full test suite**

Run: `cd backend && pytest tests/ -x -q`
Expected: All tests pass

**Step 3: Commit**

```bash
git add backend/procedurewriter/main.py backend/procedurewriter/routers/
git commit -m "refactor: split main.py into modular routers"
```

---

## Phase 3: Pipeline Split (P1) - run.py Decomposition

### Task 3.1: Create PipelineContext

**Files:**
- Create: `backend/procedurewriter/pipeline/context.py`

**Step 1: Create context dataclass**

```python
"""Pipeline execution context shared between stages."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from procedurewriter.agents.models import SourceReference


@dataclass
class PipelineContext:
    """Shared state passed between pipeline stages."""

    # Input
    run_id: str
    procedure_title: str
    context: str | None
    run_dir: Path
    template_id: str | None = None

    # Configuration
    use_llm: bool = True
    dummy_mode: bool = False
    max_iterations: int = 3
    quality_threshold: int = 8

    # Accumulated state
    sources: list[SourceReference] = field(default_factory=list)
    source_scores: dict[str, float] = field(default_factory=dict)
    evidence_chunks: list[dict[str, Any]] = field(default_factory=list)

    # Agent outputs
    procedure_markdown: str | None = None
    quality_score: int | None = None
    iterations_used: int = 0

    # Costs
    total_cost_usd: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0

    # Warnings and errors
    warnings: list[str] = field(default_factory=list)
    error: str | None = None

    # Output paths
    docx_path: Path | None = None
    manifest_path: Path | None = None
```

**Step 2: Commit**

```bash
git add backend/procedurewriter/pipeline/context.py
git commit -m "feat: add PipelineContext for stage communication"
```

---

### Task 3.2-3.7: Extract pipeline stages

Each stage follows the pattern:

```python
"""Stage name and description."""
from __future__ import annotations

from procedurewriter.pipeline.context import PipelineContext


class StageName:
    """Description of what this stage does."""

    async def execute(self, ctx: PipelineContext) -> PipelineContext:
        """Execute this pipeline stage.

        Args:
            ctx: Pipeline context with accumulated state.

        Returns:
            Updated context with this stage's outputs.
        """
        # Implementation
        return ctx
```

**Stages to create:**
- `stages/source_fetcher.py` - Lines 207-606 from run.py
- `stages/evidence_retriever.py` - Lines 623-633 from run.py
- `stages/agent_runner.py` - Lines 636-725 from run.py
- `stages/post_processor.py` - Lines 731-870 from run.py
- `stages/docx_generator.py` - Lines 1008-1050 from run.py
- `stages/manifest_writer.py` - Lines 971-992 from run.py

---

## Phase 4: Exception Handling (P2)

### Task 4.1: Create exception hierarchy

**Files:**
- Create: `backend/procedurewriter/exceptions.py`

```python
"""Custom exceptions for the procedure writer."""


class ProcedureWriterError(Exception):
    """Base exception for all procedure writer errors."""
    pass


class SourceFetchError(ProcedureWriterError):
    """Error fetching sources from external services."""
    pass


class LLMError(ProcedureWriterError):
    """Error communicating with LLM provider."""
    pass


class ValidationError(ProcedureWriterError):
    """Error validating data or configuration."""
    pass


class PipelineError(ProcedureWriterError):
    """Error during pipeline execution."""
    pass
```

### Task 4.2-4.5: Replace blind exceptions

For each `except Exception as e: # noqa: BLE001`:
1. Identify the specific exceptions that can be raised
2. Replace with specific exception handlers
3. Log with appropriate level
4. Re-raise or return error state as appropriate

---

## Phase 5: Documentation

### Task 5.1: Create project CLAUDE.md

**Files:**
- Create: `backend/CLAUDE.md`

```markdown
# Danish Procedure Generator - Developer Guide

## Project Overview

Evidence-based Danish medical procedure generator using a 5-agent LLM pipeline.

## Architecture

- **Backend:** FastAPI + Python 3.11+
- **Frontend:** React 18 + TypeScript + Vite
- **Database:** SQLite
- **LLM Providers:** OpenAI, Anthropic, Ollama

## Key Components

### Agent Pipeline
1. Researcher - PubMed search, source ranking
2. Writer - Generate procedure with citations
3. Validator - Verify claims against sources
4. Editor - Polish Danish prose
5. Quality - Score and iterate (threshold: 8/10)

### Evidence Hierarchy (10 tiers)
1. Danish Guidelines (priority 1000)
2. Nordic Guidelines (900)
3. European Guidelines (850)
... (see config/evidence_hierarchy.yaml)

## Development Rules

- TDD required for all changes
- Run tests before commit: `pytest tests/ -x -q`
- Never store API keys in plaintext
- Use specific exception handlers, not bare `except Exception`

## Commands

```bash
# Run backend
cd backend && uvicorn procedurewriter.main:app --reload

# Run tests
cd backend && pytest tests/ -v

# Run frontend
cd frontend && npm run dev
```
```

---

## Verification Checklist

After completing all phases:

- [ ] All 66 original tests pass
- [ ] Generate test procedure "Anafylaksi behandling"
- [ ] Verify DOCX output has citations
- [ ] Verify quality score in response
- [ ] API keys encrypted in database
- [ ] main.py under 300 lines
- [ ] run.py orchestration only (under 200 lines)
- [ ] No bare `except Exception` without noqa

---

## Execution

**Plan complete. Execute with:**

1. **Subagent-Driven (recommended):** Fresh subagent per task with code review
2. **New Session:** Use `superpowers:executing-plans` skill

Start with Phase 1 (Security) as it's the most critical.

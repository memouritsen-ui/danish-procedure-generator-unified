"""
Pytest configuration for backend tests.

R6-008: Shared fixtures and configuration for all tests.
"""
import sys
import tempfile
from pathlib import Path
from typing import Any

import pytest

# Add backend directory to path for imports
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from procedurewriter.pipeline.types import Snippet


# R6-002: Register integration marker for real LLM tests
def pytest_configure(config):
    """Register custom pytest markers."""
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests requiring real LLM (deselect with '-m \"not integration\"')",
    )


# ============================================================================
# R6-008: SHARED FIXTURES FOR ALL TESTS
# ============================================================================

# --- Test Constants (R6-010: Named constants instead of magic numbers) ---
DEFAULT_SOURCE_ID = "SRC0001"
DEFAULT_CHUNK_INDEX = 0
SAMPLE_MEDICAL_TEXT_EN = "Acute asthma exacerbation treatment details."
SAMPLE_MEDICAL_TEXT_DA = "Klinisk påstand om behandling."
SAMPLE_UNRELATED_TEXT = "Completely different topic about gardening."


# --- Database Fixtures ---
@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    """Provide a temporary database path for isolated testing.

    Uses pytest's tmp_path which is automatically cleaned up after tests.
    """
    return tmp_path / "test_procedurewriter.db"


@pytest.fixture
def temp_run_dir(tmp_path: Path) -> Path:
    """Provide a temporary run directory for file-based tests."""
    run_dir = tmp_path / "runs" / "test_run_001"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


# --- Snippet Fixtures (R6-006: Fixtures instead of inline data) ---
@pytest.fixture
def sample_snippet() -> Snippet:
    """Single sample snippet for basic evidence testing."""
    return Snippet(
        source_id=DEFAULT_SOURCE_ID,
        text=SAMPLE_MEDICAL_TEXT_EN,
        location={"chunk": DEFAULT_CHUNK_INDEX},
    )


@pytest.fixture
def sample_snippet_danish() -> Snippet:
    """Danish language snippet for i18n testing (R6-007)."""
    return Snippet(
        source_id=DEFAULT_SOURCE_ID,
        text=SAMPLE_MEDICAL_TEXT_DA,
        location={"chunk": DEFAULT_CHUNK_INDEX},
    )


@pytest.fixture
def sample_snippets() -> list[Snippet]:
    """Multiple snippets for evidence report testing.

    Returns two snippets: one matching expected content, one unrelated.
    """
    return [
        Snippet(
            source_id=DEFAULT_SOURCE_ID,
            text=SAMPLE_MEDICAL_TEXT_EN,
            location={"chunk": 0},
        ),
        Snippet(
            source_id=DEFAULT_SOURCE_ID,
            text=SAMPLE_UNRELATED_TEXT,
            location={"chunk": 1},
        ),
    ]


@pytest.fixture
def snippet_factory():
    """Factory function for creating custom snippets in tests.

    Usage:
        def test_something(snippet_factory):
            snippet = snippet_factory(text="Custom text", source_id="SRC002")
    """
    def _create_snippet(
        source_id: str = DEFAULT_SOURCE_ID,
        text: str = SAMPLE_MEDICAL_TEXT_EN,
        chunk: int = DEFAULT_CHUNK_INDEX,
        **extra_location: Any,
    ) -> Snippet:
        location = {"chunk": chunk, **extra_location}
        return Snippet(source_id=source_id, text=text, location=location)

    return _create_snippet


# --- Markdown Fixtures ---
@pytest.fixture
def sample_markdown_with_citations() -> str:
    """Markdown content with source citations for evidence testing."""
    return (
        "## A\n"
        "Acute asthma exacerbation treatment. [S:SRC0001]\n"
        "Completely unrelated sentence. [S:SRC0001]\n"
    )


@pytest.fixture
def sample_markdown_danish() -> str:
    """Danish markdown content for i18n testing (R6-007)."""
    return "## A\nKlinisk påstand. [S:SRC0001]\n"


# --- Verification Result Fixtures ---
@pytest.fixture
def verification_results_contradicted() -> dict[str, Any]:
    """Verification results showing a contradicted claim."""
    return {
        "sentences": [
            {"line_no": 2, "status": "contradicted"},
        ]
    }


@pytest.fixture
def verification_results_supported() -> dict[str, Any]:
    """Verification results showing a supported claim."""
    return {
        "sentences": [
            {"line_no": 2, "status": "supported"},
        ]
    }

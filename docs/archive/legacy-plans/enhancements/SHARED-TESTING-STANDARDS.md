# Shared Testing Standards

## Session Start Checklist

```
[ ] Load skill: Skill(superpowers:using-superpowers)
[ ] Load skill: Skill(superpowers:test-driven-development)
[ ] Load skill: Skill(superpowers:verification-before-completion)
[ ] Read this document fully before writing ANY test
[ ] Read README.md for critical rules
```

---

## CRITICAL: NO DUMMY/MOCK PROHIBITION

### What is FORBIDDEN

```python
# FORBIDDEN - Mock objects
mock_source = Mock()
mock_db = MagicMock()

# FORBIDDEN - Dummy data without structure
dummy_data = {"foo": "bar"}

# FORBIDDEN - Patch decorators that bypass real logic
@patch('module.RealClass')
def test_something(mock_class):
    mock_class.return_value = Mock()

# FORBIDDEN - Skip markers without resolution
@pytest.mark.skip("Will fix later")

# FORBIDDEN - Fake implementations
class FakeDatabase:
    def query(self, sql):
        return []  # Always empty - useless
```

### What is REQUIRED

```python
# REQUIRED - Real test fixtures with actual data structures
@pytest.fixture
def real_source_fixture():
    """Real Source object with actual medical content."""
    return Source(
        id="test-src-001",
        title="Akut Anafylaksi Behandling",
        url="https://example.dk/anafylaksi",
        snippet="Adrenalin 0.3-0.5 mg i.m. gives straks ved anafylaksi grad 2+",
        content="Fuld tekst om anafylaksi behandling...",
        source_type="guideline",
        retrieved_at=datetime.now(timezone.utc),
    )

# REQUIRED - Test database with real schema
@pytest.fixture
def test_db(tmp_path):
    """Real SQLite database with actual schema."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)

    # Apply REAL migrations
    from backend.procedurewriter.db.migrations import apply_all_migrations
    apply_all_migrations(conn)

    yield conn
    conn.close()

# REQUIRED - Integration tests that exercise real code paths
def test_procedure_generation_integration(test_db, real_source_fixture):
    """Test actual procedure generation with real components."""
    pipeline = Pipeline(db=test_db)
    result = pipeline.generate(
        topic="Test Procedure",
        sources=[real_source_fixture],
    )

    assert result.markdown is not None
    assert len(result.sections) > 0
    assert "[S:" in result.markdown  # Real citations
```

---

## Test Categories

### 1. Unit Tests

**Purpose**: Test individual functions/methods in isolation

**Requirements**:
- Use real input data structures
- Assert on actual output values
- No mocking of the unit under test
- Dependencies can use test fixtures (not mocks)

```python
# Example: Testing citation extraction
def test_extract_citations_from_text():
    """Test citation extraction with real medical text."""
    text = "Adrenalin 0.5 mg i.m. [S:src-001] gives ved anafylaksi [S:src-002]."

    citations = extract_citations(text)

    assert citations == ["src-001", "src-002"]
    assert len(citations) == 2

def test_extract_citations_with_danish_abbreviations():
    """Ensure n., m., v. abbreviations don't break extraction."""
    text = "Infiltrer langs n. femoralis [S:src-003] med 10 ml lidokain."

    citations = extract_citations(text)

    assert citations == ["src-003"]
```

### 2. Integration Tests

**Purpose**: Test component interactions

**Requirements**:
- Use test database with real schema
- Exercise real API endpoints
- Test actual data flow between components
- No patching of internal methods

```python
# Example: Testing API endpoint integration
@pytest.fixture
def test_client(test_db):
    """Real FastAPI test client with real database."""
    from backend.procedurewriter.main import create_app

    app = create_app(db_path=test_db)
    return TestClient(app)

def test_procedure_create_endpoint(test_client, real_source_fixture):
    """Test POST /api/procedures with real data."""
    response = test_client.post(
        "/api/procedures",
        json={
            "topic": "Akut Anafylaksi",
            "sources": [real_source_fixture.dict()],
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["topic"] == "Akut Anafylaksi"
```

### 3. End-to-End Tests

**Purpose**: Test complete user workflows

**Requirements**:
- Real browser automation (Playwright)
- Real backend services
- Real database
- No stubbed responses

```python
# Example: E2E test for procedure creation
@pytest.mark.e2e
async def test_create_procedure_e2e(page: Page, test_server):
    """Complete workflow: create procedure via UI."""
    # Navigate to create page
    await page.goto(f"{test_server}/procedures/new")

    # Fill form with real data
    await page.fill('[data-testid="topic-input"]', "Akut Anafylaksi")
    await page.click('[data-testid="generate-button"]')

    # Wait for real generation (not mocked)
    await page.wait_for_selector('[data-testid="procedure-content"]', timeout=60000)

    # Verify real content
    content = await page.text_content('[data-testid="procedure-content"]')
    assert "Adrenalin" in content  # Real medical content
    assert "[S:" in content  # Real citations
```

---

## Test Fixtures Standards

### Source Fixtures

```python
# fixtures/sources.py

from datetime import datetime, timezone
from backend.procedurewriter.models import Source

# Real Danish medical sources for testing
ANAFYLAKSI_SOURCE = Source(
    id="test-anafylaksi-001",
    title="Dansk Anafylaksi Retningslinje 2024",
    url="https://dsam.dk/anafylaksi",
    snippet="Adrenalin er førstevalg ved akut anafylaksi. Dosis: 0.3-0.5 mg i.m.",
    content="""
    # Akut Anafylaksi Behandling

    ## Indikation
    Anafylaksi grad 2+ med systemiske symptomer.

    ## Behandling
    1. Adrenalin 0.3-0.5 mg i.m. i låret
    2. Gentages efter 5-15 min ved manglende effekt
    3. I.v. adgang og væske ved hypotension

    ## Opfølgning
    Observation minimum 4-6 timer.
    """,
    source_type="guideline",
    retrieved_at=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
    evidence_level="high",
    publication_date=datetime(2024, 1, 1),
)

NERVEBLOKADE_SOURCE = Source(
    id="test-nerve-001",
    title="Ultralydsvejledt Nerveblokade",
    url="https://dasaim.dk/nerveblokade",
    snippet="N. femoralis lokaliseres lateralt for a. femoralis.",
    content="""
    # Femoralnerveblokade

    ## Anatomi
    N. femoralis ligger lateralt for a. femoralis, under fascia iliaca.

    ## Teknik
    1. Identificer a. femoralis med ultralyd
    2. Lokaliser n. femoralis lateralt
    3. Infiltrer 15-20 ml lokalanæstetikum

    ## Komplikationer
    Nerveskade, intravaskulær injektion.
    """,
    source_type="guideline",
    retrieved_at=datetime(2024, 2, 1, 14, 0, 0, tzinfo=timezone.utc),
)
```

### Database Fixtures

```python
# fixtures/database.py

import sqlite3
from pathlib import Path
import pytest

@pytest.fixture
def test_db(tmp_path):
    """
    Real SQLite database with actual schema.

    This creates a fresh database for each test with the
    real production schema applied via migrations.
    """
    db_path = tmp_path / "test_procedures.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Apply all production migrations
    from backend.procedurewriter.db.migrations import apply_all_migrations
    apply_all_migrations(conn)

    yield conn

    conn.close()

@pytest.fixture
def seeded_db(test_db):
    """
    Database pre-populated with test data.

    Use this when tests need existing data to operate on.
    """
    from tests.fixtures.sources import ANAFYLAKSI_SOURCE, NERVEBLOKADE_SOURCE

    # Insert test sources
    test_db.execute(
        """
        INSERT INTO sources (id, title, url, content, source_type, retrieved_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            ANAFYLAKSI_SOURCE.id,
            ANAFYLAKSI_SOURCE.title,
            ANAFYLAKSI_SOURCE.url,
            ANAFYLAKSI_SOURCE.content,
            ANAFYLAKSI_SOURCE.source_type,
            ANAFYLAKSI_SOURCE.retrieved_at.isoformat(),
        ),
    )

    test_db.commit()
    yield test_db
```

### Pipeline Fixtures

```python
# fixtures/pipeline.py

import pytest
from backend.procedurewriter.pipeline import Pipeline

@pytest.fixture
def test_pipeline(test_db):
    """
    Real Pipeline instance with test database.

    This uses the actual Pipeline class, not a mock.
    """
    return Pipeline(
        db=test_db,
        llm_provider="test",  # Uses deterministic test LLM
    )

@pytest.fixture
def test_llm():
    """
    Deterministic LLM for testing.

    This is NOT a mock - it's a real LLM adapter that returns
    predictable responses for testing purposes.
    """
    from backend.procedurewriter.llm.test_adapter import TestLLMAdapter

    return TestLLMAdapter(
        responses={
            "section:indikation": "Anvendes ved akut anafylaksi grad 2+ [S:test-001].",
            "section:kontraindikation": "Ingen absolutte kontraindikationer [S:test-001].",
            "section:procedure": "1. Adrenalin 0.5 mg i.m. [S:test-001]\n2. Gentag efter 5 min [S:test-001].",
        }
    )
```

---

## Test Naming Conventions

```python
# Pattern: test_<what>_<scenario>_<expected_outcome>

# Good names:
def test_extract_citations_with_multiple_sources_returns_all():
    pass

def test_procedure_create_with_invalid_topic_raises_validation_error():
    pass

def test_source_scoring_with_high_evidence_returns_score_above_80():
    pass

# Bad names:
def test_citations():  # Too vague
    pass

def test_it_works():  # Meaningless
    pass

def test_procedure():  # What about it?
    pass
```

---

## Assertion Standards

### Use Specific Assertions

```python
# WRONG - Vague assertion
assert result  # What are we checking?

# RIGHT - Specific assertion
assert result.status == "success"
assert len(result.sections) == 5
assert "Adrenalin" in result.content

# WRONG - Generic comparison
assert result == expected  # Hard to debug when it fails

# RIGHT - Decomposed assertions
assert result.id == expected.id
assert result.topic == expected.topic
assert result.created_at is not None
```

### Assert Error Cases Properly

```python
# Testing for expected exceptions
def test_invalid_source_raises_validation_error():
    """Invalid source should raise ValidationError with message."""
    invalid_source = Source(id="", title="", url="not-a-url")

    with pytest.raises(ValidationError) as exc_info:
        validate_source(invalid_source)

    assert "url" in str(exc_info.value).lower()
    assert "invalid" in str(exc_info.value).lower()
```

### Assert Database State

```python
def test_procedure_save_persists_to_database(test_db):
    """Saved procedure should exist in database."""
    procedure = create_test_procedure()

    save_procedure(procedure, db=test_db)

    # Verify by querying database directly
    cursor = test_db.execute(
        "SELECT * FROM procedures WHERE id = ?",
        (procedure.id,)
    )
    row = cursor.fetchone()

    assert row is not None
    assert row["topic"] == procedure.topic
    assert row["content"] == procedure.markdown
```

---

## Test Coverage Requirements

### Minimum Coverage by Component

| Component | Minimum Coverage | Focus Areas |
|-----------|------------------|-------------|
| Pipeline | 80% | All generation paths, error handling |
| API Endpoints | 90% | All routes, validation, error responses |
| Database Operations | 85% | CRUD, migrations, constraints |
| Source Processing | 85% | Citation extraction, scoring |
| Text Processing | 90% | Abbreviations, formatting |
| Frontend Components | 70% | User interactions, state changes |

### Coverage Commands

```bash
# Run with coverage
pytest --cov=backend/procedurewriter --cov-report=html

# Enforce minimum coverage
pytest --cov=backend/procedurewriter --cov-fail-under=80

# Check specific module
pytest --cov=backend/procedurewriter/pipeline --cov-report=term-missing
```

---

## Test Organization

### Directory Structure

```
tests/
├── conftest.py                  # Shared fixtures
├── fixtures/
│   ├── __init__.py
│   ├── sources.py               # Source test data
│   ├── procedures.py            # Procedure test data
│   ├── database.py              # Database fixtures
│   └── pipeline.py              # Pipeline fixtures
├── unit/
│   ├── test_text_units.py       # Text processing tests
│   ├── test_citations.py        # Citation tests
│   ├── test_scoring.py          # Scoring tests
│   └── test_validation.py       # Validation tests
├── integration/
│   ├── test_api_procedures.py   # API endpoint tests
│   ├── test_api_sources.py      # Source API tests
│   ├── test_pipeline.py         # Pipeline integration
│   └── test_database.py         # Database operations
└── e2e/
    ├── test_procedure_flow.py   # Full procedure creation
    ├── test_source_flow.py      # Source management
    └── conftest.py              # E2E specific fixtures
```

### Test File Template

```python
"""
Tests for [module name].

These tests verify [what this module does].

Fixtures used:
- test_db: Real SQLite database with schema
- real_source_fixture: Real Source object

NO MOCKS ALLOWED - All tests use real implementations.
"""

import pytest
from datetime import datetime, timezone

from backend.procedurewriter.module import function_under_test
from tests.fixtures.sources import ANAFYLAKSI_SOURCE


class TestFunctionUnderTest:
    """Tests for function_under_test."""

    def test_basic_operation(self, test_db):
        """Test basic functionality with standard input."""
        result = function_under_test(input_data)

        assert result is not None
        assert result.status == "success"

    def test_edge_case_empty_input(self, test_db):
        """Empty input should raise ValueError."""
        with pytest.raises(ValueError):
            function_under_test([])

    def test_danish_content_handling(self, test_db):
        """Danish characters and abbreviations should be preserved."""
        danish_input = "Undersøg n. femoralis ved blokade"

        result = function_under_test(danish_input)

        assert "n. femoralis" in result.content
```

---

## Enhancement-Specific Test Requirements

### Enhancement 1: SSE Streaming

```python
# Required tests for SSE
def test_sse_connection_established():
    """SSE endpoint should accept connection and send initial event."""

def test_sse_pipeline_events_streamed():
    """All pipeline events should stream to client in order."""

def test_sse_connection_cleanup_on_error():
    """SSE should clean up on pipeline error."""

def test_sse_reconnection_resumes_from_last_event():
    """Reconnection should continue from last event ID."""
```

### Enhancement 2: Source Scoring

```python
# Required tests for source scoring
def test_evidence_level_scoring():
    """Different evidence levels should produce different scores."""

def test_recency_scoring():
    """Newer sources should score higher."""

def test_composite_score_calculation():
    """Composite score should weight all factors correctly."""

def test_score_affects_citation_priority():
    """Higher scored sources should appear first in citations."""
```

### Enhancement 3: Versioning

```python
# Required tests for versioning
def test_version_created_on_save():
    """Saving procedure should create new version."""

def test_diff_calculation_accurate():
    """Diff should show exact changes between versions."""

def test_version_rollback_restores_content():
    """Rollback should restore exact previous content."""

def test_version_history_complete():
    """All versions should be retrievable in order."""
```

### Enhancement 4: Templates

```python
# Required tests for templates
def test_template_crud_operations():
    """Templates should be creatable, readable, updatable, deletable."""

def test_template_applied_to_procedure():
    """Template sections should appear in generated procedure."""

def test_template_validation():
    """Invalid templates should be rejected with clear errors."""

def test_default_template_exists():
    """System should always have a default template."""
```

### Enhancement 5: Validation

```python
# Required tests for validation
def test_dosing_conflict_detected():
    """Conflicting dosing should be flagged."""

def test_timing_conflict_detected():
    """Timing conflicts should be detected."""

def test_protocol_reference_linked():
    """Procedure should link to relevant protocols."""

def test_validation_report_complete():
    """Validation report should cover all checked items."""
```

---

## Running Tests

### Commands

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_citations.py

# Run specific test class
pytest tests/unit/test_citations.py::TestCitationExtraction

# Run specific test
pytest tests/unit/test_citations.py::TestCitationExtraction::test_multiple_citations

# Run with verbose output
pytest -v

# Run and stop on first failure
pytest -x

# Run tests matching pattern
pytest -k "citation"

# Run only unit tests
pytest tests/unit/

# Run only integration tests
pytest tests/integration/

# Run only e2e tests
pytest tests/e2e/ --e2e
```

### CI Configuration

```yaml
# .github/workflows/tests.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt

      - name: Run unit tests
        run: pytest tests/unit/ --cov=backend/procedurewriter --cov-fail-under=80

      - name: Run integration tests
        run: pytest tests/integration/

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

---

## Session Handoff Notes

When handing off to another session:

1. Document which tests are passing/failing
2. Note any test fixtures that need updating
3. List any new test requirements discovered
4. Update coverage numbers in README.md

---

## Status

| Aspect | Status |
|--------|--------|
| Document created | Completed |
| Fixtures implemented | NOT STARTED |
| Unit test structure | NOT STARTED |
| Integration test structure | NOT STARTED |
| E2E test structure | NOT STARTED |
| CI configuration | NOT STARTED |

---

## Last Updated

- **Date**: 2024-12-18
- **By**: Claude (documentation phase)
- **Changes**: Initial creation of shared testing standards

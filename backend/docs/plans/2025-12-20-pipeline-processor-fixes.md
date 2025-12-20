# Pipeline Processor Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix 5 critical bugs in Phase 5 Pipeline Processor that cause content flattening, orphaned step numbers, and missing workflow patterns.

**Architecture:** Modify `processor.py` to preserve document structure and `workflow_filter.py` to catch additional workflow patterns. Add step renumbering logic after filtering.

**Tech Stack:** Python 3.11+, regex, pytest

---

## Critical Issues to Fix

| # | Issue | Location | Severity |
|---|-------|----------|----------|
| 1 | Content flattening - newlines lost | `processor.py:134` | CRITICAL |
| 2 | Orphaned step numbers ("2.", "4.") | `processor.py:130` | CRITICAL |
| 3 | Step sequence not renumbered | `processor.py` (missing) | HIGH |
| 4 | Missing workflow patterns | `workflow_filter.py` | MEDIUM |
| 5 | Markdown structure not preserved | `processor.py` | HIGH |

---

## Task 1: Fix Content Flattening (Line Breaks Lost)

**Files:**
- Modify: `procedurewriter/pipeline/processor.py:130-136`
- Test: `tests/test_pipeline_processor.py`

**Step 1: Write the failing test**

```python
# Add to tests/test_pipeline_processor.py

class TestPipelineProcessorPreservesStructure:
    """Test that processor preserves document structure."""

    def test_preserves_line_breaks(self):
        """Processor should preserve line breaks in filtered content."""
        from procedurewriter.pipeline.processor import PipelineProcessor

        processor = PipelineProcessor()

        content = """Identificer 5. interkostalrum.
Marker triangle of safety.
Indsæt nålen i 45 graders vinkel."""

        result = processor.process("pleuradræn", content)

        # Line breaks should be preserved
        assert "\n" in result.filtered_content
        lines = result.filtered_content.strip().split("\n")
        assert len(lines) >= 3
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_pipeline_processor.py::TestPipelineProcessorPreservesStructure::test_preserves_line_breaks -v`
Expected: FAIL - content is joined with spaces, no newlines

**Step 3: Write minimal implementation**

```python
# processor.py - modify process() method around line 130-136

# BEFORE (BUG):
# sentences = re.split(r"(?<=[.!?])\s+", clinical_content.strip())
# ...
# filtered_content = " ".join(deduped_sentences)

# AFTER (FIX):
# Split by actual line breaks first, then process each line
lines = clinical_content.strip().split("\n")
processed_lines = []
for line in lines:
    line = line.strip()
    if line:
        processed_lines.append(line)

if processed_lines:
    deduped_lines = self._deduplicator.deduplicate(processed_lines)
    filtered_content = "\n".join(deduped_lines)
else:
    filtered_content = ""
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_pipeline_processor.py::TestPipelineProcessorPreservesStructure::test_preserves_line_breaks -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_pipeline_processor.py procedurewriter/pipeline/processor.py
git commit -m "fix: preserve line breaks in pipeline processor

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 2: Fix Orphaned Step Numbers

**Files:**
- Modify: `procedurewriter/pipeline/workflow_filter.py`
- Test: `tests/test_workflow_filter.py`

**Step 1: Write the failing test**

```python
# Add to tests/test_workflow_filter.py

class TestWorkflowFilterPreservesStepNumbers:
    """Test that workflow filter handles numbered steps correctly."""

    def test_keeps_step_number_with_clinical_content(self):
        """Step numbers should stay with their content."""
        from procedurewriter.pipeline.workflow_filter import WorkflowFilter

        wf = WorkflowFilter()

        content = "2. Identificer 5. interkostalrum."
        clinical, workflow = wf.filter_workflow_content(content)

        # The "2." should stay with the clinical content
        assert "2." in clinical or "Identificer" in clinical
        # Should NOT have orphaned "2." in workflow
        assert clinical.strip() != ""

    def test_removes_step_number_with_workflow_content(self):
        """When entire step is workflow, remove the number too."""
        from procedurewriter.pipeline.workflow_filter import WorkflowFilter

        wf = WorkflowFilter()

        content = "5. Ring til bagvagt ved komplikationer."
        clinical, workflow = wf.filter_workflow_content(content)

        # Entire step is workflow, so nothing clinical remains
        assert "Ring til bagvagt" not in clinical
        # Workflow should contain the full step
        assert "bagvagt" in workflow.lower()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_workflow_filter.py::TestWorkflowFilterPreservesStepNumbers -v`
Expected: FAIL - current implementation splits at "2." creating orphaned numbers

**Step 3: Write minimal implementation**

```python
# workflow_filter.py - modify filter_workflow_content() method

def filter_workflow_content(self, content: str) -> tuple[str, str]:
    """Filter workflow content from clinical content.

    Handles numbered steps properly - if a step is workflow,
    the entire step including the number is removed.
    """
    clinical_parts = []
    workflow_parts = []

    # Split by lines to preserve structure
    lines = content.strip().split("\n")

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Check if this line is workflow content
        is_workflow = self._is_workflow_line(line)

        if is_workflow:
            workflow_parts.append(line)
        else:
            clinical_parts.append(line)

    return "\n".join(clinical_parts), "\n".join(workflow_parts)

def _is_workflow_line(self, line: str) -> bool:
    """Check if a line contains workflow patterns."""
    # Remove step number prefix for pattern matching
    text_without_number = re.sub(r"^\d+\.\s*", "", line)

    for pattern_name, pattern in self._patterns:
        if pattern.search(text_without_number):
            return True
    return False
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_workflow_filter.py::TestWorkflowFilterPreservesStepNumbers -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_workflow_filter.py procedurewriter/pipeline/workflow_filter.py
git commit -m "fix: handle numbered steps correctly in workflow filter

Entire steps are now removed together with their numbers when
the step content is workflow. Clinical step numbers preserved.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 3: Add Step Renumbering After Filtering

**Files:**
- Modify: `procedurewriter/pipeline/processor.py`
- Test: `tests/test_pipeline_processor.py`

**Step 1: Write the failing test**

```python
# Add to tests/test_pipeline_processor.py

class TestPipelineProcessorRenumbering:
    """Test that processor renumbers steps after filtering."""

    def test_renumbers_steps_after_workflow_removal(self):
        """Steps should be renumbered sequentially after filtering."""
        from procedurewriter.pipeline.processor import PipelineProcessor

        processor = PipelineProcessor()

        content = """1. Identificer 5. interkostalrum.
2. Ring til bagvagt ved komplikationer.
3. Marker triangle of safety.
4. Følg lokal retningslinje.
5. Indsæt nålen."""

        result = processor.process("pleuradræn", content)

        # After removing steps 2 and 4 (workflow), should renumber to 1, 2, 3
        lines = result.filtered_content.strip().split("\n")
        step_numbers = []
        for line in lines:
            match = re.match(r"^(\d+)\.", line.strip())
            if match:
                step_numbers.append(int(match.group(1)))

        # Should be sequential: 1, 2, 3
        assert step_numbers == [1, 2, 3]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_pipeline_processor.py::TestPipelineProcessorRenumbering -v`
Expected: FAIL - steps remain 1, 3, 5 instead of 1, 2, 3

**Step 3: Write minimal implementation**

```python
# processor.py - add _renumber_steps() method

def _renumber_steps(self, content: str) -> str:
    """Renumber steps sequentially after filtering.

    Handles patterns like:
    - "1. Step text"
    - "1) Step text"
    """
    lines = content.split("\n")
    result_lines = []
    current_step = 1

    for line in lines:
        # Match numbered step patterns
        match = re.match(r"^(\d+)([.\)])\s*(.*)$", line.strip())
        if match:
            separator = match.group(2)  # "." or ")"
            text = match.group(3)
            result_lines.append(f"{current_step}{separator} {text}")
            current_step += 1
        else:
            result_lines.append(line)

    return "\n".join(result_lines)
```

Then call it in process():
```python
# After deduplication, before returning
filtered_content = self._renumber_steps(filtered_content)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_pipeline_processor.py::TestPipelineProcessorRenumbering -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_pipeline_processor.py procedurewriter/pipeline/processor.py
git commit -m "feat: renumber steps sequentially after workflow filtering

Steps are now renumbered 1, 2, 3... after workflow steps are removed,
preventing gaps like 1, 3, 5.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 4: Add Missing Workflow Patterns

**Files:**
- Modify: `procedurewriter/pipeline/workflow_filter.py`
- Test: `tests/test_workflow_filter.py`

**Step 1: Write the failing test**

```python
# Add to tests/test_workflow_filter.py

class TestWorkflowFilterMissingPatterns:
    """Test that new workflow patterns are detected."""

    def test_detects_kontakt_anaestesi(self):
        """Should detect 'kontakt anæstesi' as workflow."""
        from procedurewriter.pipeline.workflow_filter import WorkflowFilter

        wf = WorkflowFilter()

        content = "Kontakt anæstesi ved sedationsbehov."
        clinical, workflow = wf.filter_workflow_content(content)

        assert "anæstesi" in workflow.lower() or "anaestesi" in workflow.lower()
        assert clinical.strip() == "" or "anæstesi" not in clinical.lower()

    def test_detects_aftal_med_teamet(self):
        """Should detect 'aftal med teamet' as workflow."""
        from procedurewriter.pipeline.workflow_filter import WorkflowFilter

        wf = WorkflowFilter()

        content = "Aftal med teamet om patientovervågning."
        clinical, workflow = wf.filter_workflow_content(content)

        assert "teamet" in workflow.lower()
        assert clinical.strip() == "" or "teamet" not in clinical.lower()

    def test_detects_aftal_rollefordeling(self):
        """Should detect 'aftal rollefordeling' as workflow."""
        from procedurewriter.pipeline.workflow_filter import WorkflowFilter

        wf = WorkflowFilter()

        content = "Aftal rollefordeling med sygeplejepersonale."
        clinical, workflow = wf.filter_workflow_content(content)

        assert "rollefordeling" in workflow.lower()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_workflow_filter.py::TestWorkflowFilterMissingPatterns -v`
Expected: FAIL - these patterns not detected

**Step 3: Write minimal implementation**

```python
# workflow_filter.py - add to _patterns list

# Add these patterns to the existing pattern list:
("kontakt_anaestesi", re.compile(r"kontakt\s+an[æa]stesi", re.IGNORECASE)),
("aftal_med_teamet", re.compile(r"aftal\s+(med\s+)?teamet", re.IGNORECASE)),
("aftal_rollefordeling", re.compile(r"aftal\s+rollefordeling", re.IGNORECASE)),
("aftal_generic", re.compile(r"aftal\s+\w+\s+(med|om)", re.IGNORECASE)),
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_workflow_filter.py::TestWorkflowFilterMissingPatterns -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_workflow_filter.py procedurewriter/pipeline/workflow_filter.py
git commit -m "feat: add missing workflow patterns

Added detection for:
- kontakt anæstesi
- aftal med teamet
- aftal rollefordeling

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 5: Preserve Markdown Structure

**Files:**
- Modify: `procedurewriter/pipeline/processor.py`
- Test: `tests/test_pipeline_processor.py`

**Step 1: Write the failing test**

```python
# Add to tests/test_pipeline_processor.py

class TestPipelineProcessorMarkdownPreservation:
    """Test that processor preserves markdown structure."""

    def test_preserves_markdown_headings(self):
        """Markdown headings should be preserved."""
        from procedurewriter.pipeline.processor import PipelineProcessor

        processor = PipelineProcessor()

        content = """## Fremgangsmåde
1. Identificer 5. interkostalrum.
2. Marker triangle of safety.

## Komplikationer
- Blødning
- Infektion"""

        result = processor.process("pleuradræn", content)

        assert "## Fremgangsmåde" in result.filtered_content
        assert "## Komplikationer" in result.filtered_content

    def test_preserves_bullet_points(self):
        """Bullet points should be preserved."""
        from procedurewriter.pipeline.processor import PipelineProcessor

        processor = PipelineProcessor()

        content = """Indikationer:
- Pneumothorax
- Pleuraeffusion
- Hæmothorax"""

        result = processor.process("pleuradræn", content)

        assert result.filtered_content.count("-") >= 3
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_pipeline_processor.py::TestPipelineProcessorMarkdownPreservation -v`
Expected: FAIL - markdown structure is lost

**Step 3: Write minimal implementation**

```python
# processor.py - modify process() to preserve markdown

def process(self, procedure_name: str, content: str) -> ProcessingResult:
    """Process content through the full pipeline, preserving structure."""

    # Split content into structural blocks (headings, paragraphs)
    blocks = self._split_into_blocks(content)

    filtered_blocks = []
    all_workflow_removed = []

    for block in blocks:
        if block.startswith("##") or block.startswith("#"):
            # Preserve headings
            filtered_blocks.append(block)
        else:
            # Process content block
            clinical, workflow = self._workflow_filter.filter_workflow_content(block)
            if clinical.strip():
                filtered_blocks.append(clinical.strip())
            if workflow.strip():
                all_workflow_removed.extend(workflow.strip().split("\n"))

    filtered_content = "\n\n".join(filtered_blocks)

    # Deduplicate within the filtered content
    lines = filtered_content.split("\n")
    deduped = self._deduplicator.deduplicate(
        [l for l in lines if l.strip()]
    )
    filtered_content = "\n".join(deduped)

    # Renumber steps
    filtered_content = self._renumber_steps(filtered_content)

    # ... rest of validation and scoring

def _split_into_blocks(self, content: str) -> list[str]:
    """Split content into structural blocks."""
    blocks = []
    current_block = []

    for line in content.split("\n"):
        if line.startswith("#"):
            # Save previous block
            if current_block:
                blocks.append("\n".join(current_block))
                current_block = []
            blocks.append(line)
        elif line.strip() == "":
            # Empty line ends a block
            if current_block:
                blocks.append("\n".join(current_block))
                current_block = []
        else:
            current_block.append(line)

    if current_block:
        blocks.append("\n".join(current_block))

    return blocks
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_pipeline_processor.py::TestPipelineProcessorMarkdownPreservation -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_pipeline_processor.py procedurewriter/pipeline/processor.py
git commit -m "feat: preserve markdown structure through pipeline

Headings (##), bullet points (-), and paragraph structure
are now preserved through the filtering pipeline.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Final Verification

**Step 1: Run all tests**

```bash
pytest tests/test_pipeline_processor.py tests/test_workflow_filter.py -v
```
Expected: All tests PASS

**Step 2: Run detailed quality analysis**

```bash
python test_run_detailed.py
```
Expected:
- No "Line breaks lost" issues
- No "Orphaned step numbers" issues
- No "Step sequence broken" issues
- All quality scores ≥ 0.7 for good clinical content

**Step 3: Final commit**

```bash
git add -A
git commit -m "test: verify all pipeline processor fixes work together

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Summary

| Task | Description | Estimated Effort |
|------|-------------|------------------|
| 1 | Fix content flattening | 15 min |
| 2 | Fix orphaned step numbers | 20 min |
| 3 | Add step renumbering | 15 min |
| 4 | Add missing workflow patterns | 10 min |
| 5 | Preserve markdown structure | 25 min |

**Total: ~85 minutes of implementation work**

Each task follows TDD: write failing test → verify failure → implement fix → verify pass → commit.

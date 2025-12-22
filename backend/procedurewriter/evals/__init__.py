"""Evaluation suite for the auditable procedure system.

This module provides:
- Linter: Abstract base class for all lint checks
- LintContext: Data container for lint input
- Individual linter implementations for each issue type
"""

from procedurewriter.evals.citation import CitationIntegrityLinter
from procedurewriter.evals.linter import Linter, LintContext

__all__ = ["Linter", "LintContext", "CitationIntegrityLinter"]

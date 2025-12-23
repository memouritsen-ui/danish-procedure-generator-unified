"""
Pytest configuration for backend tests.

R6-008: Shared fixtures and configuration for all tests.
"""
import sys
from pathlib import Path

import pytest

# Add backend directory to path for imports
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))


# R6-002: Register integration marker for real LLM tests
def pytest_configure(config):
    """Register custom pytest markers."""
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests requiring real LLM (deselect with '-m \"not integration\"')",
    )

from __future__ import annotations

import pytest

from procedurewriter.pipeline.evidence import EvidencePolicyError, enforce_evidence_policy


def test_enforce_evidence_policy_warn_no_raise() -> None:
    report = {
        "unsupported_count": 1,
        "sentences": [{"supported": False, "line_no": 1, "text": "X [S:SRC0001]"}],
    }
    enforce_evidence_policy(report, policy="warn")


def test_enforce_evidence_policy_strict_raises() -> None:
    report = {
        "unsupported_count": 2,
        "sentences": [
            {"supported": False, "line_no": 1, "text": "A [S:SRC0001]"},
            {"supported": True, "line_no": 2, "text": "B [S:SRC0001]"},
            {"supported": False, "line_no": 3, "text": "C [S:SRC0002]"},
        ],
    }
    with pytest.raises(EvidencePolicyError):
        enforce_evidence_policy(report, policy="strict")

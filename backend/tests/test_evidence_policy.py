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


# ============================================================================
# GPS INTEGRATION TESTS (P6-007)
# Per GRADE methodology, GPS (Good Practice Statements) are exempt from
# evidence requirements - statements where the inverse sounds absurd.
# ============================================================================


def test_gps_sentences_pass_strict_policy() -> None:
    """GPS sentences should be exempt from STRICT evidence policy.

    Per GRADE, a statement like 'Vurder patientens luftveje' (Assess airway)
    is a Good Practice Statement because 'Don't assess airway' is absurd.
    """
    report = {
        "unsupported_count": 0,  # GPS aren't counted as unsupported
        "gps_count": 3,
        "sentences": [
            {
                "supported": True,
                "gps_exempt": True,
                "line_no": 1,
                "text": "Vurder patientens luftveje. [S:SRC0001]",
                "sentence_type": "gps",
            },
            {
                "supported": True,
                "gps_exempt": True,
                "line_no": 2,
                "text": "Tjek vitale parametre. [S:SRC0001]",
                "sentence_type": "gps",
            },
            {
                "supported": True,
                "gps_exempt": True,
                "line_no": 3,
                "text": "Dokumenter behandlingen. [S:SRC0001]",
                "sentence_type": "gps",
            },
        ],
    }
    # Should not raise - all sentences are GPS (exempt)
    enforce_evidence_policy(report, policy="strict")


def test_gps_plus_supported_therapeutic_passes_strict() -> None:
    """A mix of GPS + supported therapeutic claims should pass STRICT."""
    report = {
        "unsupported_count": 0,
        "gps_count": 2,
        "sentences": [
            {
                "supported": True,
                "gps_exempt": True,
                "line_no": 1,
                "text": "Vurder patientens luftveje. [S:SRC0001]",
                "sentence_type": "gps",
            },
            {
                "supported": True,
                "gps_exempt": False,
                "line_no": 2,
                "text": "Giv adrenalin 0,3 mg IM. [S:SRC0002]",
                "sentence_type": "therapeutic",
            },
            {
                "supported": True,
                "gps_exempt": True,
                "line_no": 3,
                "text": "Observer patienten. [S:SRC0001]",
                "sentence_type": "gps",
            },
        ],
    }
    # Should pass - GPS exempt + therapeutic is supported
    enforce_evidence_policy(report, policy="strict")


def test_gps_plus_unsupported_therapeutic_fails_strict() -> None:
    """GPS exemption doesn't save unsupported therapeutic claims.

    If a procedure has GPS + an unsupported drug claim, it should still fail.
    Only the GPS sentences are exempt.
    """
    report = {
        "unsupported_count": 1,
        "gps_count": 2,
        "sentences": [
            {
                "supported": True,
                "gps_exempt": True,
                "line_no": 1,
                "text": "Vurder patientens luftveje. [S:SRC0001]",
                "sentence_type": "gps",
            },
            {
                "supported": False,  # UNSUPPORTED - should fail
                "gps_exempt": False,
                "line_no": 2,
                "text": "Giv adrenalin 0,3 mg IM. [S:SRC0002]",
                "sentence_type": "therapeutic",
            },
            {
                "supported": True,
                "gps_exempt": True,
                "line_no": 3,
                "text": "Dokumenter behandlingen. [S:SRC0001]",
                "sentence_type": "gps",
            },
        ],
    }
    # Should fail - therapeutic claim is unsupported
    with pytest.raises(EvidencePolicyError) as exc_info:
        enforce_evidence_policy(report, policy="strict")
    assert "unsupported" in str(exc_info.value).lower()


def test_strict_error_message_notes_gps_exemption() -> None:
    """Error message should note how many GPS were exempt."""
    report = {
        "unsupported_count": 1,
        "gps_count": 3,
        "sentences": [
            {"supported": True, "gps_exempt": True, "line_no": 1, "text": "GPS1"},
            {"supported": True, "gps_exempt": True, "line_no": 2, "text": "GPS2"},
            {"supported": True, "gps_exempt": True, "line_no": 3, "text": "GPS3"},
            {
                "supported": False,
                "gps_exempt": False,
                "line_no": 4,
                "text": "Unsupported claim [S:SRC0001]",
                "sentence_type": "therapeutic",
            },
        ],
    }
    with pytest.raises(EvidencePolicyError) as exc_info:
        enforce_evidence_policy(report, policy="strict")
    # Error message should mention GPS exemptions
    assert "3 GPS" in str(exc_info.value) or "GPS" in str(exc_info.value)

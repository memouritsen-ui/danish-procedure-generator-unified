import pytest

from procedurewriter.pipeline.citations import CitationValidationError, validate_citations


def test_citation_validator_passes_with_known_source():
    md = "## Afsnit\nDette er en sætning. [S:SRC0001]\n"
    validate_citations(md, valid_source_ids={"SRC0001"})


def test_citation_validator_fails_missing_citation():
    md = "## Afsnit\nDette er en sætning uden citation.\n"
    with pytest.raises(CitationValidationError):
        validate_citations(md, valid_source_ids={"SRC0001"})


def test_citation_validator_fails_unknown_source_id():
    md = "Dette er en sætning. [S:UNKNOWN]\n"
    with pytest.raises(CitationValidationError):
        validate_citations(md, valid_source_ids={"SRC0001"})


def test_citation_validator_allows_number_marker_on_own_line():
    md = "## Afsnit\n1.\nGør noget. [S:SRC0001]\n"
    validate_citations(md, valid_source_ids={"SRC0001"})


def test_citation_validator_merges_common_abbreviation_splits():
    md = "Dette er en sætning, f.eks. med eksempel. [S:SRC0001]\n"
    validate_citations(md, valid_source_ids={"SRC0001"})


def test_citation_validator_accepts_citation_on_next_line():
    md = "Dette er en sætning.\n[S:SRC0001]\n"
    validate_citations(md, valid_source_ids={"SRC0001"})

from procedurewriter.pipeline.run import (
    _pubmed_evidence_score,
    _pubmed_relevance_score,
    _tokenize_for_relevance,
)


def test_pubmed_relevance_score_prefers_matching_title():
    query_tokens = _tokenize_for_relevance("akut astma acute asthma")
    good = _pubmed_relevance_score(query_tokens, "Acute asthma exacerbation in adults", None)
    bad = _pubmed_relevance_score(query_tokens, "Elemental carbon exposure and disease incidence", None)
    assert good > bad


def test_pubmed_candidate_sorting_prefers_relevance_with_same_evidence():
    query_tokens = _tokenize_for_relevance("acute asthma")
    evidence = _pubmed_evidence_score(["Systematic Review"])
    candidates = [
        {
            "score": evidence,
            "relevance": _pubmed_relevance_score(query_tokens, "Air pollution meta-analysis", None),
            "has_abstract": True,
            "year": 2024,
            "id": "bad",
        },
        {
            "score": evidence,
            "relevance": _pubmed_relevance_score(query_tokens, "Acute asthma treatment meta-analysis", None),
            "has_abstract": True,
            "year": 2024,
            "id": "good",
        },
    ]
    candidates.sort(key=lambda c: (c["score"], c["relevance"], c["has_abstract"], c["year"]), reverse=True)
    assert candidates[0]["id"] == "good"

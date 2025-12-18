from procedurewriter.pipeline.evidence import build_evidence_report
from procedurewriter.pipeline.types import Snippet


def test_evidence_report_marks_supported_and_unsupported():
    md = "## A\nAcute asthma exacerbation treatment. [S:SRC0001]\nCompletely unrelated sentence. [S:SRC0001]\n"
    snippets = [
        Snippet(source_id="SRC0001", text="Acute asthma exacerbation treatment details.", location={"chunk": 0}),
        Snippet(source_id="SRC0001", text="Completely different topic.", location={"chunk": 1}),
    ]
    report = build_evidence_report(md, snippets=snippets)
    assert report["sentence_count"] == 2
    assert report["supported_count"] + report["unsupported_count"] == 2
    s0 = report["sentences"][0]
    s1 = report["sentences"][1]
    assert s0["supported"] is True
    assert s1["supported"] is False

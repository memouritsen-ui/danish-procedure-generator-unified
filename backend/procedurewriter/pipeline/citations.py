from __future__ import annotations

from procedurewriter.pipeline.text_units import (
    CitationValidationError,
    iter_cited_sentences,
)


def validate_citations(markdown_text: str, *, valid_source_ids: set[str]) -> None:
    errors: list[str] = []
    for sent in iter_cited_sentences(markdown_text):
        if not sent.citations:
            errors.append(f"Line {sent.line_no}: Missing citation in sentence: {sent.text[:160]}")
            continue
        for cid in sent.citations:
            if cid not in valid_source_ids:
                errors.append(f"Line {sent.line_no}: Unknown source_id {cid!r} in: {sent.text[:160]}")

    if errors:
        raise CitationValidationError("\n".join(errors))

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any

from procedurewriter.pipeline.text_units import CitedSentence, iter_cited_sentences
from procedurewriter.pipeline.types import Snippet

_token_re = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9]+", re.UNICODE)
_citation_tag_re = re.compile(r"\[S:[^\]]+\]")

_stopwords = {
    "og",
    "eller",
    "the",
    "and",
    "of",
    "in",
    "to",
    "for",
    "a",
    "an",
    "på",
    "i",
    "af",
    "til",
    "med",
    "som",
    "ved",
    "fra",
    "der",
    "det",
    "den",
    "de",
    "en",
    "et",
}


class EvidencePolicyError(ValueError):
    pass


def build_evidence_report(markdown_text: str, *, snippets: list[Snippet]) -> dict[str, Any]:
    index = _Bm25Index(snippets)
    items: list[dict[str, Any]] = []

    supported = 0
    unsupported = 0
    for sent in iter_cited_sentences(markdown_text):
        item = _score_sentence(sent, index=index)
        if item["supported"]:
            supported += 1
        else:
            unsupported += 1
        items.append(item)

    return {
        "version": 1,
        "sentence_count": len(items),
        "supported_count": supported,
        "unsupported_count": unsupported,
        "sentences": items,
    }


def enforce_evidence_policy(report: dict[str, Any], *, policy: str) -> None:
    p = (policy or "").strip().lower()
    if p in {"", "off", "warn"}:
        return
    if p != "strict":
        return

    unsupported = int(report.get("unsupported_count") or 0)
    if unsupported <= 0:
        return

    sentences = report.get("sentences")
    examples: list[str] = []
    if isinstance(sentences, list):
        for s in sentences:
            if not isinstance(s, dict):
                continue
            if s.get("supported") is True:
                continue
            line_no = s.get("line_no")
            text = str(s.get("text") or "").strip()
            examples.append(f"Line {line_no}: {text[:160]}")

    sample = "\n".join(examples[:8]) if examples else "(no details)"
    raise EvidencePolicyError(
        "Evidence policy STRICT failed: "
        f"{unsupported} unsupported sentences.\n"
        f"{sample}\n"
        "See evidence_report.json for details."
    )


def _score_sentence(sent: CitedSentence, *, index: _Bm25Index) -> dict[str, Any]:
    clean = _clean_sentence_text(sent.text)
    query_tokens = set(_tokenize(clean))
    matches: list[dict[str, Any]] = []
    for cid in sent.citations:
        best = index.best_match(clean, source_id=cid)
        best_tokens = set(best.snippet_tokens) if best.snippet_tokens else set()
        overlap = len(query_tokens & best_tokens) if query_tokens and best_tokens else 0
        matches.append(
            {
                "source_id": cid,
                "supported": bool(best.supported and overlap >= 2),
                "bm25": best.score,
                "overlap": overlap,
                "snippet": {
                    "source_id": best.snippet.source_id if best.snippet else None,
                    "location": best.snippet.location if best.snippet else None,
                    "excerpt": (best.snippet.text[:320] if best.snippet and best.snippet.text else None),
                },
            }
        )
    overall_supported = any(m["supported"] for m in matches) if matches else False

    return {
        "line_no": sent.line_no,
        "text": sent.text,
        "clean_text": clean,
        "citations": list(sent.citations),
        "supported": overall_supported,
        "matches": matches,
    }


def _clean_sentence_text(text: str) -> str:
    stripped = _citation_tag_re.sub("", text)
    return " ".join(stripped.split()).strip()


def _tokenize(text: str) -> list[str]:
    toks = [t.lower() for t in _token_re.findall(text) if len(t) >= 2]
    return [t for t in toks if t not in _stopwords]


@dataclass(frozen=True)
class _Match:
    score: float
    snippet: Snippet | None
    snippet_tokens: list[str] | None
    supported: bool


class _Bm25Index:
    def __init__(self, snippets: list[Snippet]) -> None:
        self._snippets = snippets
        self._tokens = [_tokenize(s.text) for s in snippets]

        self._doc_lens = [len(t) for t in self._tokens]
        self._avgdl = (sum(self._doc_lens) / len(self._doc_lens)) if self._doc_lens else 0.0

        df: dict[str, int] = {}
        for toks in self._tokens:
            for term in set(toks):
                df[term] = df.get(term, 0) + 1

        n_docs = len(self._tokens)
        self._idf: dict[str, float] = {}
        for term, freq in df.items():
            self._idf[term] = math.log((n_docs - freq + 0.5) / (freq + 0.5) + 1.0)

        self._by_source: dict[str, list[int]] = {}
        for idx, s in enumerate(snippets):
            self._by_source.setdefault(s.source_id, []).append(idx)

    def best_match(self, query: str, *, source_id: str | None) -> _Match:
        q_tokens = _tokenize(query)
        if not q_tokens:
            return _Match(score=0.0, snippet=None, snippet_tokens=None, supported=False)

        candidates = self._by_source.get(source_id, []) if source_id else list(range(len(self._snippets)))
        if not candidates:
            return _Match(score=0.0, snippet=None, snippet_tokens=None, supported=False)

        q_set = set(q_tokens)
        best_score = 0.0
        best_idx: int | None = None
        for idx in candidates:
            score = self._bm25_score(q_set, idx)
            if score > best_score:
                best_score = score
                best_idx = idx

        if best_idx is None:
            return _Match(score=0.0, snippet=None, snippet_tokens=None, supported=False)

        snippet = self._snippets[best_idx]
        snippet_tokens = self._tokens[best_idx]
        supported = best_score > 0.0
        return _Match(score=float(best_score), snippet=snippet, snippet_tokens=snippet_tokens, supported=supported)

    def _bm25_score(self, q_tokens: set[str], doc_idx: int) -> float:
        k1 = 1.5
        b = 0.75
        doc_tokens = self._tokens[doc_idx]
        dl = self._doc_lens[doc_idx]
        if not doc_tokens:
            return 0.0

        tf: dict[str, int] = {}
        for t in doc_tokens:
            tf[t] = tf.get(t, 0) + 1

        score = 0.0
        denom_base = k1 * (1.0 - b + b * (dl / (self._avgdl or 1.0)))
        for q in q_tokens:
            freq = tf.get(q, 0)
            if freq <= 0:
                continue
            idf = self._idf.get(q, 0.0)
            denom = freq + denom_base
            score += idf * (freq * (k1 + 1.0) / (denom or 1.0))
        return score

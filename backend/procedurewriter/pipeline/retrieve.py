from __future__ import annotations

import math
import re
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from procedurewriter.pipeline.io import write_json
from procedurewriter.pipeline.types import Snippet, SourceRecord

_token_re = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9]+", re.UNICODE)


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _token_re.findall(text)]


def chunk_text(text: str, *, max_chars: int = 900, overlap: int = 120) -> list[str]:
    text = text.strip()
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + max_chars)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(0, end - overlap)
    return chunks


def build_snippets(sources: list[SourceRecord]) -> list[Snippet]:
    snippets: list[Snippet] = []
    for src in sources:
        extra = src.extra or {}
        pages_json = extra.get("pages_json")
        if pages_json:
            pages_path = Path(str(pages_json))
            pages: list[dict[str, Any]] = _read_json(pages_path)
            for p in pages:
                t = str(p.get("text", "")).strip()
                if not t:
                    continue
                snippets.append(
                    Snippet(
                        source_id=src.source_id,
                        text=t,
                        location={"page": int(p.get("page", 0))},
                    )
                )
            continue

        blocks_json = extra.get("blocks_json")
        if blocks_json:
            blocks_path = Path(str(blocks_json))
            blocks: list[dict[str, Any]] = _read_json(blocks_path)
            for b in blocks:
                t = str(b.get("text", "")).strip()
                if not t:
                    continue
                loc: dict[str, Any] = {"block": int(b.get("i", 0))}
                kind = b.get("kind")
                if kind:
                    loc["kind"] = str(kind)
                level = b.get("level")
                if level is not None:
                    with suppress(Exception):
                        loc["level"] = int(level)
                snippets.append(Snippet(source_id=src.source_id, text=t, location=loc))
            continue

        normalized_text = Path(src.normalized_path).read_text(encoding="utf-8")
        for i, chunk in enumerate(chunk_text(normalized_text)):
            snippets.append(Snippet(source_id=src.source_id, text=chunk, location={"chunk": i}))
    return snippets


def retrieve(
    query: str,
    snippets: list[Snippet],
    *,
    top_k: int = 8,
    prefer_embeddings: bool = False,
    embeddings_model: str = "text-embedding-3-small",
    run_index_dir: Path | None = None,
    openai_api_key: str | None = None,
) -> list[Snippet]:
    query = query.strip()
    if not query or not snippets:
        return []

    if prefer_embeddings and openai_api_key:
        try:
            return _retrieve_embeddings(
                query,
                snippets,
                top_k=top_k,
                embeddings_model=embeddings_model,
                run_index_dir=run_index_dir,
                openai_api_key=openai_api_key,
            )
        except Exception:
            pass

    return _retrieve_bm25(query, snippets, top_k=top_k)


def _retrieve_bm25(query: str, snippets: list[Snippet], *, top_k: int) -> list[Snippet]:
    docs_tokens = [_tokenize(s.text) for s in snippets]
    query_tokens = _tokenize(query)
    if not query_tokens:
        return snippets[:top_k]

    n_docs = len(docs_tokens)
    doc_lens = [len(toks) for toks in docs_tokens]
    avgdl = (sum(doc_lens) / n_docs) if n_docs else 0.0

    df: dict[str, int] = {}
    for toks in docs_tokens:
        for term in set(toks):
            df[term] = df.get(term, 0) + 1

    idf: dict[str, float] = {}
    for term, freq in df.items():
        idf[term] = math.log((n_docs - freq + 0.5) / (freq + 0.5) + 1.0)

    k1 = 1.5
    b = 0.75

    scores: list[tuple[float, int]] = []
    for idx, toks in enumerate(docs_tokens):
        tf: dict[str, int] = {}
        for t in toks:
            tf[t] = tf.get(t, 0) + 1
        score = 0.0
        dl = doc_lens[idx]
        for q in query_tokens:
            if q not in tf:
                continue
            term_idf = idf.get(q, 0.0)
            term_tf = tf[q]
            denom = term_tf + k1 * (1.0 - b + b * (dl / (avgdl or 1.0)))
            score += term_idf * (term_tf * (k1 + 1.0) / (denom or 1.0))
        scores.append((score, idx))

    scores.sort(key=lambda x: x[0], reverse=True)
    top = [snippets[i] for score, i in scores if score > 0.0][:top_k]
    return top or snippets[:top_k]


@dataclass(frozen=True)
class _Emb:
    vector: list[float]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b, strict=False):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0.0 or nb <= 0.0:
        return 0.0
    return dot / math.sqrt(na * nb)


def _retrieve_embeddings(
    query: str,
    snippets: list[Snippet],
    *,
    top_k: int,
    embeddings_model: str,
    run_index_dir: Path | None,
    openai_api_key: str,
) -> list[Snippet]:
    from openai import OpenAI

    client = OpenAI(api_key=openai_api_key, timeout=15.0, max_retries=0)

    texts = [query] + [s.text[:2000] for s in snippets]
    resp = client.embeddings.create(model=embeddings_model, input=texts)
    vectors = [d.embedding for d in resp.data]
    query_vec = vectors[0]
    doc_vecs = vectors[1:]

    scored: list[tuple[float, int]] = []
    for i, v in enumerate(doc_vecs):
        scored.append((_cosine(query_vec, v), i))
    scored.sort(key=lambda x: x[0], reverse=True)
    selected = [snippets[i] for score, i in scored[:top_k] if score > 0.0]
    if not selected:
        selected = [snippets[i] for _, i in scored[:top_k]]

    if run_index_dir is not None:
        run_index_dir.mkdir(parents=True, exist_ok=True)
        write_json(
            run_index_dir / "embeddings_retrieval.json",
            {
                "model": embeddings_model,
                "top_k": top_k,
                "results": [
                    {"score": float(score), "source_id": snippets[i].source_id, "location": snippets[i].location}
                    for score, i in scored[:top_k]
                ],
            },
        )

    return selected


def _read_json(path: Path) -> Any:
    import json

    return json.loads(path.read_text(encoding="utf-8"))

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from procedurewriter.config_store import load_yaml
from procedurewriter.db import LibrarySourceRow
from procedurewriter.pipeline.citations import validate_citations
from procedurewriter.pipeline.docx_writer import write_procedure_docx
from procedurewriter.pipeline.evidence import build_evidence_report, enforce_evidence_policy
from procedurewriter.pipeline.fetcher import CachedHttpClient
from procedurewriter.pipeline.io import write_json, write_jsonl, write_text
from procedurewriter.pipeline.manifest import write_manifest
from procedurewriter.pipeline.normalize import normalize_html, normalize_pubmed
from procedurewriter.pipeline.pubmed import PubMedClient
from procedurewriter.pipeline.retrieve import build_snippets, retrieve
from procedurewriter.pipeline.sources import make_source_id, to_jsonl_record, write_source_files
from procedurewriter.pipeline.types import SourceRecord
from procedurewriter.pipeline.writer import write_procedure_markdown
from procedurewriter.settings import Settings


def run_pipeline(
    *,
    run_id: str,
    created_at_utc: str,
    procedure: str,
    context: str | None,
    settings: Settings,
    library_sources: list[LibrarySourceRow],
    openai_api_key: str | None = None,
    anthropic_api_key: str | None = None,
    ollama_base_url: str | None = None,
    ncbi_api_key: str | None = None,
) -> dict[str, str]:
    run_dir = settings.runs_dir / run_id
    (run_dir / "raw").mkdir(parents=True, exist_ok=True)
    (run_dir / "normalized").mkdir(parents=True, exist_ok=True)
    (run_dir / "index").mkdir(parents=True, exist_ok=True)

    author_guide = load_yaml(settings.author_guide_path)
    allowlist = load_yaml(settings.allowlist_path)

    http = CachedHttpClient(cache_dir=settings.cache_dir)
    try:
        sources: list[SourceRecord] = []
        source_n = 1
        warnings: list[str] = []

        for lib in library_sources:
            source_id = make_source_id(source_n)
            source_n += 1

            raw_src_path = Path(lib.raw_path)
            raw_suffix = raw_src_path.suffix or ".bin"
            raw_bytes = raw_src_path.read_bytes()
            normalized_text = Path(lib.normalized_path).read_text(encoding="utf-8")

            written = write_source_files(
                run_dir=run_dir,
                source_id=source_id,
                raw_bytes=raw_bytes,
                raw_suffix=raw_suffix,
                normalized_text=normalized_text,
            )

            extra = dict(lib.meta)
            pages_json = extra.get("pages_json")
            if pages_json and Path(str(pages_json)).exists():
                pages = Path(str(pages_json)).read_text(encoding="utf-8")
                pages_out = run_dir / "normalized" / f"{source_id}_pages.json"
                write_text(pages_out, pages)
                extra["pages_json"] = str(pages_out)

            blocks_json = extra.get("blocks_json")
            if blocks_json and Path(str(blocks_json)).exists():
                blocks = Path(str(blocks_json)).read_text(encoding="utf-8")
                blocks_out = run_dir / "normalized" / f"{source_id}_blocks.json"
                write_text(blocks_out, blocks)
                extra["blocks_json"] = str(blocks_out)

            year_val = lib.meta.get("year")
            year: int | None
            if isinstance(year_val, int):
                year = year_val
            elif isinstance(year_val, str) and year_val.isdigit():
                year = int(year_val)
            else:
                year = None

            sources.append(
                SourceRecord(
                    source_id=source_id,
                    fetched_at_utc=lib.created_at_utc,
                    kind=lib.kind,
                    title=lib.title,
                    year=year,
                    url=lib.url,
                    doi=str(lib.meta.get("doi")) if lib.meta.get("doi") else None,
                    pmid=str(lib.meta.get("pmid")) if lib.meta.get("pmid") else None,
                    raw_path=str(written.raw_path),
                    normalized_path=str(written.normalized_path),
                    raw_sha256=written.raw_sha256,
                    normalized_sha256=written.normalized_sha256,
                    extraction_notes=str(lib.meta.get("extraction_notes")) if lib.meta.get("extraction_notes") else None,
                    terms_licence_note=str(lib.meta.get("terms_licence_note")) if lib.meta.get("terms_licence_note") else None,
                    extra=extra,
                )
            )

        if not settings.dummy_mode:
            source_n = _append_seed_url_sources(
                allowlist=allowlist,
                http=http,
                run_dir=run_dir,
                source_n=source_n,
                sources=sources,
                warnings=warnings,
            )

        if settings.dummy_mode:
            source_id = make_source_id(source_n)
            source_n += 1
            dummy_text = (
                "Dette er en lokal dummy-kilde til demo/test. Den repræsenterer ikke en klinisk guideline."
            )
            written = write_source_files(
                run_dir=run_dir,
                source_id=source_id,
                raw_bytes=dummy_text.encode("utf-8"),
                raw_suffix=".txt",
                normalized_text=dummy_text,
            )
            sources.append(
                SourceRecord(
                    source_id=source_id,
                    fetched_at_utc=_utc_now_iso(),
                    kind="dummy",
                    title="Dummy kilde (demo/test)",
                    year=None,
                    url=None,
                    doi=None,
                    pmid=None,
                    raw_path=str(written.raw_path),
                    normalized_path=str(written.normalized_path),
                    raw_sha256=written.raw_sha256,
                    normalized_sha256=written.normalized_sha256,
                    extraction_notes="Genereret lokalt til dummy mode.",
                    terms_licence_note="Kun til demo/test. Ikke medicinsk rådgivning.",
                    extra={},
                )
            )

        if not settings.dummy_mode:
            pubmed = PubMedClient(
                http,
                tool=settings.ncbi_tool,
                email=settings.ncbi_email,
                api_key=ncbi_api_key or settings.ncbi_api_key,
            )
            expanded_terms = _expand_procedure_terms(procedure=procedure, context=context)
            queries = _build_pubmed_queries(expanded_terms=expanded_terms)
            candidates: list[dict[str, Any]] = []
            seen_pmids: set[str] = set()
            pubmed_warnings: list[str] = []
            query_tokens = _tokenize_for_relevance(" ".join(expanded_terms))

            for q in queries:
                try:
                    pmids, search_resp = pubmed.search(q, retmax=25)
                except Exception as e:  # noqa: BLE001
                    pubmed_warnings.append(f"PubMed search failed for query={q!r}: {e}")
                    continue
                if not pmids:
                    continue
                try:
                    fetched_articles, fetch_resp = pubmed.fetch(pmids)
                except Exception as e:  # noqa: BLE001
                    pubmed_warnings.append(f"PubMed fetch failed for query={q!r}: {e}")
                    continue
                for fetched in fetched_articles:
                    art = fetched.article
                    if art.pmid in seen_pmids:
                        continue
                    seen_pmids.add(art.pmid)
                    candidates.append(
                        {
                            "fetched": fetched,
                            "fetch_resp": fetch_resp,
                            "search_query": q,
                            "search_cache_path": search_resp.cache_path,
                            "score": _pubmed_evidence_score(art.publication_types),
                            "relevance": _pubmed_relevance_score(query_tokens, art.title, art.abstract),
                            "has_abstract": bool(art.abstract),
                            "year": art.year or 0,
                        }
                    )
                if len(candidates) >= 40:
                    break

            candidates.sort(key=lambda c: (c["score"], c["relevance"], c["has_abstract"], c["year"]), reverse=True)
            selected = candidates[:12]

            for c in selected:
                fetched = c["fetched"]
                fetch_resp = c["fetch_resp"]
                q = str(c["search_query"])
                search_cache_path = str(c["search_cache_path"])
                art = fetched.article

                source_id = make_source_id(source_n)
                source_n += 1
                normalized = normalize_pubmed(art.title, art.abstract, art.journal, art.year)
                written = write_source_files(
                    run_dir=run_dir,
                    source_id=source_id,
                    raw_bytes=fetched.raw_xml,
                    raw_suffix=".xml",
                    normalized_text=normalized,
                )
                sources.append(
                    SourceRecord(
                        source_id=source_id,
                        fetched_at_utc=fetch_resp.fetched_at_utc,
                        kind="pubmed",
                        title=art.title,
                        year=art.year,
                        url=f"https://pubmed.ncbi.nlm.nih.gov/{art.pmid}/",
                        doi=art.doi,
                        pmid=art.pmid,
                        raw_path=str(written.raw_path),
                        normalized_path=str(written.normalized_path),
                        raw_sha256=written.raw_sha256,
                        normalized_sha256=written.normalized_sha256,
                        extraction_notes=f"PubMed via NCBI E-utilities. Search cache: {search_cache_path}",
                        terms_licence_note="PubMed abstract/metadata. Tjek rettigheder for fuldtekst.",
                        extra={
                            "search_query": q,
                            "publication_types": art.publication_types,
                        },
                    )
                )
            warnings.extend(pubmed_warnings)

        if not sources:
            source_id = make_source_id(1)
            note = "Ingen eksterne kilder kunne hentes i denne kørsel."
            if warnings:
                note = note + "\n\nAdvarsler:\n" + "\n".join(warnings[:8])
            written = write_source_files(
                run_dir=run_dir,
                source_id=source_id,
                raw_bytes=note.encode("utf-8"),
                raw_suffix=".txt",
                normalized_text=note,
            )
            sources.append(
                SourceRecord(
                    source_id=source_id,
                    fetched_at_utc=_utc_now_iso(),
                    kind="system_note",
                    title="System note: ingen kilder",
                    year=None,
                    url=None,
                    doi=None,
                    pmid=None,
                    raw_path=str(written.raw_path),
                    normalized_path=str(written.normalized_path),
                    raw_sha256=written.raw_sha256,
                    normalized_sha256=written.normalized_sha256,
                    extraction_notes="Oprettet fordi ingen kilder var tilgængelige.",
                    terms_licence_note=None,
                    extra={},
                )
            )

        sources_jsonl_path = run_dir / "sources.jsonl"
        write_jsonl(sources_jsonl_path, [to_jsonl_record(s) for s in sources])

        snippets = build_snippets(sources)
        query = " ".join([procedure, context or ""]).strip()
        retrieved = retrieve(
            query,
            snippets,
            top_k=80,
            prefer_embeddings=bool(openai_api_key),
            embeddings_model=settings.openai_embeddings_model,
            run_index_dir=run_dir / "index",
            openai_api_key=openai_api_key,
        )

        md = write_procedure_markdown(
            procedure=procedure,
            context=context,
            author_guide=author_guide,
            snippets=retrieved,
            sources=sources,
            dummy_mode=settings.dummy_mode,
            use_llm=settings.use_llm,
            llm_model=settings.llm_model,
            llm_provider=settings.llm_provider.value,
            openai_api_key=openai_api_key,
            anthropic_api_key=anthropic_api_key,
            ollama_base_url=ollama_base_url or settings.ollama_base_url,
        )
        validate_citations(md, valid_source_ids={s.source_id for s in sources})

        procedure_md_path = run_dir / "procedure.md"
        write_text(procedure_md_path, md)

        evidence_report_path = run_dir / "evidence_report.json"
        evidence = build_evidence_report(md, snippets=snippets)
        write_json(evidence_report_path, evidence)

        evidence_policy = "warn"
        if isinstance(author_guide, dict):
            validation = author_guide.get("validation")
            if isinstance(validation, dict):
                p = validation.get("evidence_policy")
                if isinstance(p, str) and p.strip():
                    evidence_policy = p.strip().lower()

        runtime: dict[str, Any] = {
            "dummy_mode": settings.dummy_mode,
            "use_llm": settings.use_llm,
            "openai_api_key_present": bool(openai_api_key),
            "retrieval": "embeddings" if bool(openai_api_key) else "bm25",
            "allowlist_version": (allowlist.get("version") if isinstance(allowlist, dict) else None),
            "source_count": len(sources),
            "evidence_policy": evidence_policy,
            "evidence_supported_count": int(evidence.get("supported_count") or 0),
            "evidence_unsupported_count": int(evidence.get("unsupported_count") or 0),
        }
        if warnings:
            runtime["warnings"] = warnings[:20]

        manifest_path = run_dir / "run_manifest.json"
        manifest_hash = write_manifest(
            manifest_path=manifest_path,
            run_id=run_id,
            created_at_utc=created_at_utc,
            procedure=procedure,
            context=context,
            author_guide_path=settings.author_guide_path,
            allowlist_path=settings.allowlist_path,
            sources_jsonl_path=sources_jsonl_path,
            procedure_md_path=procedure_md_path,
            evidence_report_path=evidence_report_path,
            sources=sources,
            runtime=runtime,
        )

        if not settings.dummy_mode:
            enforce_evidence_policy(evidence, policy=evidence_policy)

        docx_path = run_dir / "Procedure.docx"
        write_procedure_docx(
            markdown_text=md,
            sources=sources,
            output_path=docx_path,
            run_id=run_id,
            manifest_hash=manifest_hash,
        )

        write_json(
            run_dir / "run_summary.json",
            {
                "run_id": run_id,
                "created_at_utc": created_at_utc,
                "procedure": procedure,
                "status": "DONE",
                "manifest_sha256": manifest_hash,
            },
        )

        # Calculate quality score based on evidence coverage
        supported = int(evidence.get("supported_count") or 0)
        unsupported = int(evidence.get("unsupported_count") or 0)
        total_claims = supported + unsupported
        if total_claims > 0:
            # Score 1-10 based on support ratio, with minimum of 5 for having any claims
            quality_score = max(5, min(10, 5 + int((supported / total_claims) * 5)))
        else:
            quality_score = 5  # Default score when no claims to validate

        return {
            "run_dir": str(run_dir),
            "sources_jsonl_path": str(sources_jsonl_path),
            "procedure_md_path": str(procedure_md_path),
            "manifest_path": str(manifest_path),
            "docx_path": str(docx_path),
            "quality_score": quality_score,
            "iterations_used": 1,  # Single pass for now
            "total_cost_usd": 0.0,  # TODO: Track when agent orchestrator is integrated
            "total_input_tokens": 0,
            "total_output_tokens": 0,
        }
    finally:
        http.close()


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _pubmed_evidence_score(publication_types: list[str]) -> int:
    if not publication_types:
        return 0
    types = {t.strip().lower() for t in publication_types if t and t.strip()}
    score = 0
    if "practice guideline" in types or "guideline" in types:
        score += 1000
    if "systematic review" in types:
        score += 900
    if "meta-analysis" in types:
        score += 850
    if "review" in types:
        score += 700
    if "randomized controlled trial" in types:
        score += 650
    if "clinical trial" in types:
        score += 600
    if "case reports" in types:
        score -= 200
    return score


def _allowlist_prefixes(allowlist: dict[str, Any]) -> list[str]:
    prefixes = allowlist.get("allowed_url_prefixes", []) if isinstance(allowlist, dict) else []
    out: list[str] = []
    for p in prefixes:
        s = str(p).strip()
        if s:
            out.append(s)
    return out


def _seed_urls(allowlist: dict[str, Any]) -> list[str]:
    urls = allowlist.get("seed_urls", []) if isinstance(allowlist, dict) else []
    out: list[str] = []
    for u in urls:
        s = str(u).strip()
        if s:
            out.append(s)
    return out


def _is_allowed_url(url: str, *, prefixes: list[str]) -> bool:
    return any(url.startswith(p) for p in prefixes)


def _extract_html_title(raw_html: bytes) -> str | None:
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(raw_html, "html.parser")
        if soup.title and soup.title.string:
            title = str(soup.title.string).strip()
            return title or None
    except Exception:  # noqa: BLE001
        return None
    return None


def _append_seed_url_sources(
    *,
    allowlist: dict[str, Any],
    http: CachedHttpClient,
    run_dir: Path,
    source_n: int,
    sources: list[SourceRecord],
    warnings: list[str],
) -> int:
    prefixes = _allowlist_prefixes(allowlist)
    urls = _seed_urls(allowlist)
    if not urls:
        return source_n

    # Keep conservative; users can still ingest many URLs via the UI.
    max_per_run = 8
    for url in urls[:max_per_run]:
        if not _is_allowed_url(url, prefixes=prefixes):
            warnings.append(f"Seed URL not allowed by allowlist: {url}")
            continue
        try:
            resp = http.get(url)
        except Exception as e:  # noqa: BLE001
            warnings.append(f"Seed URL fetch failed for {url}: {e}")
            continue

        source_id = make_source_id(source_n)
        source_n += 1
        raw_suffix = ".html"
        normalized_text = normalize_html(resp.content)
        written = write_source_files(
            run_dir=run_dir,
            source_id=source_id,
            raw_bytes=resp.content,
            raw_suffix=raw_suffix,
            normalized_text=normalized_text,
        )

        title = _extract_html_title(resp.content) or url
        sources.append(
            SourceRecord(
                source_id=source_id,
                fetched_at_utc=resp.fetched_at_utc,
                kind="guideline_url",
                title=title,
                year=None,
                url=url,
                doi=None,
                pmid=None,
                raw_path=str(written.raw_path),
                normalized_path=str(written.normalized_path),
                raw_sha256=written.raw_sha256,
                normalized_sha256=written.normalized_sha256,
                extraction_notes=f"Fetched from allowlist seed_urls. Cache: {resp.cache_path}",
                terms_licence_note="Respektér source terms/licence. Ingen paywall scraping.",
                extra={"final_url": resp.url},
            )
        )

    if len(urls) > max_per_run:
        warnings.append(f"seed_urls truncated: using first {max_per_run} of {len(urls)}")
    return source_n


_DA_EN_PHRASES: dict[str, list[str]] = {
    "skulderfraktur": ["shoulder fracture", "proximal humerus fracture"],
    "lumbalpunktur": ["lumbar puncture"],
    "proceduresedation": ["procedural sedation"],
    "akut astma": ["acute asthma"],
}

_DA_EN_SUBSTRINGS: list[tuple[str, str]] = [
    ("lumbalpunktur", "lumbar puncture"),
    ("skulder", "shoulder"),
    ("fraktur", "fracture"),
    ("luksation", "dislocation"),
    ("reponering", "reduction"),
    ("akut", "acute"),
    ("astma", "asthma"),
    ("intubation", "intubation"),
    ("koniotomi", "cricothyrotomy"),
]


def _expand_procedure_terms(*, procedure: str, context: str | None) -> list[str]:
    base = procedure.strip()
    if not base:
        return []

    terms: list[str] = [base]
    lowered = base.lower().strip()
    if lowered in _DA_EN_PHRASES:
        terms.extend(_DA_EN_PHRASES[lowered])
    translated = lowered
    for da, en in _DA_EN_SUBSTRINGS:
        if da in translated:
            translated = translated.replace(da, f" {en} ")
    translated = " ".join(translated.split()).strip()
    if translated and translated != lowered:
        terms.append(translated)

    # Lightly include context terms if provided (kept conservative to avoid over-filtering).
    if context:
        ctx = context.strip()
        if ctx:
            terms.append(f"{base} {ctx}")

    # Deduplicate while preserving order.
    seen: set[str] = set()
    deduped_terms: list[str] = []
    for t in terms:
        t = t.strip()
        if not t:
            continue
        key = t.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped_terms.append(t)
    return deduped_terms


def _build_pubmed_queries(*, expanded_terms: list[str]) -> list[str]:
    if not expanded_terms:
        return []
    evidence_filter = '(guideline[pt] OR "practice guideline"[pt] OR systematic[sb] OR "systematic review"[pt] OR "meta-analysis"[pt])'
    queries: list[str] = []
    for t in expanded_terms:
        queries.append(f"{t} {evidence_filter}")
        queries.append(t)

    # Deduplicate queries while preserving order.
    q_seen: set[str] = set()
    out: list[str] = []
    for q in queries:
        k = q.lower().strip()
        if k in q_seen:
            continue
        q_seen.add(k)
        out.append(q)
    return out


_relevance_token_re = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9]+", re.UNICODE)


def _tokenize_for_relevance(text: str) -> set[str]:
    tokens = {t.lower() for t in _relevance_token_re.findall(text) if len(t) >= 2}
    # Remove ultra-common stopwords (minimal; keep conservative).
    return {t for t in tokens if t not in {"og", "or", "the", "and", "of", "in", "to", "for"}}


def _pubmed_relevance_score(query_tokens: set[str], title: str | None, abstract: str | None) -> int:
    if not query_tokens:
        return 0
    score = 0
    if title:
        score += 3 * len(query_tokens & _tokenize_for_relevance(title))
    if abstract:
        score += 1 * len(query_tokens & _tokenize_for_relevance(abstract))
    return score

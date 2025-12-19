from __future__ import annotations

import contextlib
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from procedurewriter.agents.models import PipelineInput as AgentPipelineInput
from procedurewriter.agents.models import SourceReference
from procedurewriter.config_store import load_yaml
from procedurewriter.db import LibrarySourceRow
from procedurewriter.llm import get_session_tracker, reset_session_tracker
from procedurewriter.llm.providers import get_llm_client
from procedurewriter.pipeline.citations import validate_citations
from procedurewriter.pipeline.docx_writer import write_procedure_docx
from procedurewriter.pipeline.events import EventType, get_emitter, remove_emitter
from procedurewriter.pipeline.evidence import build_evidence_report, enforce_evidence_policy
from procedurewriter.pipeline.evidence_hierarchy import EvidenceHierarchy
from procedurewriter.pipeline.fetcher import CachedHttpClient
from procedurewriter.pipeline.io import write_json, write_jsonl, write_text
from procedurewriter.pipeline.library_search import LibrarySearchProvider
from procedurewriter.pipeline.manifest import write_manifest
from procedurewriter.pipeline.normalize import normalize_html, normalize_pubmed
from procedurewriter.pipeline.pubmed import PubMedClient
from procedurewriter.pipeline.retrieve import build_snippets, retrieve
from procedurewriter.pipeline.source_scoring import SourceScore, rank_sources
from procedurewriter.pipeline.sources import make_source_id, to_jsonl_record, write_source_files
from procedurewriter.pipeline.types import SourceRecord
from procedurewriter.pipeline.writer import write_procedure_markdown
from procedurewriter.settings import Settings


def source_record_to_reference(
    source: SourceRecord,
    source_score: SourceScore | None = None,
) -> SourceReference:
    """
    Convert a pipeline SourceRecord to an agent SourceReference.

    Adapts the pipeline's source format to the agent system's format,
    using composite source score when available, or falling back to
    evidence priority for relevance calculation.
    """
    # Use composite score if available (0-100 mapped to 0.0-1.0)
    if source_score is not None:
        relevance_score = min(1.0, source_score.composite_score / 100.0)
    else:
        # Fallback: calculate from evidence priority or relevance_score
        evidence_priority = source.extra.get("evidence_priority", 0)
        relevance = source.extra.get("relevance_score")
        if relevance is not None:
            # relevance_score in source.extra may be on 0-10 scale; normalize to 0-1
            raw_score = float(relevance)
            relevance_score = min(1.0, raw_score / 10.0) if raw_score > 1.0 else raw_score
        elif evidence_priority:
            # Map priority 0-1000 to 0.0-1.0
            relevance_score = min(1.0, evidence_priority / 1000.0)
        else:
            relevance_score = 0.5  # Default mid-range

    # Get abstract excerpt from normalized text if available
    abstract_excerpt = None
    try:
        normalized_path = source.normalized_path
        if normalized_path:
            from pathlib import Path
            norm_text = Path(normalized_path).read_text(encoding="utf-8")
            # Take first 500 chars as excerpt
            abstract_excerpt = norm_text[:500] if norm_text else None
    except Exception:
        pass

    return SourceReference(
        source_id=source.source_id,
        title=source.title or "Untitled",
        year=source.year,
        pmid=source.pmid,
        doi=source.doi,
        url=source.url,
        relevance_score=relevance_score,
        abstract_excerpt=abstract_excerpt,
    )


def _source_record_to_scoring_dict(source: SourceRecord) -> dict[str, Any]:
    """
    Convert a SourceRecord to a dict suitable for source scoring.
    """
    return {
        "source_id": source.source_id,
        "kind": source.kind,
        "title": source.title,
        "year": source.year,
        "url": source.url,
        "doi": source.doi,
        "pmid": source.pmid,
        "extra": source.extra,
    }


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

    # Get event emitter for SSE streaming
    emitter = get_emitter(run_id)
    emitter.emit(EventType.PROGRESS, {"message": "Pipeline starting", "stage": "init"})

    # Reset session cost tracker for this pipeline run
    reset_session_tracker()

    author_guide = load_yaml(settings.author_guide_path)
    allowlist = load_yaml(settings.allowlist_path)
    evidence_hierarchy = EvidenceHierarchy.from_config(settings.evidence_hierarchy_path)

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

            # Classify evidence level for library source
            evidence_level = evidence_hierarchy.classify_source(
                url=lib.url,
                kind="library",
                title=lib.title,
            )
            extra["evidence_level"] = evidence_level.level_id
            extra["evidence_badge"] = evidence_level.badge
            extra["evidence_badge_color"] = evidence_level.badge_color
            extra["evidence_priority"] = evidence_level.priority

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
                evidence_hierarchy=evidence_hierarchy,
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

        # Search Danish guideline library FIRST (priority 1000 - highest)
        if not settings.dummy_mode:
            emitter.emit(EventType.PROGRESS, {"message": "Searching Danish guideline library", "stage": "library_search"})
            library_provider = LibrarySearchProvider(settings.resolved_guideline_library_path)
            if library_provider.available():
                query_text = " ".join([procedure, context or ""]).strip()
                library_results = library_provider.search(query_text, limit=15)

                for lib_result in library_results:
                    source_id = make_source_id(source_n)
                    source_n += 1

                    # Get extracted text content
                    text_content = lib_result.get_text_content()
                    if not text_content:
                        continue  # Skip documents without extracted text

                    # Read raw content (HTML or PDF)
                    raw_path = lib_result.local_path / "original.html"
                    if not raw_path.exists():
                        raw_path = lib_result.local_path / "original.pdf"
                    if not raw_path.exists():
                        # Use extracted text as raw
                        raw_bytes = text_content.encode("utf-8")
                        raw_suffix = ".txt"
                    else:
                        raw_bytes = raw_path.read_bytes()
                        raw_suffix = raw_path.suffix

                    written = write_source_files(
                        run_dir=run_dir,
                        source_id=source_id,
                        raw_bytes=raw_bytes,
                        raw_suffix=raw_suffix,
                        normalized_text=text_content,
                    )

                    # Parse year from publish_year field
                    year_val = lib_result.publish_year
                    year: int | None = None
                    if year_val:
                        with contextlib.suppress(ValueError):
                            year = int(year_val[:4]) if len(year_val) >= 4 else int(year_val)

                    # Classify evidence level - Danish guidelines get priority 1000
                    library_evidence_level = evidence_hierarchy.classify_source(
                        url=lib_result.url,
                        kind="danish_guideline",
                        title=lib_result.title,
                    )

                    sources.append(
                        SourceRecord(
                            source_id=source_id,
                            fetched_at_utc=_utc_now_iso(),
                            kind="danish_guideline",
                            title=lib_result.title,
                            year=year,
                            url=lib_result.url,
                            doi=None,
                            pmid=None,
                            raw_path=str(written.raw_path),
                            normalized_path=str(written.normalized_path),
                            raw_sha256=written.raw_sha256,
                            normalized_sha256=written.normalized_sha256,
                            extraction_notes=f"Danish guideline library: {lib_result.source_name} (doc_id={lib_result.doc_id})",
                            terms_licence_note="Danish regional/national clinical guideline. Respect source terms.",
                            extra={
                                "library_source_id": lib_result.source_id,
                                "library_doc_id": lib_result.doc_id,
                                "category": lib_result.category,
                                "relevance_score": lib_result.relevance_score,
                                "evidence_level": library_evidence_level.level_id,
                                "evidence_badge": library_evidence_level.badge,
                                "evidence_badge_color": library_evidence_level.badge_color,
                                "evidence_priority": library_evidence_level.priority,
                            },
                        )
                    )

        # Search PubMed (priority 100 - fallback for international research)
        if not settings.dummy_mode:
            emitter.emit(EventType.PROGRESS, {"message": "Searching PubMed for evidence", "stage": "pubmed_search"})
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
                    # Get evidence hierarchy boost for this publication
                    hierarchy_boost = evidence_hierarchy.get_priority_boost(
                        publication_types=art.publication_types
                    )
                    candidates.append(
                        {
                            "fetched": fetched,
                            "fetch_resp": fetch_resp,
                            "search_query": q,
                            "search_cache_path": search_resp.cache_path,
                            "score": _pubmed_evidence_score(art.publication_types) + hierarchy_boost,
                            "relevance": _pubmed_relevance_score(query_tokens, art.title, art.abstract),
                            "has_abstract": bool(art.abstract),
                            "year": art.year or 0,
                            "hierarchy_boost": hierarchy_boost,
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
                # Classify evidence level for PubMed source
                pubmed_evidence_level = evidence_hierarchy.classify_source(
                    publication_types=art.publication_types
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
                            "evidence_level": pubmed_evidence_level.level_id,
                            "evidence_badge": pubmed_evidence_level.badge,
                            "evidence_badge_color": pubmed_evidence_level.badge_color,
                            "evidence_priority": pubmed_evidence_level.priority,
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

        # Score all sources and add scoring data to extra fields
        source_dicts_for_scoring = [_source_record_to_scoring_dict(s) for s in sources]
        all_scored = rank_sources(source_dicts_for_scoring)
        score_by_id = {ss.source_id: ss for ss in all_scored}

        # Enrich sources with scoring data
        for source in sources:
            score = score_by_id.get(source.source_id)
            if score:
                source.extra["composite_score"] = score.composite_score
                source.extra["recency_score"] = score.recency_score
                source.extra["quality_score"] = score.quality_score
                source.extra["scoring_reasoning"] = score.reasoning

        sources_jsonl_path = run_dir / "sources.jsonl"
        write_jsonl(sources_jsonl_path, [to_jsonl_record(s) for s in sources])

        # Write scores summary to separate file for API
        scores_summary = [
            {
                "source_id": ss.source_id,
                "evidence_level": ss.evidence_level,
                "evidence_priority": ss.evidence_priority,
                "recency_score": ss.recency_score,
                "recency_year": ss.recency_year,
                "quality_score": ss.quality_score,
                "composite_score": ss.composite_score,
                "reasoning": ss.reasoning,
            }
            for ss in all_scored
        ]
        write_json(run_dir / "source_scores.json", scores_summary)

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

        # Use multi-agent orchestrator when LLM is enabled
        if settings.use_llm and not settings.dummy_mode:
            # Emit scored sources info (scoring already done above)
            emitter.emit(EventType.SOURCES_FOUND, {
                "count": len(all_scored),
                "top_score": all_scored[0].composite_score if all_scored else 0,
            })

            # Convert sources to agent format with pre-computed scores
            agent_sources = [
                source_record_to_reference(s, score_by_id.get(s.source_id))
                for s in sources
            ]

            # Get LLM client
            llm = get_llm_client(
                provider=settings.llm_provider,
                openai_api_key=openai_api_key,
                anthropic_api_key=anthropic_api_key,
                ollama_base_url=ollama_base_url or settings.ollama_base_url,
            )

            # Create and run orchestrator with event emitter for SSE streaming
            # Lazy import to avoid circular dependency:
            # agents/__init__ → orchestrator → pipeline.events → pipeline/__init__ → run → orchestrator
            from procedurewriter.agents.orchestrator import AgentOrchestrator

            orchestrator = AgentOrchestrator(
                llm=llm,
                model=settings.llm_model,
                pubmed_client=None,  # Sources already fetched
                emitter=emitter,
            )

            pipeline_input = AgentPipelineInput(
                procedure_title=procedure,
                context=context,
                max_iterations=3,
                quality_threshold=8,
            )

            pipeline_result = orchestrator.run(
                input_data=pipeline_input,
                sources=agent_sources,
            )

            if pipeline_result.success and pipeline_result.procedure_markdown:
                md = pipeline_result.procedure_markdown
                orchestrator_quality_score = pipeline_result.quality_score
                orchestrator_iterations = pipeline_result.iterations_used
                orchestrator_cost = pipeline_result.total_cost_usd
            else:
                # Fallback to simple writer if orchestrator fails
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
                orchestrator_quality_score = None
                orchestrator_iterations = 1
                orchestrator_cost = 0.0
        else:
            # Use simple writer for dummy mode or when LLM is disabled
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
            orchestrator_quality_score = None
            orchestrator_iterations = 1
            orchestrator_cost = 0.0

        # Skip citation validation for orchestrator output - agents do their own validation
        if orchestrator_quality_score is None:
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

        # Use orchestrator quality score if available, otherwise calculate from evidence
        if orchestrator_quality_score is not None:
            quality_score = orchestrator_quality_score
        else:
            # Calculate quality score based on evidence coverage
            supported = int(evidence.get("supported_count") or 0)
            unsupported = int(evidence.get("unsupported_count") or 0)
            total_claims = supported + unsupported
            if total_claims > 0:
                # Score 1-10 based on support ratio, with minimum of 5 for having any claims
                quality_score = max(5, min(10, 5 + int((supported / total_claims) * 5)))
            else:
                quality_score = 5  # Default score when no claims to validate

        docx_path = run_dir / "Procedure.docx"
        write_procedure_docx(
            markdown_text=md,
            sources=sources,
            output_path=docx_path,
            run_id=run_id,
            manifest_hash=manifest_hash,
            template_path=settings.docx_template_path,
            quality_score=quality_score,
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

        # Get cost summary from session tracker
        cost_summary = get_session_tracker().get_summary()

        # Combine orchestrator cost with session tracker cost
        total_cost = cost_summary.total_cost_usd + orchestrator_cost

        return {
            "run_dir": str(run_dir),
            "sources_jsonl_path": str(sources_jsonl_path),
            "procedure_md_path": str(procedure_md_path),
            "manifest_path": str(manifest_path),
            "docx_path": str(docx_path),
            "quality_score": quality_score,
            "iterations_used": orchestrator_iterations,
            "total_cost_usd": total_cost,
            "total_input_tokens": cost_summary.total_input_tokens,
            "total_output_tokens": cost_summary.total_output_tokens,
        }
    finally:
        http.close()
        # Clean up event emitter when pipeline completes
        remove_emitter(run_id)


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
    evidence_hierarchy: EvidenceHierarchy,
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
        # Classify evidence level for seed URL source
        seed_evidence_level = evidence_hierarchy.classify_source(
            url=url,
            kind="guideline_url",
            title=title,
        )
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
                extra={
                    "final_url": resp.url,
                    "evidence_level": seed_evidence_level.level_id,
                    "evidence_badge": seed_evidence_level.badge,
                    "evidence_badge_color": seed_evidence_level.badge_color,
                    "evidence_priority": seed_evidence_level.priority,
                },
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

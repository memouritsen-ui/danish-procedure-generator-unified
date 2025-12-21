from __future__ import annotations

import contextlib
import logging
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

from procedurewriter.agents.meta_analysis.orchestrator import (
    MetaAnalysisOrchestrator,
    OrchestratorInput,
)
from procedurewriter.agents.meta_analysis.screener_agent import PICOQuery
from procedurewriter.agents.models import PipelineInput as AgentPipelineInput
from procedurewriter.agents.models import SourceReference
from procedurewriter.config_store import load_yaml
from procedurewriter.db import LibrarySourceRow
from procedurewriter.llm import get_session_tracker, reset_session_tracker
from procedurewriter.llm.providers import get_llm_client
from procedurewriter.pipeline.citations import validate_citations
from procedurewriter.pipeline.docx_writer import (
    write_evidence_review_docx,
    write_meta_analysis_docx,
    write_procedure_docx,
    write_source_analysis_docx,
)
from procedurewriter.pipeline.events import EventType, get_emitter, remove_emitter
from procedurewriter.pipeline.evidence import (
    EvidenceGapAcknowledgementRequired,
    EvidencePolicyError,
    build_evidence_report,
    enforce_evidence_policy,
)
from procedurewriter.pipeline.evidence_hierarchy import EvidenceHierarchy
from procedurewriter.pipeline.fetcher import CachedHttpClient
from procedurewriter.pipeline.io import write_json, write_jsonl, write_text
from procedurewriter.pipeline.library_search import LibrarySearchProvider
from procedurewriter.pipeline.manifest import update_manifest_artifact, write_manifest
from procedurewriter.pipeline.normalize import normalize_html, normalize_pdf_pages, normalize_pubmed, extract_pdf_pages
from procedurewriter.pipeline.international_sources import InternationalSourceAggregator
from procedurewriter.pipeline.pubmed import PubMedClient
from procedurewriter.pipeline.retrieve import build_snippets, retrieve
from procedurewriter.pipeline.source_scoring import SourceScore, rank_sources
from procedurewriter.pipeline.sources import make_source_id, to_jsonl_record, write_source_files
from procedurewriter.pipeline.structure_validator import (
    StructureValidationError,
    validate_required_sections,
)
from procedurewriter.pipeline.types import SourceRecord
from procedurewriter.pipeline.writer import write_procedure_markdown
from procedurewriter.settings import Settings

# Style profile imports
from procedurewriter.agents.style_agent import StyleAgent, StyleInput, StyleValidationError
from procedurewriter.db import get_default_style_profile
from procedurewriter.llm.providers import LLMProvider
from procedurewriter.models.style_profile import StyleProfile

# Content generalization
from procedurewriter.pipeline.content_generalizer import ContentGeneralizer

logger = logging.getLogger(__name__)

_INTERNATIONAL_KINDS = {"nice_guideline", "cochrane_review", "international_guideline", "who_guideline"}


def _apply_style_profile(
    *,
    raw_markdown: str,
    sources: list[SourceRecord],
    procedure_name: str,
    style_profile: StyleProfile | None,
    llm: LLMProvider | None,
    model: str | None,
    outline: list[str] | None,
    strict_mode: bool,
) -> str:
    """Apply style profile to markdown using StyleAgent.

    Returns original markdown if no profile or LLM available.
    """
    if style_profile is None or llm is None:
        return raw_markdown

    try:
        # Use GPT-5.2 as default for gold-standard output (not gpt-4)
        agent = StyleAgent(llm=llm, model=model or "gpt-5.2")
        result = agent.execute(
            StyleInput(
                procedure_title=procedure_name,
                raw_markdown=raw_markdown,
                sources=sources,
                style_profile=style_profile,
                outline=outline,
            ),
            strict_mode=strict_mode,
        )

        if result.output.success:
            return result.output.polished_markdown

        # Non-strict mode: log and return original
        logger.warning("StyleAgent failed: %s", result.output.error)
        if strict_mode:
            raise StyleValidationError(result.output.error or "StyleAgent failed in strict mode")
        return raw_markdown

    except Exception as e:
        logger.warning("StyleAgent error: %s", e)
        if strict_mode:
            raise
        return raw_markdown


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

    # Compute evidence_policy EARLY - before _enforce_source_requirements is called
    # Default to STRICT evidence policy for gold-standard output
    # Only override if explicitly configured in author guide
    evidence_policy = "strict"
    missing_tier_policy = settings.missing_tier_policy
    if isinstance(author_guide, dict):
        validation = author_guide.get("validation")
        if isinstance(validation, dict):
            p = validation.get("evidence_policy")
            if isinstance(p, str) and p.strip():
                evidence_policy = p.strip().lower()
            m = validation.get("missing_tier_policy")
            if isinstance(m, str) and m.strip():
                missing_tier_policy = m.strip().lower()

    http = CachedHttpClient(cache_dir=settings.cache_dir)
    try:
        sources: list[SourceRecord] = []
        source_n = 1
        warnings: list[str] = []
        orchestrator_cost = 0.0
        orchestrator_stop_reason: str | None = None
        post_manifest_artifacts: list[tuple[str, Path]] = []
        availability_stats: dict[str, int] = {
            "nice_candidates": 0,
            "cochrane_candidates": 0,
            "pubmed_candidates": 0,
            "pubmed_review_candidates": 0,
        }
        seed_url_stats: dict[str, int] = {
            "total_entries": 0,
            "matched_entries": 0,
            "filtered_out": 0,
            "allowed_urls": 0,
            "blocked_urls": 0,
            "used_urls": 0,
            "fetch_failed": 0,
            "truncated": 0,
        }

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
                procedure=procedure,
                context=context,
                stats=seed_url_stats,
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

        # Search international sources (NICE/Cochrane) before local guidelines.
        if not settings.dummy_mode:
            emitter.emit(EventType.PROGRESS, {"message": "Searching international guidelines", "stage": "international_search"})
            query_text = " ".join([procedure, context or ""]).strip()
            source_n = _append_international_sources(
                query=query_text,
                http=http,
                run_dir=run_dir,
                source_n=source_n,
                sources=sources,
                warnings=warnings,
                evidence_hierarchy=evidence_hierarchy,
                max_per_tier=5,
                strict_mode=evidence_policy == "strict",
                nice_api_key=settings.nice_api_key,
                cochrane_api_key=settings.cochrane_api_key,
                nice_api_base_url=settings.nice_api_base_url,
                cochrane_api_base_url=settings.cochrane_api_base_url,
                allow_html_fallback=settings.allow_html_fallback_international,
                availability_stats=availability_stats,
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

            # Get LLM for term expansion if available (improves search quality)
            term_expansion_llm = None
            if settings.use_llm and (openai_api_key or anthropic_api_key):
                try:
                    term_expansion_llm = get_llm_client(
                        provider=settings.llm_provider,
                        openai_api_key=openai_api_key,
                        anthropic_api_key=anthropic_api_key,
                        ollama_base_url=ollama_base_url or settings.ollama_base_url,
                    )
                except Exception as e:
                    logger.warning("Could not create LLM for term expansion: %s", e)

            expanded_terms = _expand_procedure_terms(
                procedure=procedure,
                context=context,
                llm=term_expansion_llm,
                model=settings.llm_model,
            )
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

            def _is_pubmed_review(pub_types: list[str]) -> bool:
                return any(
                    str(pt).lower() in {"systematic review", "meta-analysis"}
                    for pt in pub_types
                    if pt
                )

            availability_stats["pubmed_candidates"] = len(candidates)
            availability_stats["pubmed_review_candidates"] = sum(
                1 for c in candidates
                if _is_pubmed_review(c["fetched"].article.publication_types)
            )

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

        wiley_tdm_stats: dict[str, int] | None = None
        if not settings.dummy_mode:
            tdm_token = _resolve_wiley_tdm_token(settings)
            tdm_enabled = settings.enable_wiley_tdm or bool(tdm_token)
            if tdm_enabled:
                if not tdm_token:
                    msg = (
                        "Wiley TDM enabled but no token found. "
                        "Set PROCEDUREWRITER_WILEY_TDM_TOKEN, TDM_API_TOKEN, or WILEY_TDM_TOKEN."
                    )
                    if evidence_policy == "strict":
                        raise EvidencePolicyError(msg)
                    warnings.append(msg)
                else:
                    wiley_tdm_stats = _apply_wiley_tdm_fulltext(
                        sources=sources,
                        http=http,
                        run_dir=run_dir,
                        token=tdm_token,
                        base_url=settings.wiley_tdm_base_url,
                        max_downloads=settings.wiley_tdm_max_downloads,
                        allow_non_wiley_doi=settings.wiley_tdm_allow_non_wiley_doi,
                        strict_mode=evidence_policy == "strict",
                        use_client=settings.wiley_tdm_use_client,
                    )
                    if wiley_tdm_stats.get("failed"):
                        warnings.append(
                            f"Wiley TDM failures: {wiley_tdm_stats['failed']} (check run logs)."
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

        selection_report = _build_source_selection_report(
            sources=sources,
            settings=settings,
            warnings=warnings,
            availability=availability_stats,
            seed_url_stats=seed_url_stats,
        )
        selection_report_path = run_dir / "source_selection.json"
        write_json(selection_report_path, selection_report)
        post_manifest_artifacts.append(("source_selection_report", selection_report_path))

        _enforce_source_requirements(
            sources=sources,
            settings=settings,
            warnings=warnings,
            evidence_policy=evidence_policy,
            availability=availability_stats,
            missing_tier_policy=missing_tier_policy,
        )

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

        llm: LLMProvider | None = None
        if settings.use_llm and not settings.dummy_mode:
            llm = get_llm_client(
                provider=settings.llm_provider,
                openai_api_key=openai_api_key,
                anthropic_api_key=anthropic_api_key,
                ollama_base_url=ollama_base_url or settings.ollama_base_url,
            )

        # Pre-compute quantitative evidence context BEFORE writing
        # This allows writers to incorporate meta-analysis findings into content generation
        quantitative_candidates = _collect_quantitative_candidates(sources)
        meta_summary_lines: list[str] = []
        fallback_lines: list[str] = []

        if llm and len(quantitative_candidates) >= 2:
            emitter.emit(EventType.PROGRESS, {
                "message": f"Running automated meta-analysis on {len(quantitative_candidates)} studies",
                "stage": "meta_analysis",
            })

            try:
                ma_pico = PICOQuery(
                    population=context or "Patients",
                    intervention=procedure,
                    comparison="Standard Care",
                    outcome="Primary Clinical Outcome",
                )

                ma_input = OrchestratorInput(
                    query=ma_pico,
                    study_sources=quantitative_candidates,
                    outcome_of_interest="Primary Clinical Outcome",
                    run_id=run_id,
                )

                ma_orchestrator = MetaAnalysisOrchestrator(
                    llm=llm,
                    emitter=emitter,
                )

                ma_result = ma_orchestrator.execute(ma_input)

                ma_report_path = run_dir / "synthesis_report.json"
                synthesis_dict = (
                    ma_result.output.model_dump()
                    if hasattr(ma_result.output, "model_dump")
                    else ma_result.output.dict()
                )
                write_json(ma_report_path, synthesis_dict)

                ma_docx_path = run_dir / "Procedure_MetaAnalysis.docx"
                write_meta_analysis_docx(
                    output=ma_result.output,
                    output_path=ma_docx_path,
                    run_id=run_id,
                )

                post_manifest_artifacts.append(("meta_analysis_docx", ma_docx_path))
                post_manifest_artifacts.append(("synthesis_report", ma_report_path))

                orchestrator_cost += ma_result.stats.cost_usd

                meta_summary_lines = _format_meta_analysis_summary(
                    synthesis=ma_result.output.synthesis,
                    included_ids=ma_result.output.included_study_ids,
                    fallback_ids=[c["study_id"] for c in quantitative_candidates],
                )

            except Exception as e:
                logger.error("Meta-analysis failed: %s", e)
                emitter.emit(EventType.ERROR, {"error": f"Meta-analysis failed: {str(e)}"})

        if not meta_summary_lines and quantitative_candidates:
            # Narrative fallback when meta-analysis fails or is skipped but we have quantitative sources
            fallback_lines = _format_narrative_evidence_fallback(
                candidates=quantitative_candidates,
                sources=sources,
            )

        evidence_summary_lines = meta_summary_lines or fallback_lines
        evidence_summary_text = "\n".join(evidence_summary_lines).strip() if evidence_summary_lines else None

        quantitative_evidence_context = _compute_quantitative_evidence_context(
            sources=sources,
            candidates=quantitative_candidates,
            summary_lines=evidence_summary_lines,
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

            if llm is None:
                raise RuntimeError("LLM client unavailable for orchestrator run.")

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
                max_iterations=settings.quality_loop_max_iterations,
                quality_threshold=settings.quality_loop_quality_threshold,
                quality_loop_policy=settings.quality_loop_policy,
                quality_loop_max_cost_usd=settings.quality_loop_max_cost_usd,
                outline=_author_guide_outline(author_guide) if isinstance(author_guide, dict) else None,
                style_guide=_author_guide_style_text(author_guide) if isinstance(author_guide, dict) else None,
                evidence_summary=evidence_summary_text,
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
                orchestrator_stop_reason = pipeline_result.quality_loop_stop_reason
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
                    quantitative_evidence_context=quantitative_evidence_context,
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
                quantitative_evidence_context=quantitative_evidence_context,
            )
            orchestrator_quality_score = None
            orchestrator_iterations = 1
            orchestrator_cost = 0.0

        # Skip citation validation for orchestrator output - agents do their own validation
        if orchestrator_quality_score is None:
            validate_citations(md, valid_source_ids={s.source_id for s in sources})

        # Inject evidence summary into markdown BEFORE style polishing
        if evidence_summary_lines:
            md = _replace_section(
                md,
                heading="Evidens og Meta-analyse",
                new_lines=evidence_summary_lines,
                strict_mode=True,
            )

        # Apply style profile if available (LLM-powered markdown polishing)
        style_profile_data = get_default_style_profile(settings.db_path)
        style_profile: StyleProfile | None = None
        if style_profile_data:
            style_profile = StyleProfile.from_db_dict(style_profile_data)

        if style_profile and settings.use_llm and not settings.dummy_mode:
            style_outline = _author_guide_outline(author_guide) if isinstance(author_guide, dict) else None
            style_strict_mode = evidence_policy == "strict"
            try:
                style_llm = get_llm_client(
                    provider=settings.llm_provider,
                    openai_api_key=openai_api_key,
                    anthropic_api_key=anthropic_api_key,
                    ollama_base_url=ollama_base_url or settings.ollama_base_url,
                )
                polished_md = _apply_style_profile(
                    raw_markdown=md,
                    sources=sources,
                    procedure_name=procedure,
                    style_profile=style_profile,
                    llm=style_llm,
                    model=settings.llm_model,
                    outline=style_outline,
                    strict_mode=style_strict_mode,
                )
            except Exception as e:
                logger.warning("Failed to apply style profile: %s", e)
                if style_strict_mode:
                    raise
                polished_md = md
        else:
            polished_md = md

        # Generalize hospital-specific content to universal Danish output
        generalizer = ContentGeneralizer(use_lokal_markers=True)
        final_md, gen_stats = generalizer.generalize(polished_md)
        if gen_stats.total_replacements > 0:
            logger.info(
                "Generalized content: %d replacements (phones=%d, rooms=%d, locations=%d, hospitals=%d)",
                gen_stats.total_replacements,
                gen_stats.phone_numbers,
                gen_stats.room_references,
                gen_stats.location_references,
                gen_stats.hospital_references,
            )

        required_headings = _author_guide_outline(author_guide) if isinstance(author_guide, dict) else []
        if required_headings:
            structure_result = validate_required_sections(
                final_md,
                required_headings=required_headings,
            )
            structure_report_path = run_dir / "structure_validation.json"
            write_json(structure_report_path, structure_result.to_dict())
            post_manifest_artifacts.append(("structure_validation", structure_report_path))
            if not structure_result.is_valid:
                raise StructureValidationError(
                    "Structure validation failed: "
                    f"missing={structure_result.missing_headings}, "
                    f"out_of_order={structure_result.out_of_order_headings}, "
                    f"wrong_level={structure_result.wrong_level_headings}. "
                    "See structure_validation.json for details."
                )

        # Validate citations against final markdown
        validate_citations(final_md, valid_source_ids={s.source_id for s in sources})

        procedure_md_path = run_dir / "procedure.md"
        write_text(procedure_md_path, final_md)

        # evidence_policy is already computed at the top of run_pipeline()

        # Run evidence verification if enabled and Anthropic key is available
        verification_cost = 0.0
        verification_result: dict[str, Any] | None = None
        if (
            settings.enable_evidence_verification
            and anthropic_api_key
            and not settings.dummy_mode
            and sources
        ):
            try:
                import asyncio

                from anthropic import AsyncAnthropic

                from procedurewriter.pipeline.evidence_verifier import (
                    summary_to_dict,
                    verify_all_citations,
                )

                emitter.emit(EventType.PROGRESS, {"message": "Verifying evidence", "stage": "verification"})

                source_contents: dict[str, str] = {}
                for src in sources:
                    if src.normalized_path:
                        norm_path = Path(src.normalized_path)
                        if norm_path.exists():
                            source_contents[src.source_id] = norm_path.read_text(
                                encoding="utf-8", errors="replace"
                            )

                async def run_verification() -> tuple:
                    client = AsyncAnthropic(api_key=anthropic_api_key)
                    return await verify_all_citations(
                        markdown_text=final_md,
                        sources=source_contents,
                        anthropic_client=client,
                        max_concurrent=5,
                        max_verifications=50,
                    )

                verification_summary, verification_cost = asyncio.run(run_verification())

                # Use summary_to_dict which includes "sentences" for build_evidence_report compatibility
                verification_result = summary_to_dict(verification_summary)
                verification_result["verification_cost_usd"] = verification_cost

                verification_path = run_dir / "evidence_verification.json"
                write_json(verification_path, verification_result)

                emitter.emit(EventType.PROGRESS, {
                    "message": f"Evidence verified: {verification_summary.overall_score}% supported",
                    "stage": "verification_complete",
                    "score": verification_summary.overall_score,
                })

            except Exception as e:
                logger.warning("Evidence verification failed: %s", e)
                verification_result = {"error": str(e)}

        # Build evidence report AFTER verification so we can include verification results
        # The verification_result includes "sentences" key for build_evidence_report compatibility
        evidence_report_path = run_dir / "evidence_report.json"
        evidence = build_evidence_report(
            final_md,
            snippets=snippets,
            verification_results=verification_result,  # Pass verification results if available
        )
        write_json(evidence_report_path, evidence)

        # Strict mode enforcement for evidence verification
        # Read verification requirements from author guide
        require_verification = False
        min_verification_score = 70.0  # Default minimum score
        if isinstance(author_guide, dict):
            validation = author_guide.get("validation")
            if isinstance(validation, dict):
                require_verification = validation.get("require_evidence_verification", False)
                score_setting = validation.get("min_verification_score")
                if isinstance(score_setting, (int, float)):
                    min_verification_score = float(score_setting)

        # In strict mode, evidence verification is required by default
        if evidence_policy == "strict":
            require_verification = True

        if require_verification:
            if not anthropic_api_key:
                raise EvidencePolicyError(
                    "Evidence verification required in strict mode but ANTHROPIC_API_KEY not set. "
                    "Set the key or use evidence_policy: warn in author_guide.yaml."
                )
            if verification_result is None:
                raise EvidencePolicyError(
                    "Evidence verification required but not performed. "
                    "Check that enable_evidence_verification is True in settings."
                )
            if "error" in verification_result:
                raise EvidencePolicyError(
                    f"Evidence verification required but failed: {verification_result.get('error')}"
                )
            actual_score = verification_result.get("overall_score", 0)
            if actual_score < min_verification_score:
                raise EvidencePolicyError(
                    f"Evidence verification score {actual_score}% below minimum {min_verification_score}%. "
                    f"Fully supported: {verification_result.get('fully_supported', 0)}, "
                    f"Not supported: {verification_result.get('not_supported', 0)}, "
                    f"Contradicted: {verification_result.get('contradicted', 0)}. "
                    "Fix evidence gaps or lower min_verification_score in author_guide.yaml."
                )

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
        if orchestrator_stop_reason:
            runtime["quality_loop_stop_reason"] = orchestrator_stop_reason
        if warnings:
            runtime["warnings"] = warnings[:20]
        if verification_result:
            runtime["evidence_verification"] = verification_result
        if wiley_tdm_stats is not None:
            runtime["wiley_tdm"] = wiley_tdm_stats

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

        for artifact_key, artifact_path in post_manifest_artifacts:
            update_manifest_artifact(
                manifest_path=manifest_path,
                artifact_key=artifact_key,
                artifact_path=artifact_path,
            )

        if not settings.dummy_mode:
            enforce_evidence_policy(evidence, policy=evidence_policy)

        if orchestrator_quality_score is not None:
            quality_score = orchestrator_quality_score
        else:
            supported = int(evidence.get("supported_count") or 0)
            unsupported = int(evidence.get("unsupported_count") or 0)
            total_claims = supported + unsupported
            if total_claims > 0:
                quality_score = max(5, min(10, 5 + int((supported / total_claims) * 5)))
            else:
                quality_score = 5

        docx_path = run_dir / "Procedure.docx"
        write_procedure_docx(
            markdown_text=final_md,
            sources=sources,
            output_path=docx_path,
            run_id=run_id,
            manifest_hash=manifest_hash,
            template_path=settings.docx_template_path,
            quality_score=quality_score,
        )

        # ---------------------------------------------------------------------
        # VERBOSE DOCUMENTATION: Source Analysis & Evidence Review
        # ---------------------------------------------------------------------
        # Generate source analysis DOCX (explains how sources were found/scored)
        source_analysis_path = run_dir / "source_analysis.docx"
        write_source_analysis_docx(
            sources=sources,
            procedure=procedure,
            run_id=run_id,
            output_path=source_analysis_path,
            search_terms=None,  # Terms not preserved in scope - sources contain metadata
        )
        update_manifest_artifact(
            manifest_path=manifest_path,
            artifact_key="source_analysis_docx",
            artifact_path=source_analysis_path,
        )

        # Generate evidence review DOCX (explains claim verification)
        evidence_review_path = run_dir / "evidence_review.docx"
        write_evidence_review_docx(
            evidence_report=evidence,
            sources=sources,
            procedure=procedure,
            run_id=run_id,
            output_path=evidence_review_path,
        )
        update_manifest_artifact(
            manifest_path=manifest_path,
            artifact_key="evidence_review_docx",
            artifact_path=evidence_review_path,
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
        total_cost = cost_summary.total_cost_usd + orchestrator_cost + verification_cost

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


def _has_international_sources(sources: list[SourceRecord]) -> bool:
    for src in sources:
        if src.kind in _INTERNATIONAL_KINDS:
            return True
        if src.extra.get("international_source_type"):
            return True
    return False


def _has_danish_guidelines(sources: list[SourceRecord]) -> bool:
    return any(src.kind == "danish_guideline" for src in sources)


def _compute_tier_details(
    sources: list[SourceRecord],
    settings: Settings,
    availability: dict[str, int] | None = None,
) -> dict[str, dict[str, Any]]:
    """Compute tier details for source selection report.

    Returns a dict with tier names as keys, each containing:
    - count: number of sources in this tier
    - required: whether this tier is required
    - sources: list of source IDs in this tier
    - when_available: True for tiers that are required "when available" (soft requirement)
    """
    tier_details: dict[str, dict[str, Any]] = {}

    # NICE sources
    nice_sources = [s for s in sources if s.kind == "nice_guideline"
                    or (s.extra.get("international_source_type") == "nice")]
    nice_available = availability.get("nice_candidates") if availability else None
    tier_details["nice"] = {
        "count": len(nice_sources),
        "required": (nice_available > 0) if isinstance(nice_available, int) else True,
        "when_available": True,
        "sources": [s.source_id for s in nice_sources],
        "available_candidates": nice_available,
    }

    # Cochrane sources
    cochrane_sources = [s for s in sources if s.kind == "cochrane_review"
                        or (s.extra.get("international_source_type") == "cochrane")
                        or "cochranelibrary.com" in (s.url or "")]
    cochrane_available = availability.get("cochrane_candidates") if availability else None
    tier_details["cochrane"] = {
        "count": len(cochrane_sources),
        "required": (cochrane_available > 0) if isinstance(cochrane_available, int) else True,
        "when_available": True,
        "sources": [s.source_id for s in cochrane_sources],
        "available_candidates": cochrane_available,
    }

    # PubMed meta-analyses/systematic reviews (required "when available")
    pubmed_reviews = [
        s for s in sources
        if s.kind == "pubmed"
        and isinstance(s.extra, dict)
        and any(
            pt.lower() in ("systematic review", "meta-analysis")
            for pt in (s.extra.get("publication_types") or [])
            if isinstance(pt, str)
        )
    ]
    pubmed_review_available = availability.get("pubmed_review_candidates") if availability else None
    pubmed_total_available = availability.get("pubmed_candidates") if availability else None
    tier_details["pubmed_reviews"] = {
        "count": len(pubmed_reviews),
        "required": (pubmed_review_available > 0) if isinstance(pubmed_review_available, int) else True,
        "when_available": True,  # Soft requirement - only enforced when sources exist
        "sources": [s.source_id for s in pubmed_reviews],
        "available_candidates": pubmed_review_available,
        "total_pubmed_candidates": pubmed_total_available,
    }

    # Danish guidelines
    danish_sources = [s for s in sources if s.kind == "danish_guideline"]
    tier_details["danish"] = {
        "count": len(danish_sources),
        "required": settings.require_danish_guidelines,
        "when_available": False,
        "sources": [s.source_id for s in danish_sources],
    }

    # Seed URLs (from guideline_url kind)
    seed_sources = [s for s in sources if s.kind == "guideline_url"]
    tier_details["seed_urls"] = {
        "count": len(seed_sources),
        "required": False,
        "when_available": False,
        "sources": [s.source_id for s in seed_sources],
    }

    return tier_details


def _build_source_selection_report(
    *,
    sources: list[SourceRecord],
    settings: Settings,
    warnings: list[str],
    availability: dict[str, int] | None = None,
    seed_url_stats: dict[str, int] | None = None,
) -> dict[str, Any]:
    by_kind: dict[str, int] = {}
    by_evidence_level: dict[str, int] = {}
    for src in sources:
        by_kind[src.kind] = by_kind.get(src.kind, 0) + 1
        level = str(src.extra.get("evidence_level") or "unknown")
        by_evidence_level[level] = by_evidence_level.get(level, 0) + 1

    has_international = _has_international_sources(sources)
    has_danish = _has_danish_guidelines(sources)
    missing: list[str] = []
    if settings.require_international_sources and not has_international:
        missing.append("international (NICE/Cochrane)")
    if settings.require_danish_guidelines and not has_danish:
        missing.append("Danish guidelines")

    # Compute tier details
    tier_details = _compute_tier_details(sources, settings, availability)

    return {
        "version": 2,  # Bumped for tier_details addition
        "generated_at_utc": _utc_now_iso(),
        "requirements": {
            "require_international_sources": settings.require_international_sources,
            "require_danish_guidelines": settings.require_danish_guidelines,
            "has_international_sources": has_international,
            "has_danish_guidelines": has_danish,
            "missing": missing,
        },
        "tier_details": tier_details,  # Per-tier breakdown with "when available" info
        "availability": availability or {},
        "seed_url_stats": seed_url_stats or {},
        "counts": {
            "total_sources": len(sources),
            "by_kind": by_kind,
            "by_evidence_level": by_evidence_level,
        },
        "sources": [
            {
                "source_id": src.source_id,
                "kind": src.kind,
                "title": src.title,
                "year": src.year,
                "url": src.url,
                "evidence_level": src.extra.get("evidence_level"),
                "evidence_priority": src.extra.get("evidence_priority"),
            }
            for src in sources
        ],
        "warnings": warnings[:50],
    }


def _enforce_source_requirements(
    *,
    sources: list[SourceRecord],
    settings: Settings,
    warnings: list[str],
    availability: dict[str, int] | None = None,
    evidence_policy: str = "strict",
    missing_tier_policy: str = "strict_fail",
) -> None:
    """Enforce per-tier source requirements for gold-standard output.

    In strict mode, requires:
    - At least one NICE source
    - At least one Cochrane source
    - At least one PubMed meta-analysis/systematic review (when available)
    - Danish guidelines when require_danish_guidelines is True
    """
    if settings.dummy_mode:
        return

    missing: list[str] = []

    # Check NICE sources
    nice_sources = [s for s in sources if s.kind == "nice_guideline"
                    or (s.extra.get("international_source_type") == "nice")]
    nice_available = availability.get("nice_candidates") if availability else None
    nice_required = (nice_available > 0) if isinstance(nice_available, int) else True
    if nice_required and not nice_sources:
        msg = "No NICE guideline sources found."
        if msg not in warnings:
            warnings.append(msg)
        missing.append("NICE guidelines")

    # Check Cochrane sources
    cochrane_sources = [s for s in sources if s.kind == "cochrane_review"
                        or (s.extra.get("international_source_type") == "cochrane")
                        or "cochranelibrary.com" in (s.url or "")]
    cochrane_available = availability.get("cochrane_candidates") if availability else None
    cochrane_required = (cochrane_available > 0) if isinstance(cochrane_available, int) else True
    if cochrane_required and not cochrane_sources:
        msg = "No Cochrane systematic review sources found."
        if msg not in warnings:
            warnings.append(msg)
        missing.append("Cochrane reviews")

    # Check PubMed meta-analyses/systematic reviews ("when available" tier)
    all_pubmed_sources = [s for s in sources if s.kind == "pubmed"]
    pubmed_reviews = [
        s for s in all_pubmed_sources
        if isinstance(s.extra, dict)
        and any(
            pt.lower() in ("systematic review", "meta-analysis")
            for pt in (s.extra.get("publication_types") or [])
            if isinstance(pt, str)
        )
    ]
    pubmed_review_available = availability.get("pubmed_review_candidates") if availability else None
    pubmed_required = (
        pubmed_review_available > 0 if isinstance(pubmed_review_available, int) else len(all_pubmed_sources) > 0
    )
    if pubmed_required and not pubmed_reviews:
        msg = "No PubMed systematic reviews or meta-analyses found among PubMed sources."
        if msg not in warnings:
            warnings.append(msg)
        missing.append("PubMed meta-analyses")

    # Check for general international sources (legacy check)
    if settings.require_international_sources and not _has_international_sources(sources):
        available_international = None
        if availability:
            available_international = (availability.get("nice_candidates", 0) > 0) or (
                availability.get("cochrane_candidates", 0) > 0
            )
        if available_international is None or available_international:
            if "international (NICE/Cochrane)" not in missing:
                msg = "No international sources found (NICE/Cochrane)."
                if msg not in warnings:
                    warnings.append(msg)
                missing.append("international (NICE/Cochrane)")

    # Check Danish guidelines
    if settings.require_danish_guidelines and not _has_danish_guidelines(sources):
        msg = "No Danish guideline sources found in local library."
        if msg not in warnings:
            warnings.append(msg)
        missing.append("Danish guidelines")

    # Only fail in strict mode
    if missing and evidence_policy == "strict":
        missing_text = ", ".join(missing)
        if missing_tier_policy == "allow_with_ack":
            raise EvidenceGapAcknowledgementRequired(
                "Evidence gaps require user acknowledgement before proceeding.",
                missing_tiers=missing,
                availability=availability or {},
            )
        raise EvidencePolicyError(
            "Evidence policy STRICT failed: required source tiers missing. "
            f"Missing: {missing_text}. See source_selection.json for tier details."
        )


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


@dataclass(frozen=True)
class _SeedUrlEntry:
    """A seed URL with optional procedure keyword filtering."""

    url: str
    keywords: list[str]  # Empty list means no filtering (always include)


def _seed_urls(allowlist: dict[str, Any]) -> list[_SeedUrlEntry]:
    """Extract seed URLs from allowlist config.

    Seed URLs can be either:
    - Simple strings: "https://example.com/page" (always included)
    - Dicts with url key: {"url": "https://example.com", "procedure_keywords": [...]}
      (only included if keywords match the procedure + context)
    """
    urls = allowlist.get("seed_urls", []) if isinstance(allowlist, dict) else []
    out: list[_SeedUrlEntry] = []
    for u in urls:
        if isinstance(u, dict):
            # Dict format with optional keywords
            url = u.get("url", "").strip()
            keywords = u.get("procedure_keywords", [])
            if isinstance(keywords, str):
                keywords = [keywords]
            keywords = [k.strip().lower() for k in keywords if k and isinstance(k, str)]
        else:
            # Simple string format - no filtering
            url = str(u).strip()
            keywords = []
        if url:
            out.append(_SeedUrlEntry(url=url, keywords=keywords))
    return out


def _matches_procedure_keywords(
    entry: _SeedUrlEntry, *, procedure: str, context: str | None
) -> bool:
    """Check if a seed URL entry matches the procedure/context.

    Returns True if:
    - The entry has no keywords (always matches)
    - Any keyword appears in procedure or context (case-insensitive)
    """
    if not entry.keywords:
        # No keywords means always include
        return True

    search_text = f"{procedure} {context or ''}".lower()
    return any(kw in search_text for kw in entry.keywords)


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
    procedure: str,
    context: str | None,
    stats: dict[str, int] | None = None,
) -> int:
    prefixes = _allowlist_prefixes(allowlist)
    all_entries = _seed_urls(allowlist)
    if not all_entries:
        return source_n

    if stats is not None:
        stats["total_entries"] += len(all_entries)

    # Filter entries by procedure_keywords matching
    matching_entries = [
        e for e in all_entries
        if _matches_procedure_keywords(e, procedure=procedure, context=context)
    ]

    filtered_count = len(all_entries) - len(matching_entries)
    if filtered_count > 0:
        warnings.append(
            f"seed_urls: {filtered_count} URL(s) filtered out (keywords not matching procedure)"
        )
    if stats is not None:
        stats["matched_entries"] += len(matching_entries)
        stats["filtered_out"] += filtered_count

    if not matching_entries:
        return source_n

    # Keep conservative; users can still ingest many URLs via the UI.
    max_per_run = 8
    urls = [e.url for e in matching_entries]
    for url in urls[:max_per_run]:
        if not _is_allowed_url(url, prefixes=prefixes):
            warnings.append(f"Seed URL not allowed by allowlist: {url}")
            if stats is not None:
                stats["blocked_urls"] += 1
            continue
        if stats is not None:
            stats["allowed_urls"] += 1
        try:
            resp = http.get(url)
        except Exception as e:  # noqa: BLE001
            warnings.append(f"Seed URL fetch failed for {url}: {e}")
            if stats is not None:
                stats["fetch_failed"] += 1
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
        if stats is not None:
            stats["used_urls"] += 1

    if len(urls) > max_per_run:
        warnings.append(f"seed_urls truncated: using first {max_per_run} of {len(urls)}")
        if stats is not None:
            stats["truncated"] += len(urls) - max_per_run
    return source_n


def _append_international_sources(
    *,
    query: str,
    http: CachedHttpClient,
    run_dir: Path,
    source_n: int,
    sources: list[SourceRecord],
    warnings: list[str],
    evidence_hierarchy: EvidenceHierarchy,
    max_per_tier: int = 5,
    strict_mode: bool = False,
    nice_api_key: str | None = None,
    cochrane_api_key: str | None = None,
    nice_api_base_url: str | None = None,
    cochrane_api_base_url: str | None = None,
    allow_html_fallback: bool = False,
    availability_stats: dict[str, int] | None = None,
) -> int:
    aggregator = InternationalSourceAggregator(
        http_client=http,
        strict_mode=strict_mode,
        nice_api_key=nice_api_key,
        cochrane_api_key=cochrane_api_key,
        nice_api_base_url=nice_api_base_url,
        cochrane_api_base_url=cochrane_api_base_url,
        allow_html_fallback=allow_html_fallback,
    )
    results, stats = aggregator.search_all_with_stats(query, max_per_tier=max_per_tier)
    if availability_stats is not None:
        availability_stats["nice_candidates"] += stats.get("nice_candidates", 0)
        availability_stats["cochrane_candidates"] += stats.get("cochrane_candidates", 0)
    if not results:
        warnings.append("No international sources found (NICE/Cochrane).")
        return source_n

    for result in results:
        if not result.url:
            continue
        try:
            resp = http.get(result.url)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"International source fetch failed: {result.url} ({exc})")
            continue

        raw_bytes = resp.content
        raw_suffix = ".html"
        normalized_text = ""

        if raw_bytes[:4] == b"%PDF" or result.url.lower().endswith(".pdf"):
            raw_suffix = ".pdf"
            pdf_path = run_dir / "raw" / f"tmp_{source_n}.pdf"
            pdf_path.write_bytes(raw_bytes)
            pages = extract_pdf_pages(pdf_path)
            normalized_text = normalize_pdf_pages(pages)
        else:
            normalized_text = normalize_html(raw_bytes)

        if not normalized_text:
            if result.abstract:
                normalized_text = f"{result.title}\n\n{result.abstract}"
            else:
                warnings.append(f"International source had no extractable text: {result.url}")
                continue

        source_id = make_source_id(source_n)
        source_n += 1

        written = write_source_files(
            run_dir=run_dir,
            source_id=source_id,
            raw_bytes=raw_bytes,
            raw_suffix=raw_suffix,
            normalized_text=normalized_text,
        )

        evidence_level = evidence_hierarchy.classify_source(
            url=result.url,
            kind="international_guideline",
            title=result.title,
        )

        sources.append(
            SourceRecord(
                source_id=source_id,
                fetched_at_utc=_utc_now_iso(),
                kind=result.source_type,
                title=result.title,
                year=result.publication_year,
                url=result.url,
                doi=None,
                pmid=None,
                raw_path=str(written.raw_path),
                normalized_path=str(written.normalized_path),
                raw_sha256=written.raw_sha256,
                normalized_sha256=written.normalized_sha256,
                extraction_notes=f"International source: {result.source_type}",
                terms_licence_note="International guideline/review. Verify rights for full text use.",
                extra={
                    "international_source_type": result.source_type,
                    "evidence_level": evidence_level.level_id,
                    "evidence_badge": evidence_level.badge,
                    "evidence_badge_color": evidence_level.badge_color,
                    "evidence_priority": evidence_level.priority,
                },
            )
        )

    return source_n


class SectionNotFoundError(ValueError):
    """Raised when a required section heading is not found in strict mode."""
    pass


def _replace_section(
    markdown_text: str,
    *,
    heading: str,
    new_lines: list[str],
    strict_mode: bool = False,
) -> str:
    """Replace a markdown section with new lines.

    Args:
        markdown_text: The markdown to modify
        heading: The section heading (without ##)
        new_lines: Lines to insert in the section
        strict_mode: If True, raise SectionNotFoundError when heading is missing.
                    If False (default), append section at end.

    Raises:
        SectionNotFoundError: When strict_mode=True and heading is not found
    """
    lines = markdown_text.splitlines()
    header = f"## {heading}".strip()
    start_idx = None
    end_idx = None
    for i, line in enumerate(lines):
        if line.strip() == header:
            start_idx = i
            continue
        if start_idx is not None and line.startswith("## "):
            end_idx = i
            break
    if start_idx is None:
        if strict_mode:
            raise SectionNotFoundError(
                f"Section '## {heading}' not found in document. "
                "In strict mode, all sections must exist in the canonical outline."
            )
        # Append new section at end (non-strict mode)
        out = lines + ["", header] + new_lines + [""]
        return "\n".join(out).strip() + "\n"
    if end_idx is None:
        end_idx = len(lines)
    out = lines[: start_idx + 1] + new_lines + lines[end_idx:]
    return "\n".join(out).strip() + "\n"


def _format_meta_analysis_summary(
    *,
    synthesis: Any | None,
    included_ids: list[str],
    fallback_ids: list[str],
) -> list[str]:
    """Build evidence summary lines with citations."""
    cite_ids = included_ids or fallback_ids
    cite = " ".join(f"[S:{sid}]" for sid in cite_ids[:6]) if cite_ids else ""
    lines: list[str] = []
    if synthesis is None:
        lines.append(f"Meta-analyse kunne ikke genereres ud fra de indsamlede kilder. {cite}".strip())
        return lines

    try:
        pooled = synthesis.pooled_estimate
        hetero = synthesis.heterogeneity
        lines.append(
            "Meta-analyse inkluderer "
            f"{synthesis.included_studies} studier (n={synthesis.total_sample_size}). "
            f"Pooled effekt={pooled.pooled_effect:.3f} "
            f"(95% CI {pooled.ci_lower:.3f}-{pooled.ci_upper:.3f}, p={pooled.p_value:.3f}). {cite}".strip()
        )
        lines.append(
            "Heterogenitet: "
            f"I2={hetero.i_squared:.1f}%, tau2={hetero.tau_squared:.3f}, "
            f"Q={hetero.cochrans_q:.2f} (p={hetero.p_value:.3f}). {cite}".strip()
        )
        lines.append(
            f"GRADE-sammenfatning: {synthesis.grade_summary} (sikkerhed: {synthesis.certainty_level}). {cite}".strip()
        )
    except Exception:
        lines.append(f"Meta-analyse opsummering kunne ikke formateres. {cite}".strip())
    return lines


def _format_narrative_evidence_fallback(
    *,
    candidates: list[dict[str, Any]],
    sources: list[SourceRecord],
) -> list[str]:
    """Build narrative evidence summary when meta-analysis is not possible.

    This provides a narrative fallback describing the available evidence
    when formal meta-analysis cannot be performed (e.g., too few studies,
    meta-analysis orchestrator unavailable, or analysis failed).
    """
    if not candidates:
        return []

    source_lookup = {s.source_id: s for s in sources}
    lines: list[str] = []

    # Build citation string
    cite_ids = [c["study_id"] for c in candidates[:6]]
    cite = " ".join(f"[S:{sid}]" for sid in cite_ids) if cite_ids else ""

    # Count study types
    sr_count = sum(1 for c in candidates if "systematic" in c.get("abstract", "").lower())
    rct_count = sum(
        1 for c in candidates
        if "randomized" in c.get("abstract", "").lower() or "rct" in c.get("abstract", "").lower()
    )
    other_count = len(candidates) - sr_count - rct_count

    if len(candidates) == 1:
        lines.append(f"Evidensen baseres på ét studie. {cite}")
    else:
        parts = []
        if sr_count:
            parts.append(f"{sr_count} systematiske reviews")
        if rct_count:
            parts.append(f"{rct_count} randomiserede studier")
        if other_count:
            parts.append(f"{other_count} andre studier")

        study_summary = ", ".join(parts) if parts else f"{len(candidates)} studier"
        lines.append(f"Evidensen baseres på {study_summary}. {cite}")

    lines.append(
        "Formel meta-analyse kunne ikke gennemføres på grund af utilstrækkelige data "
        "eller heterogenitet mellem studierne. Se de individuelle kilder for detaljer."
    )

    return lines


def _author_guide_outline(author_guide: dict[str, Any]) -> list[str]:
    sections = (author_guide.get("structure") or {}).get("sections") if isinstance(author_guide, dict) else None
    headings: list[str] = []
    for item in sections or []:
        if not isinstance(item, dict):
            continue
        heading = item.get("heading")
        if isinstance(heading, str) and heading.strip():
            headings.append(heading.strip())
    return headings


def _author_guide_style_text(author_guide: dict[str, Any]) -> str:
    if not isinstance(author_guide, dict):
        return ""
    style = author_guide.get("style") or {}
    constraints = style.get("constraints") if isinstance(style, dict) else None
    lines: list[str] = []
    if isinstance(style, dict):
        lang = style.get("language")
        tone = style.get("tone")
        audience = style.get("audience")
        if lang:
            lines.append(f"Sprog: {lang}")
        if tone:
            lines.append(f"Tone: {tone}")
        if audience:
            lines.append(f"Målgruppe: {audience}")
    if isinstance(constraints, list):
        lines.append("Krav:")
        lines.extend(f"- {c}" for c in constraints if isinstance(c, str) and c.strip())
    return "\n".join(lines).strip()


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


def _get_llm_english_terms(
    procedure: str,
    context: str | None,
    llm: Any,
    model: str,
) -> list[str]:
    """Use LLM to suggest English medical terms for a Danish procedure.

    Args:
        procedure: Danish procedure title
        context: Optional context
        llm: LLM provider instance
        model: Model name to use for completion

    Returns:
        List of English medical terms/phrases for PubMed search.
        Empty list if LLM call fails.
    """
    import json as json_module

    prompt = f"""Du er en medicinsk oversætter. Givet en dansk procedure-titel,
foreslå 2-4 engelske medicinske søgetermer til PubMed.

Dansk procedure: "{procedure}"
{f'Kontekst: "{context}"' if context else ''}

Svar KUN med en JSON-liste af engelske termer, f.eks.:
["lumbar puncture", "spinal tap", "cerebrospinal fluid collection"]

Fokusér på:
- Officielle medicinske termer (MeSH hvor muligt)
- Almindelige synonymer
- Specifikke procedure-navne"""

    try:
        response = llm.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            model=model,
            temperature=0.1,
            max_tokens=200,
        )
        content = response.content.strip()

        # Parse JSON array
        if content.startswith("["):
            terms = json_module.loads(content)
            if isinstance(terms, list):
                return [str(t).strip() for t in terms if t]
        # Try to extract JSON from response
        import re
        match = re.search(r'\[.*?\]', content, re.DOTALL)
        if match:
            terms = json_module.loads(match.group())
            if isinstance(terms, list):
                return [str(t).strip() for t in terms if t]
    except Exception as e:
        logger.warning("LLM term expansion failed, using fallback: %s", e)

    return []


def _expand_procedure_terms(
    *,
    procedure: str,
    context: str | None,
    llm: Any | None = None,
    model: str = "gpt-5.2",  # Gold-standard model for accurate term expansion
) -> list[str]:
    """Expand Danish procedure terms to include English equivalents.

    Args:
        procedure: Danish procedure title
        context: Optional context
        llm: Optional LLM provider for live translation (recommended)
        model: Model name to use for LLM completion

    Returns:
        List of search terms including Danish original and English translations.

    Strategy:
        1. If LLM provided: Use LLM to suggest English terms (most accurate)
        2. Fall back to static dictionary for known phrases
        3. Fall back to substring-based translation for components
    """
    base = procedure.strip()
    if not base:
        return []

    terms: list[str] = [base]
    lowered = base.lower().strip()

    # Strategy 1: LLM-based translation (most accurate for medical terms)
    if llm is not None:
        llm_terms = _get_llm_english_terms(procedure, context, llm, model)
        if llm_terms:
            logger.info("LLM suggested English terms: %s", llm_terms)
            terms.extend(llm_terms)

    # Strategy 2: Static dictionary lookup (fallback)
    if lowered in _DA_EN_PHRASES:
        terms.extend(_DA_EN_PHRASES[lowered])

    # Strategy 3: Substring-based translation (component matching)
    translated = lowered
    for da, en in _DA_EN_SUBSTRINGS:
        if da in translated:
            translated = translated.replace(da, f" {en} ")
    translated = " ".join(translated.split()).strip()
    if translated and translated != lowered:
        terms.append(translated)

    # Include context terms if provided
    if context:
        ctx = context.strip()
        if ctx:
            terms.append(f"{base} {ctx}")

    # Deduplicate while preserving order
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


def _collect_quantitative_candidates(sources: list[SourceRecord]) -> list[dict[str, Any]]:
    """Collect quantitative candidates for meta-analysis and evidence context."""
    candidates: list[dict[str, Any]] = []
    for src in sources:
        # Check if source has quantitative evidence indicators
        level = str(src.extra.get("evidence_level", "")).lower()
        is_quant_level = any(
            x in level
            for x in ["meta_analysis", "systematic_review", "rct", "randomized", "syst_review"]
        )

        pub_types = [str(t).lower() for t in src.extra.get("publication_types", [])]
        is_quant_pub = any(
            kw in t
            for t in pub_types
            for kw in ["randomized", "meta-analysis", "systematic review", "clinical trial"]
        )

        # Also check kind for known high-evidence source types
        is_high_evidence_kind = src.kind in {
            "pubmed", "cochrane_review", "nice_guideline", "systematic_review",
        }

        # Include if any quantitative indicator is positive
        if is_quant_level or is_quant_pub or is_high_evidence_kind:
            if src.normalized_path and Path(src.normalized_path).exists():
                text = Path(src.normalized_path).read_text(encoding="utf-8")
                candidates.append({
                    "study_id": src.source_id,
                    "title": src.title,
                    "abstract": text[:3000],
                    "source": src.kind,
                })

    return candidates


def _compute_quantitative_evidence_context(
    *,
    sources: list[SourceRecord],
    candidates: list[dict[str, Any]] | None = None,
    summary_lines: list[str] | None = None,
) -> str | None:
    """Pre-compute quantitative evidence context BEFORE writing.

    This provides key findings from systematic reviews, meta-analyses, and RCTs
    to the writer so it can incorporate evidence-based recommendations into
    the procedure content generation (not just inject after).
    """
    quantitative_sources: list[str] = []
    candidates = candidates or _collect_quantitative_candidates(sources)

    for c in candidates:
        title = c.get("title") or "Ukendt titel"
        source_id = c.get("study_id")
        source_desc = f"- [{source_id}] {title}" if source_id else f"- {title}"
        quantitative_sources.append(source_desc)

    if not quantitative_sources and not summary_lines:
        return None

    summary_text = ""
    if summary_lines:
        summary_text = "EVIDENS-SAMMENFATNING:\n" + "\n".join(summary_lines)

    sources_text = ""
    if quantitative_sources:
        sources_text = (
            "KVANTITATIV EVIDENS TILGÆNGELIG:\n"
            "Følgende kilder indeholder systematiske reviews, meta-analyser eller RCT'er. "
            "Inkludér deres konklusioner i relevante sektioner, særligt 'Evidens og Meta-analyse':\n"
            + "\n".join(quantitative_sources[:10])
        )

    return "\n\n".join([s for s in [summary_text, sources_text] if s])


_WILEY_DOI_PREFIXES = ("10.1002/", "10.1111/", "10.1113/")
_DOI_RE = re.compile(r"(10\.\d{4,9}/[^\s\"'>]+)", re.IGNORECASE)


def _resolve_wiley_tdm_token(settings: Settings) -> str | None:
    """Resolve Wiley TDM token from settings or environment."""
    if settings.wiley_tdm_token:
        return settings.wiley_tdm_token
    return os.environ.get("TDM_API_TOKEN") or os.environ.get("WILEY_TDM_TOKEN")


def _extract_doi_from_url(url: str | None) -> str | None:
    """Extract DOI from URL if present."""
    if not url:
        return None
    match = _DOI_RE.search(url)
    if not match:
        return None
    doi = match.group(1).strip()
    return doi.rstrip(").,;")


def _looks_like_wiley_source(url: str | None, doi: str | None) -> bool:
    if doi and any(doi.lower().startswith(prefix) for prefix in _WILEY_DOI_PREFIXES):
        return True
    if url:
        lowered = url.lower()
        return any(host in lowered for host in ("wiley.com", "onlinelibrary.wiley.com", "cochranelibrary.com"))
    return False


def _apply_wiley_tdm_fulltext(
    *,
    sources: list[SourceRecord],
    http: CachedHttpClient,
    run_dir: Path,
    token: str,
    base_url: str,
    max_downloads: int,
    allow_non_wiley_doi: bool,
    strict_mode: bool,
    use_client: bool = False,
) -> dict[str, int]:
    """Download full-text PDFs via Wiley TDM API and update sources in place."""
    if use_client:
        return _apply_wiley_tdm_fulltext_client(
            sources=sources,
            run_dir=run_dir,
            token=token,
            max_downloads=max_downloads,
            allow_non_wiley_doi=allow_non_wiley_doi,
            strict_mode=strict_mode,
        )

    stats = {
        "attempted": 0,
        "downloaded": 0,
        "skipped_no_doi": 0,
        "skipped_non_wiley": 0,
        "skipped_already_tdm": 0,
        "failed": 0,
        "truncated": 0,
    }
    seen_dois: set[str] = set()
    for idx, src in enumerate(sources):
        if stats["downloaded"] >= max_downloads:
            stats["truncated"] += 1
            continue

        doi = (src.doi or _extract_doi_from_url(src.url) or "").strip()
        if not doi:
            stats["skipped_no_doi"] += 1
            continue
        if doi in seen_dois:
            continue
        if not allow_non_wiley_doi and not _looks_like_wiley_source(src.url, doi):
            stats["skipped_non_wiley"] += 1
            continue
        if src.extra.get("tdm_fulltext"):
            stats["skipped_already_tdm"] += 1
            continue

        stats["attempted"] += 1
        tdm_url = f"{base_url.rstrip('/')}/articles/{quote(doi)}"
        try:
            resp = http.get(
                tdm_url,
                headers={
                    "Wiley-TDM-Client-Token": token,
                    "Accept": "application/pdf",
                },
            )
            status = int(getattr(resp, "status_code", 200))
            if status != 200:
                raise RuntimeError(f"Wiley TDM returned status {status}")
            pdf_bytes = resp.content or b""
            if not pdf_bytes:
                raise RuntimeError("Wiley TDM returned empty PDF content.")

            tmp_pdf_path = run_dir / "raw" / f"{src.source_id}_tdm.pdf"
            tmp_pdf_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_pdf_path.write_bytes(pdf_bytes)
            pages = extract_pdf_pages(tmp_pdf_path)
            normalized_text = normalize_pdf_pages(pages)
            with contextlib.suppress(FileNotFoundError):
                tmp_pdf_path.unlink()

            written = write_source_files(
                run_dir=run_dir,
                source_id=src.source_id,
                raw_bytes=pdf_bytes,
                raw_suffix=".pdf",
                normalized_text=normalized_text,
            )

            new_extra = dict(src.extra)
            new_extra.update(
                {
                    "tdm_fulltext": True,
                    "tdm_doi": doi,
                    "tdm_url": tdm_url,
                    "tdm_downloaded_at_utc": _utc_now_iso(),
                    "tdm_original_raw_path": src.raw_path,
                    "tdm_original_normalized_path": src.normalized_path,
                    "tdm_original_raw_sha256": src.raw_sha256,
                    "tdm_original_normalized_sha256": src.normalized_sha256,
                }
            )

            tdm_note = "Wiley TDM full-text accessed under text-and-data mining terms. Do not redistribute full text."
            terms_note = (src.terms_licence_note or "").strip()
            if terms_note:
                terms_note = f"{terms_note} {tdm_note}"
            else:
                terms_note = tdm_note

            extraction_notes = (src.extraction_notes or "").strip()
            if extraction_notes:
                extraction_notes = f"{extraction_notes} | Wiley TDM full-text applied."
            else:
                extraction_notes = "Wiley TDM full-text applied."

            sources[idx] = SourceRecord(
                source_id=src.source_id,
                fetched_at_utc=_utc_now_iso(),
                kind=src.kind,
                title=src.title,
                year=src.year,
                url=src.url,
                doi=doi,
                pmid=src.pmid,
                raw_path=str(written.raw_path),
                normalized_path=str(written.normalized_path),
                raw_sha256=written.raw_sha256,
                normalized_sha256=written.normalized_sha256,
                extraction_notes=extraction_notes,
                terms_licence_note=terms_note,
                extra=new_extra,
            )
            stats["downloaded"] += 1
            seen_dois.add(doi)
        except Exception as e:
            stats["failed"] += 1
            if strict_mode:
                raise EvidencePolicyError(f"Wiley TDM download failed for DOI {doi}: {e}") from e

    return stats


def _apply_wiley_tdm_fulltext_client(
    *,
    sources: list[SourceRecord],
    run_dir: Path,
    token: str,
    max_downloads: int,
    allow_non_wiley_doi: bool,
    strict_mode: bool,
) -> dict[str, int]:
    """Download full-text PDFs via the Wiley TDM client when available."""
    stats = {
        "attempted": 0,
        "downloaded": 0,
        "skipped_no_doi": 0,
        "skipped_non_wiley": 0,
        "skipped_already_tdm": 0,
        "failed": 0,
        "truncated": 0,
    }
    try:
        from wiley_tdm import DownloadStatus, TDMClient
    except Exception as e:  # noqa: BLE001
        if strict_mode:
            raise EvidencePolicyError("wiley-tdm client not available.") from e
        return stats

    download_dir = run_dir / "tdm_downloads"
    tdm = TDMClient(api_token=token, download_dir=download_dir)
    seen_dois: set[str] = set()

    for idx, src in enumerate(sources):
        if stats["downloaded"] >= max_downloads:
            stats["truncated"] += 1
            continue

        doi = (src.doi or _extract_doi_from_url(src.url) or "").strip()
        if not doi:
            stats["skipped_no_doi"] += 1
            continue
        if doi in seen_dois:
            continue
        if not allow_non_wiley_doi and not _looks_like_wiley_source(src.url, doi):
            stats["skipped_non_wiley"] += 1
            continue
        if src.extra.get("tdm_fulltext"):
            stats["skipped_already_tdm"] += 1
            continue

        stats["attempted"] += 1
        result = tdm.download_pdf(doi)
        status = getattr(result, "status", None)
        pdf_path = getattr(result, "path", None)

        if status in {DownloadStatus.SUCCESS, DownloadStatus.EXISTING_FILE} and pdf_path:
            try:
                pdf_bytes = Path(pdf_path).read_bytes()
            except Exception as e:  # noqa: BLE001
                stats["failed"] += 1
                if strict_mode:
                    raise EvidencePolicyError(
                        f"Wiley TDM client failed to read PDF for DOI {doi}: {e}"
                    ) from e
                continue

            pages = extract_pdf_pages(Path(pdf_path))
            normalized_text = normalize_pdf_pages(pages)

            written = write_source_files(
                run_dir=run_dir,
                source_id=src.source_id,
                raw_bytes=pdf_bytes,
                raw_suffix=".pdf",
                normalized_text=normalized_text,
            )

            new_extra = dict(src.extra)
            new_extra.update(
                {
                    "tdm_fulltext": True,
                    "tdm_doi": doi,
                    "tdm_url": str(pdf_path),
                    "tdm_downloaded_at_utc": _utc_now_iso(),
                    "tdm_original_raw_path": src.raw_path,
                    "tdm_original_normalized_path": src.normalized_path,
                    "tdm_original_raw_sha256": src.raw_sha256,
                    "tdm_original_normalized_sha256": src.normalized_sha256,
                }
            )

            tdm_note = (
                "Wiley TDM full-text accessed under text-and-data mining terms. "
                "Do not redistribute full text."
            )
            terms_note = (src.terms_licence_note or "").strip()
            if terms_note:
                terms_note = f"{terms_note} {tdm_note}"
            else:
                terms_note = tdm_note

            extraction_notes = (src.extraction_notes or "").strip()
            if extraction_notes:
                extraction_notes = f"{extraction_notes} | Wiley TDM full-text applied."
            else:
                extraction_notes = "Wiley TDM full-text applied."

            sources[idx] = SourceRecord(
                source_id=src.source_id,
                fetched_at_utc=_utc_now_iso(),
                kind=src.kind,
                title=src.title,
                year=src.year,
                url=src.url,
                doi=doi,
                pmid=src.pmid,
                raw_path=str(written.raw_path),
                normalized_path=str(written.normalized_path),
                raw_sha256=written.raw_sha256,
                normalized_sha256=written.normalized_sha256,
                extraction_notes=extraction_notes,
                terms_licence_note=terms_note,
                extra=new_extra,
            )
            stats["downloaded"] += 1
            seen_dois.add(doi)
        else:
            stats["failed"] += 1
            if strict_mode:
                detail = getattr(result, "comment", None)
                raise EvidencePolicyError(
                    f"Wiley TDM client failed for DOI {doi}: {status} {detail or ''}".strip()
                )

    return stats


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

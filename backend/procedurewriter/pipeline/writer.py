from __future__ import annotations

import re
from typing import Any

from procedurewriter.pipeline.text_units import split_sentences
from procedurewriter.pipeline.types import Snippet, SourceRecord

_citation_id_re = re.compile(r"\[S:([^\]]+)\]")
_citation_tag_re = re.compile(r"\[S:[^\]]+\]")


def _parse_sections(author_guide: dict[str, Any]) -> list[dict[str, str]]:
    sections = ((author_guide.get("structure") or {}).get("sections")) if isinstance(author_guide, dict) else None
    parsed: list[dict[str, str]] = []
    for item in sections or []:
        if not isinstance(item, dict):
            continue
        heading = item.get("heading")
        if not isinstance(heading, str) or not heading.strip():
            continue
        fmt = item.get("format")
        bundle = item.get("bundle")
        parsed.append(
            {
                "heading": heading.strip(),
                "format": (fmt.strip().lower() if isinstance(fmt, str) and fmt.strip() else "paragraphs"),
                "bundle": (bundle.strip().lower() if isinstance(bundle, str) and bundle.strip() else ""),
            }
        )

    if parsed:
        return parsed

    return [
        {"heading": "Indikationer", "format": "bullets", "bundle": "action"},
        {"heading": "Kontraindikationer", "format": "bullets", "bundle": "action"},
        {"heading": "Forberedelse", "format": "bullets", "bundle": "action"},
        {"heading": "Udstyr", "format": "bullets", "bundle": "action"},
        {"heading": "Fremgangsmåde (trin-for-trin)", "format": "numbered", "bundle": "action"},
        {"heading": "Forklaringslag (baggrund og rationale)", "format": "paragraphs", "bundle": "explanation"},
        {"heading": "Sikkerhedsboks", "format": "bullets", "bundle": "safety"},
        {"heading": "Komplikationer og fejlfinding", "format": "bullets", "bundle": "action"},
        {"heading": "Disposition og opfølgning", "format": "bullets", "bundle": "action"},
        {"heading": "Evidens og begrænsninger", "format": "bullets", "bundle": "explanation"},
    ]


def write_procedure_markdown(
    *,
    procedure: str,
    context: str | None,
    author_guide: dict[str, Any],
    snippets: list[Snippet],
    sources: list[SourceRecord],
    dummy_mode: bool,
    use_llm: bool,
    llm_model: str,
    openai_api_key: str | None = None,
) -> str:
    citation_pool = _citation_pool(snippets, sources)
    if dummy_mode or not use_llm or not openai_api_key:
        return _write_template(procedure=procedure, context=context, author_guide=author_guide, citations=citation_pool)

    try:
        return _write_llm_sectioned(
            procedure=procedure,
            context=context,
            author_guide=author_guide,
            snippets=snippets,
            sources=sources,
            citations=citation_pool,
            llm_model=llm_model,
            openai_api_key=openai_api_key,
        )
    except Exception:
        try:
            return _write_llm(
                procedure=procedure,
                context=context,
                author_guide=author_guide,
                snippets=snippets,
                sources=sources,
                citations=citation_pool,
                llm_model=llm_model,
                openai_api_key=openai_api_key,
            )
        except Exception:
            return _write_template(procedure=procedure, context=context, author_guide=author_guide, citations=citation_pool)


def _citation_pool(snippets: list[Snippet], sources: list[SourceRecord]) -> list[str]:
    ids: list[str] = []
    for s in snippets:
        if s.source_id not in ids:
            ids.append(s.source_id)
    if ids:
        return ids[:12]
    if sources:
        return [sources[0].source_id]
    return ["SRC0000"]


def _write_template(*, procedure: str, context: str | None, author_guide: dict[str, Any], citations: list[str]) -> str:
    title_prefix = (
        ((author_guide.get("structure") or {}).get("title_prefix")) if isinstance(author_guide, dict) else None
    )
    title = f"{title_prefix or 'Procedure'}: {procedure}".strip()
    sections = _parse_sections(author_guide)

    cite = " ".join(f"[S:{cid}]" for cid in citations[:2])
    lines: list[str] = [f"# {title}", ""]

    if context:
        lines.append(f"**Kontekst (input):** {context.strip()} {cite}")
        lines.append("")

    for sec in sections:
        heading = sec["heading"]
        fmt = sec["format"]
        bundle = sec.get("bundle") or ""
        lines.append(f"## {heading}")
        if fmt == "numbered":
            lines.append(f"1. Udfyld trin-for-trin fremgangsmåde baseret på de indsamlede kilder. {cite}")
            lines.append(f"2. Angiv konkrete handlinger (imperativt) og relevante doser/tærskler hvis de fremgår af kilderne. {cite}")
            lines.append(f"3. Indsæt tydelige stop-kriterier/eskalation hvis det fremgår af kilderne. {cite}")
        elif fmt == "bullets":
            prefix = "OBS:" if bundle == "safety" else ""
            lines.append(f"- {prefix} Udfyld med konkrete, handlingsorienterede punkter fra kilderne. {cite}".strip())
            lines.append(f"- Markér tydeligt usikkerhed/variation hvis kilderne er svage eller uenige. {cite}")
            lines.append(f"- Henvis til lokale retningslinjer hvor kilderne ikke dækker. {cite}")
        else:
            lines.append(f"Dette afsnit beskriver kort rationale og vigtige valg som fremgår af kilderne. {cite}")
            lines.append("")
            lines.append(f"Hvis de indsamlede kilder ikke dækker centrale spørgsmål, skal det stå eksplicit her. {cite}")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def _write_llm_sectioned(
    *,
    procedure: str,
    context: str | None,
    author_guide: dict[str, Any],
    snippets: list[Snippet],
    sources: list[SourceRecord],
    citations: list[str],
    llm_model: str,
    openai_api_key: str,
) -> str:
    from openai import OpenAI

    from procedurewriter.pipeline.retrieve import retrieve

    client = OpenAI(api_key=openai_api_key, timeout=20.0, max_retries=0)

    title_prefix = (
        ((author_guide.get("structure") or {}).get("title_prefix")) if isinstance(author_guide, dict) else None
    )
    title = f"{title_prefix or 'Procedure'}: {procedure}".strip()

    sections = _parse_sections(author_guide)
    source_by_id = {s.source_id: s for s in sources}

    lines: list[str] = [f"# {title}", ""]
    if context:
        cid = citations[0] if citations else (sources[0].source_id if sources else "SRC0000")
        lines.append(f"**Kontekst (input):** {context.strip()} [S:{cid}]")
        lines.append("")

    for sec in sections:
        heading = sec["heading"]
        fmt = sec["format"]
        bundle = sec.get("bundle") or ""

        query = " ".join(x for x in [procedure, heading, context or ""] if x).strip()
        sec_snips = retrieve(query, snippets, top_k=10, prefer_embeddings=False)
        allowed_ids: list[str] = []
        for sn in sec_snips:
            if sn.source_id not in allowed_ids:
                allowed_ids.append(sn.source_id)
        if not allowed_ids:
            allowed_ids = citations[:1] or ([sources[0].source_id] if sources else ["SRC0000"])

        body = _write_llm_section_body(
            client=client,
            llm_model=llm_model,
            procedure=procedure,
            context=context,
            heading=heading,
            fmt=fmt,
            bundle=bundle,
            section_snippets=sec_snips[:8],
            allowed_source_ids=allowed_ids,
            source_by_id=source_by_id,
        )

        lines.append(f"## {heading}")
        lines.extend(body)
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def _write_llm_section_body(
    *,
    client: Any,
    llm_model: str,
    procedure: str,
    context: str | None,
    heading: str,
    fmt: str,
    bundle: str,
    section_snippets: list[Snippet],
    allowed_source_ids: list[str],
    source_by_id: dict[str, SourceRecord],
) -> list[str]:
    snippet_lines: list[str] = []
    for s in section_snippets:
        snippet_body = s.text.replace("\n", " ").strip()
        loc = ", ".join(f"{k}={v}" for k, v in (s.location or {}).items())
        snippet_lines.append(f"- [S:{s.source_id}] ({loc}) {snippet_body[:900]}")
    snippets_text = "\n".join(snippet_lines) if snippet_lines else "(ingen)"
    allowed = ", ".join(allowed_source_ids)

    source_lines: list[str] = []
    for sid in allowed_source_ids:
        src = source_by_id.get(sid)
        if not src:
            continue
        pub_types = (src.extra or {}).get("publication_types") if isinstance(src.extra, dict) else None
        pub_types_text = ""
        if isinstance(pub_types, list) and pub_types:
            pub_types_text = f" | PT: {', '.join(str(x) for x in pub_types if x)}"
        title = (src.title or "").strip()
        year = f"{src.year}" if src.year else ""
        url = (src.url or "").strip()
        doi = f"DOI: {src.doi}" if src.doi else ""
        pmid = f"PMID: {src.pmid}" if src.pmid else ""
        meta = " — ".join(p for p in [title, year, url, doi, pmid] if p)
        source_lines.append(f"- [S:{sid}] {meta}{pub_types_text}".strip())
    sources_text = "\n".join(source_lines) if source_lines else "(ingen)"

    fmt_hint = {
        "bullets": "Markdown bullets: hver linje starter med '- '",
        "numbered": "Markdown nummereret liste: hver linje starter med '1. ', '2. ' osv.",
        "paragraphs": "Korte afsnit. Skriv én sætning per linje (ingen bullets/nummerering).",
    }.get(fmt, "Markdown")
    bundle_hint = {
        "action": "Action-bundle: korte, imperative instruktioner (bedside).",
        "explanation": "Forklaringslag: kun nødvendig baggrund og rationale.",
        "safety": "Sikkerhedsboks: OBS/stop-kriterier/eskalation.",
    }.get(bundle, "")

    system = (
        "Du er en akutmedicinsk procedureforfatter (DK). Du skriver kun INDHOLD til én sektion ad gangen.\n\n"
        "KRAV (ikke til forhandling):\n"
        f"- Format: {fmt_hint}\n"
        f"- Stil: {bundle_hint}\n"
        "- Du må kun citere kilder ved at bruge tags præcis i formatet [S:<source_id>] hvor <source_id> er et af de "
        "tilladte ids.\n"
        "- Hver linje skal være én kort sætning og indeholde mindst én citations-tag.\n"
        "- Du må kun bruge information, der er understøttet af de vedlagte SNIPPETS. Brug ikke generel viden.\n"
        "- Hvis SNIPPETS ikke dækker noget centralt for sektionen, skal du skrive det eksplicit (fx 'Ikke dækket i de "
        "indsamlede kilder; følg lokal retningslinje.') og stadig citere med et tilladt source_id.\n"
        "- Ingen overskrifter, ingen preface, ingen kilde-URLs i brødteksten.\n"
    )
    user = (
        f"PROCEDURE: {procedure}\n"
        f"KONTEKST: {context or ''}\n"
        f"SEKTION: {heading}\n"
        f"TILLADTE source_id: {allowed}\n\n"
        f"SOURCES:\n{sources_text}\n\n"
        f"SNIPPETS:\n{snippets_text}\n"
    )

    resp = client.chat.completions.create(
        model=llm_model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.15,
    )
    raw = (resp.choices[0].message.content or "").strip()
    return _normalize_section_lines(raw, fmt=fmt, fallback_citation=allowed_source_ids[0])


def _normalize_section_lines(text: str, *, fmt: str, fallback_citation: str) -> list[str]:
    cleaned: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("```"):
            continue
        if line.startswith("#"):
            continue
        cleaned.append(line)

    if not cleaned:
        cleaned = ["Ikke dækket i de indsamlede kilder; følg lokal retningslinje."]

    atomic: list[str] = []

    for line in cleaned:
        s = line.strip()
        if s.startswith(("-", "*")) and len(s) > 1 and s[1].isspace():
            s = s[2:].strip()
        s = re.sub(r"^\d+[.)]\s+", "", s).strip()
        if not s:
            continue

        citation_ids = _citation_id_re.findall(s)
        if not citation_ids:
            citation_ids = [fallback_citation]
        citation_ids = _dedupe_preserve(citation_ids)

        content = _citation_tag_re.sub("", s).strip()
        if not content:
            content = "Ikke dækket i de indsamlede kilder; følg lokal retningslinje."

        for sent in split_sentences(content) or [content]:
            sent = sent.strip()
            if not sent:
                continue
            tags = " ".join(f"[S:{cid}]" for cid in citation_ids)
            atomic.append(f"{sent} {tags}".strip())

    if not atomic:
        atomic = [f"Ikke dækket i de indsamlede kilder; følg lokal retningslinje. [S:{fallback_citation}]"]

    if fmt == "bullets":
        return [f"- {s}".strip() for s in atomic]
    if fmt == "numbered":
        return [f"{i}. {s}".strip() for i, s in enumerate(atomic, start=1)]
    return atomic


def _dedupe_preserve(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for x in items:
        x = x.strip()
        if not x:
            continue
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


def _write_llm(
    *,
    procedure: str,
    context: str | None,
    author_guide: dict[str, Any],
    snippets: list[Snippet],
    sources: list[SourceRecord],
    citations: list[str],
    llm_model: str,
    openai_api_key: str,
) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=openai_api_key, timeout=20.0, max_retries=0)

    guide_text = _yaml_like_compact(author_guide)
    snippet_lines: list[str] = []
    for s in snippets[:18]:
        snippet_body = s.text.replace("\n", " ").strip()
        loc = ", ".join(f"{k}={v}" for k, v in (s.location or {}).items())
        snippet_lines.append(f"- [S:{s.source_id}] ({loc}) {snippet_body[:900]}")
    snippets_text = "\n".join(snippet_lines)
    allowed = ", ".join(citations)

    allowed_set = set(citations)
    source_lines: list[str] = []
    for src in sources:
        if src.source_id not in allowed_set:
            continue
        pub_types = (src.extra or {}).get("publication_types") if isinstance(src.extra, dict) else None
        pub_types_text = ""
        if isinstance(pub_types, list) and pub_types:
            pub_types_text = f" | PT: {', '.join(str(x) for x in pub_types if x)}"
        title = (src.title or "").strip()
        year = f"{src.year}" if src.year else ""
        url = (src.url or "").strip()
        doi = f"DOI: {src.doi}" if src.doi else ""
        pmid = f"PMID: {src.pmid}" if src.pmid else ""
        meta = " — ".join(p for p in [title, year, url, doi, pmid] if p)
        source_lines.append(f"- [S:{src.source_id}] {meta}{pub_types_text}".strip())
    sources_text = "\n".join(source_lines) if source_lines else "(ingen)"

    system = (
        "Du er en akutmedicinsk procedureforfatter (DK). Du skal skrive en bedside-brugbar procedure i et fast, "
        "lagdelt format.\n\n"
        "KRAV (ikke til forhandling):\n"
        "- Du må kun citere kilder ved at bruge tags præcis i formatet [S:<source_id>] hvor <source_id> er et af de "
        "tilladte ids.\n"
        "- Hver sætning skal have mindst én citations-tag.\n"
        "- Du må kun bruge information, der er understøttet af de vedlagte SNIPPETS. Brug ikke generel viden. Hvis "
        "noget ikke er dækket af SNIPPETS, skal du skrive det eksplicit (fx 'Ikke dækket i de indsamlede kilder; følg "
        "lokal retningslinje.').\n"
        "- Følg strukturen og formateringen i AUTHOR_GUIDE: 'bullets' -> Markdown '- ' linjer, 'numbered' -> '1. ' "
        "linjer, 'paragraphs' -> korte afsnit.\n"
        "- Action-bundle: korte, imperative instruktioner. Forklaringslag: kort rationale. Sikkerhedsboks: altid "
        "med.\n"
    )
    user = (
        f"PROCEDURE: {procedure}\n\n"
        f"KONTEKST: {context or ''}\n\n"
        f"AUTHOR_GUIDE (YAML):\n{guide_text}\n\n"
        f"TILLADTE source_id: {allowed}\n\n"
        f"SOURCES:\n{sources_text}\n\n"
        "SNIPPETS:\n"
        f"{snippets_text}\n\n"
        "OUTPUT:\n"
        "- Skriv en dansk procedure i Markdown.\n"
        "- Brug præcis overskrifterne fra AUTHOR_GUIDE.\n"
        "- Hold hvert bullet/nummereret trin til én kort sætning.\n"
        "- Ingen forord, ingen forklaring af regler, ingen kilde-URLs i brødteksten (kun i referencer senere).\n"
    )

    resp = client.chat.completions.create(
        model=llm_model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.2,
    )
    text = resp.choices[0].message.content or ""
    return text.strip() + "\n"


def _yaml_like_compact(obj: Any) -> str:
    import json

    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True)

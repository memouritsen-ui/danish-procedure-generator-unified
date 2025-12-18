from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from xml.etree import ElementTree as ET

from procedurewriter.pipeline.fetcher import CachedHttpClient, CachedResponse

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


@dataclass(frozen=True)
class PubMedArticle:
    pmid: str
    title: str | None
    abstract: str | None
    journal: str | None
    year: int | None
    doi: str | None
    publication_types: list[str]


@dataclass(frozen=True)
class PubMedFetchedArticle:
    article: PubMedArticle
    raw_xml: bytes


class PubMedClient:
    def __init__(self, http: CachedHttpClient, *, tool: str, email: str | None, api_key: str | None = None) -> None:
        self._http = http
        self._tool = tool
        self._email = email
        self._api_key = api_key

    def _common_params(self) -> dict[str, Any]:
        params: dict[str, Any] = {"tool": self._tool}
        if self._email:
            params["email"] = self._email
        if self._api_key:
            params["api_key"] = self._api_key
        return params

    def search(self, query: str, *, retmax: int = 8) -> tuple[list[str], CachedResponse]:
        url = f"{EUTILS_BASE}/esearch.fcgi"
        params = {
            **self._common_params(),
            "db": "pubmed",
            "term": query,
            "retmode": "xml",
            "retmax": str(retmax),
        }
        resp = self._http.get(url, params=params)
        root = ET.fromstring(resp.content)
        ids = [e.text.strip() for e in root.findall(".//IdList/Id") if e.text and e.text.strip()]
        return ids, resp

    def fetch(self, pmids: list[str]) -> tuple[list[PubMedFetchedArticle], CachedResponse]:
        url = f"{EUTILS_BASE}/efetch.fcgi"
        params = {
            **self._common_params(),
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml",
        }
        resp = self._http.get(url, params=params)
        root = ET.fromstring(resp.content)
        articles: list[PubMedFetchedArticle] = []
        for article in root.findall(".//PubmedArticle"):
            pmid = _findtext(article, ".//MedlineCitation/PMID")
            if not pmid:
                continue
            title = _findtext(article, ".//Article/ArticleTitle")
            abstract = _findalltext(article, ".//Article/Abstract/AbstractText")
            journal = _findtext(article, ".//Article/Journal/Title")
            year_text = _findtext(article, ".//Article/Journal/JournalIssue/PubDate/Year")
            year = int(year_text) if year_text and year_text.isdigit() else None
            doi = _findtext(article, ".//ArticleIdList/ArticleId[@IdType='doi']")
            publication_types = _findall_texts(article, ".//Article/PublicationTypeList/PublicationType")
            raw_xml = ET.tostring(article, encoding="utf-8")
            articles.append(
                PubMedFetchedArticle(
                    article=PubMedArticle(
                        pmid=pmid,
                        title=title,
                        abstract=abstract,
                        journal=journal,
                        year=year,
                        doi=doi,
                        publication_types=publication_types,
                    ),
                    raw_xml=raw_xml,
                )
            )
        return articles, resp


def _findtext(elem: ET.Element, path: str) -> str | None:
    node = elem.find(path)
    if node is None or node.text is None:
        return None
    text = node.text.strip()
    return text or None


def _findalltext(elem: ET.Element, path: str) -> str | None:
    nodes = elem.findall(path)
    parts: list[str] = []
    for n in nodes:
        if n.text and n.text.strip():
            parts.append(n.text.strip())
    if not parts:
        return None
    return " ".join(parts)


def _findall_texts(elem: ET.Element, path: str) -> list[str]:
    nodes = elem.findall(path)
    parts: list[str] = []
    for n in nodes:
        if n.text and n.text.strip():
            parts.append(n.text.strip())
    return parts

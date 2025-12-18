import httpx
import respx

from procedurewriter.pipeline.fetcher import CachedHttpClient
from procedurewriter.pipeline.pubmed import PubMedClient


@respx.mock
def test_pubmed_client_search_and_fetch(tmp_path):
    search_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<eSearchResult>
  <IdList>
    <Id>12345678</Id>
  </IdList>
</eSearchResult>
"""
    fetch_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>12345678</PMID>
      <Article>
        <ArticleTitle>Test Title</ArticleTitle>
        <Abstract>
          <AbstractText>Test abstract.</AbstractText>
        </Abstract>
        <Journal>
          <Title>Test Journal</Title>
          <JournalIssue>
            <PubDate><Year>2020</Year></PubDate>
          </JournalIssue>
        </Journal>
      </Article>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>
"""

    respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi").mock(
        return_value=httpx.Response(200, content=search_xml)
    )
    respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi").mock(
        return_value=httpx.Response(200, content=fetch_xml)
    )

    http = CachedHttpClient(cache_dir=tmp_path, per_host_min_interval_s={})
    try:
        client = PubMedClient(http, tool="test", email="test@example.com", api_key=None)
        pmids, _search_resp = client.search("asthma", retmax=1)
        assert pmids == ["12345678"]

        fetched, _fetch_resp = client.fetch(pmids)
        assert len(fetched) == 1
        article = fetched[0].article
        assert article.pmid == "12345678"
        assert article.title == "Test Title"
        assert article.abstract == "Test abstract."
        assert article.journal == "Test Journal"
        assert article.year == 2020
        assert article.doi is None
        assert article.publication_types == []
        assert b"<PMID>12345678</PMID>" in fetched[0].raw_xml

        cached_files = list((tmp_path / "http").glob("*"))
        assert cached_files
    finally:
        http.close()


@respx.mock
def test_pubmed_fetch_parses_doi_and_publication_types(tmp_path):
    fetch_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>999</PMID>
      <Article>
        <ArticleTitle>Guideline Title</ArticleTitle>
        <Abstract>
          <AbstractText>Guideline abstract.</AbstractText>
        </Abstract>
        <PublicationTypeList>
          <PublicationType>Practice Guideline</PublicationType>
          <PublicationType>Review</PublicationType>
        </PublicationTypeList>
      </Article>
    </MedlineCitation>
    <PubmedData>
      <ArticleIdList>
        <ArticleId IdType="doi">10.1234/example.doi</ArticleId>
      </ArticleIdList>
    </PubmedData>
  </PubmedArticle>
</PubmedArticleSet>
"""
    respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi").mock(
        return_value=httpx.Response(200, content=fetch_xml)
    )

    http = CachedHttpClient(cache_dir=tmp_path, per_host_min_interval_s={})
    try:
        client = PubMedClient(http, tool="test", email="test@example.com", api_key=None)
        fetched, _fetch_resp = client.fetch(["999"])
        assert len(fetched) == 1
        article = fetched[0].article
        assert article.pmid == "999"
        assert article.doi == "10.1234/example.doi"
        assert article.publication_types == ["Practice Guideline", "Review"]
    finally:
        http.close()


@respx.mock
def test_pubmed_client_includes_ncbi_api_key_in_requests(tmp_path):
    search_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<eSearchResult>
  <IdList>
    <Id>123</Id>
  </IdList>
</eSearchResult>
"""
    route = respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi").mock(
        return_value=httpx.Response(200, content=search_xml)
    )

    http = CachedHttpClient(cache_dir=tmp_path, per_host_min_interval_s={}, backoff_s=0.0, sleep_fn=lambda _s: None)
    try:
        client = PubMedClient(http, tool="test", email=None, api_key="NCBIKEY123")
        pmids, _search_resp = client.search("asthma", retmax=1)
        assert pmids == ["123"]
        assert route.calls
        url = str(route.calls[0].request.url)
        assert "api_key=NCBIKEY123" in url
    finally:
        http.close()

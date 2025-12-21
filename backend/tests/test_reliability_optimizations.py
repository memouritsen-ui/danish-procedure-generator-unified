"""Tests for reliability optimizations (neurotiske forbedringer).

Tests for:
1. FTS5 phrase-based search with weighted BM25 ranking
2. QualityParsingError exception and retry logic
3. Dynamic claim chunking (no arbitrary limit)
4. LLM-based term expansion
5. RFC 5987 filename encoding
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest


class TestFTS5PhraseSearch:
    """Tests for FTS5 phrase-based search logic."""

    def test_prepare_fts_query_single_word(self) -> None:
        """Single word should not be phrase-wrapped."""
        from procedurewriter.pipeline.library_search import LibrarySearchProvider

        provider = LibrarySearchProvider()
        result = provider._prepare_fts_query("hypoglykæmi")

        # Single word, no phrase wrapping
        assert result == "hypoglykæmi"

    def test_prepare_fts_query_multi_word_phrase_boost(self) -> None:
        """Multi-word queries should include phrase for boosting."""
        from procedurewriter.pipeline.library_search import LibrarySearchProvider

        provider = LibrarySearchProvider()
        result = provider._prepare_fts_query("akut hypoglykæmi")

        # Should include exact phrase AND individual terms
        assert '"akut hypoglykæmi"' in result
        assert " OR " in result
        assert "akut" in result
        assert "hypoglykæmi" in result

    def test_prepare_fts_query_preserves_quoted_phrases(self) -> None:
        """Explicitly quoted phrases should be preserved."""
        from procedurewriter.pipeline.library_search import LibrarySearchProvider

        provider = LibrarySearchProvider()
        result = provider._prepare_fts_query('"akut behandling" diabetes')

        assert '"akut behandling"' in result
        assert "diabetes" in result

    def test_prepare_fts_query_escapes_special_chars(self) -> None:
        """FTS5 special characters should be escaped/removed."""
        from procedurewriter.pipeline.library_search import LibrarySearchProvider

        provider = LibrarySearchProvider()
        # These chars could break FTS5 syntax
        result = provider._prepare_fts_query("akut (behandling) [test]")

        # Should not contain unescaped special chars
        assert "(" not in result
        assert ")" not in result
        assert "[" not in result
        assert "]" not in result

    def test_prepare_fts_query_escapes_slashes(self) -> None:
        """Forward/back slashes should be escaped/removed."""
        from procedurewriter.pipeline.library_search import LibrarySearchProvider

        provider = LibrarySearchProvider()
        # Slashes can break FTS5 - e.g., "defibrillering/kardiovertering"
        result = provider._prepare_fts_query("Manuel defibrillering/kardiovertering")

        # Should not contain slashes
        assert "/" not in result
        assert "\\" not in result
        # Should have individual terms
        assert "Manuel" in result
        assert "defibrillering" in result
        assert "kardiovertering" in result

    def test_prepare_fts_query_phrase_boost_disabled(self) -> None:
        """With phrase_boost=False, no automatic phrase wrapping."""
        from procedurewriter.pipeline.library_search import LibrarySearchProvider

        provider = LibrarySearchProvider()
        result = provider._prepare_fts_query(
            "akut hypoglykæmi", phrase_boost=False
        )

        # Should have individual terms but NOT the full phrase
        assert "akut" in result
        assert "hypoglykæmi" in result
        # The full phrase should NOT be there
        assert result.count('"akut hypoglykæmi"') == 0


class TestQualityParsingError:
    """Tests for QualityParsingError and retry logic."""

    def test_quality_parsing_error_attributes(self) -> None:
        """QualityParsingError should have expected attributes."""
        from procedurewriter.agents.quality import QualityParsingError

        raw = '{"invalid json'
        err = QualityParsingError(
            message="Parse failed",
            raw_response=raw,
            parse_error=ValueError("test"),
        )

        assert err.raw_response == raw
        assert err.is_retryable is True
        assert isinstance(err.parse_error, ValueError)

    def test_quality_parse_response_raises_on_no_json(self) -> None:
        """Missing JSON should raise QualityParsingError."""
        from procedurewriter.agents.quality import QualityAgent, QualityParsingError

        agent = QualityAgent(llm=MagicMock(), model="test")

        with pytest.raises(QualityParsingError) as exc_info:
            agent._parse_response("Just some text without any JSON")

        assert "did not contain valid JSON" in str(exc_info.value)
        assert exc_info.value.is_retryable is True

    def test_quality_parse_response_raises_on_missing_field(self) -> None:
        """JSON missing required fields should raise QualityParsingError."""
        from procedurewriter.agents.quality import QualityAgent, QualityParsingError

        agent = QualityAgent(llm=MagicMock(), model="test")

        # Missing overall_score field
        invalid_json = '```json\n{"criteria": []}\n```'

        with pytest.raises(QualityParsingError) as exc_info:
            agent._parse_response(invalid_json)

        assert "overall_score" in str(exc_info.value)

    def test_quality_parse_response_valid_json(self) -> None:
        """Valid JSON should parse successfully."""
        from procedurewriter.agents.quality import QualityAgent

        agent = QualityAgent(llm=MagicMock(), model="test")

        valid_json = """```json
{
  "criteria": [{"name": "Test", "score": 8, "notes": "Good"}],
  "overall_score": 8,
  "passes_threshold": true,
  "revision_suggestions": []
}
```"""

        result = agent._parse_response(valid_json)

        assert result.success is True
        assert result.overall_score == 8
        assert result.passes_threshold is True

    def test_quality_retries_on_parse_failure(self) -> None:
        """Quality agent should retry on JSON parse failures."""
        from procedurewriter.agents.models import QualityInput, SourceReference
        from procedurewriter.agents.quality import QualityAgent
        from procedurewriter.llm.providers import LLMResponse

        mock_llm = MagicMock()
        agent = QualityAgent(llm=mock_llm, model="test")

        # Patch llm_call to return different responses
        call_count = 0
        def mock_llm_call(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return LLMResponse(content="Not valid JSON at all", input_tokens=10, output_tokens=10, total_tokens=20, model="test")
            return LLMResponse(
                content="""```json
{
  "criteria": [],
  "overall_score": 7,
  "passes_threshold": false,
  "revision_suggestions": ["Improve"]
}
```""",
                input_tokens=10,
                output_tokens=50,
                total_tokens=60,
                model="test",
            )

        agent.llm_call = mock_llm_call
        agent.reset_stats = MagicMock()
        agent.get_stats = MagicMock(return_value=MagicMock())

        input_data = QualityInput(
            procedure_title="Test",
            content_markdown="# Test\n\nSome content.",
            sources=[SourceReference(source_id="s1", title="Test Source", relevance_score=0.9)],
            citations_used=["s1"],
        )

        result = agent.execute(input_data, max_parse_retries=2)

        # Should have called LLM twice (initial + 1 retry)
        assert call_count == 2
        assert result.output.overall_score == 7


class TestDynamicClaimChunking:
    """Tests for dynamic claim chunking without arbitrary limits."""

    def test_extract_claims_returns_chunked_lists(self) -> None:
        """Claims should be returned as list of chunks."""
        from procedurewriter.agents.orchestrator import AgentOrchestrator

        mock_llm = MagicMock()
        orchestrator = AgentOrchestrator(llm=mock_llm, model="test")

        # Content with citations
        content = """
        Første påstand her [ref1]. Dette er også en påstand [ref2].
        Endnu en påstand med citation [ref3].
        """

        result = orchestrator._extract_claims(content, max_claims_per_chunk=2)

        # Should be list of lists
        assert isinstance(result, list)
        assert all(isinstance(chunk, list) for chunk in result)
        # With 3 claims and max 2 per chunk, should have 2 chunks
        total_claims = sum(len(chunk) for chunk in result)
        assert total_claims == 3

    def test_extract_claims_no_limit_on_total(self) -> None:
        """All claims should be extracted regardless of count."""
        from procedurewriter.agents.orchestrator import AgentOrchestrator

        mock_llm = MagicMock()
        orchestrator = AgentOrchestrator(llm=mock_llm, model="test")

        # Generate 50 claims (more than old 20 limit)
        claims = " ".join(f"Påstand nummer {i} med citation [ref{i}]." for i in range(50))
        content = f"# Procedure\n\n{claims}"

        result = orchestrator._extract_claims(content, max_claims_per_chunk=10)

        total = sum(len(chunk) for chunk in result)
        assert total == 50, f"Expected 50 claims, got {total}"
        assert len(result) == 5, f"Expected 5 chunks of 10, got {len(result)}"

    def test_extract_claims_empty_content(self) -> None:
        """Content without citations should return empty list."""
        from procedurewriter.agents.orchestrator import AgentOrchestrator

        mock_llm = MagicMock()
        orchestrator = AgentOrchestrator(llm=mock_llm, model="test")

        result = orchestrator._extract_claims("No citations here.")

        assert result == []


class TestLLMTermExpansion:
    """Tests for LLM-based term expansion."""

    def test_get_llm_english_terms_parses_json_array(self) -> None:
        """LLM term expansion should parse JSON array response."""
        from procedurewriter.pipeline.run import _get_llm_english_terms

        mock_llm = MagicMock()
        mock_llm.chat_completion.return_value = MagicMock(
            content='["acute hypoglycemia", "low blood sugar", "diabetes emergency"]'
        )

        result = _get_llm_english_terms("akut hypoglykæmi", None, mock_llm, "test-model")

        assert len(result) == 3
        assert "acute hypoglycemia" in result

    def test_get_llm_english_terms_handles_code_block(self) -> None:
        """LLM term expansion should handle code block wrapped JSON."""
        from procedurewriter.pipeline.run import _get_llm_english_terms

        mock_llm = MagicMock()
        mock_llm.chat_completion.return_value = MagicMock(
            content='```json\n["term1", "term2"]\n```'
        )

        result = _get_llm_english_terms("test", None, mock_llm, "test-model")

        assert len(result) == 2
        assert "term1" in result

    def test_get_llm_english_terms_handles_error(self) -> None:
        """LLM errors should return empty list, not crash."""
        from procedurewriter.pipeline.run import _get_llm_english_terms

        mock_llm = MagicMock()
        mock_llm.chat_completion.side_effect = Exception("API error")

        result = _get_llm_english_terms("test", None, mock_llm, "test-model")

        assert result == []

    def test_expand_procedure_terms_uses_llm_when_provided(self) -> None:
        """Term expansion should use LLM when available."""
        from procedurewriter.pipeline.run import _expand_procedure_terms

        mock_llm = MagicMock()
        mock_llm.chat_completion.return_value = MagicMock(
            content='["llm suggested term"]'
        )

        result = _expand_procedure_terms(
            procedure="akut test",
            context=None,
            llm=mock_llm,
            model="test-model",
        )

        assert "llm suggested term" in result
        mock_llm.chat_completion.assert_called_once()


class TestRFC5987Encoding:
    """Tests for RFC 5987 filename encoding."""

    def test_encode_filename_rfc5987_ascii(self) -> None:
        """ASCII filenames should be encoded correctly."""
        from procedurewriter.routers.runs import _encode_filename_rfc5987

        result = _encode_filename_rfc5987("test.docx")

        assert result == "UTF-8''test.docx"

    def test_encode_filename_rfc5987_danish_chars(self) -> None:
        """Danish characters should be percent-encoded."""
        from procedurewriter.routers.runs import _encode_filename_rfc5987

        result = _encode_filename_rfc5987("Blødning_æøå.docx")

        # Should have UTF-8'' prefix and percent-encoded chars
        assert result.startswith("UTF-8''")
        assert "%C3%B8" in result  # ø
        assert "%C3%A6" in result  # æ
        assert "%C3%A5" in result  # å

    def test_make_content_disposition_dual_format(self) -> None:
        """Content-Disposition should have both ASCII and RFC 5987 formats."""
        from procedurewriter.routers.runs import _make_content_disposition

        result = _make_content_disposition("Blødning.docx")

        # Should have attachment directive
        assert result.startswith("attachment;")
        # Should have ASCII-safe filename with underscores
        assert 'filename="Bl_dning.docx"' in result
        # Should have filename* with RFC 5987 encoding
        assert "filename*=UTF-8''" in result

    def test_make_content_disposition_preserves_extension(self) -> None:
        """File extension should be preserved."""
        from procedurewriter.routers.runs import _make_content_disposition

        result = _make_content_disposition("Procedure_æøå.docx")

        # Extension should still be .docx
        assert ".docx" in result


class TestFalsePositivePrevention:
    """Tests to prevent false positives in validation."""

    def test_quality_score_not_silently_defaulted(self) -> None:
        """Quality score should never silently default to 5 on parse error."""
        from procedurewriter.agents.quality import QualityAgent, QualityParsingError

        agent = QualityAgent(llm=MagicMock(), model="test")

        # This should RAISE, not return score=5
        with pytest.raises(QualityParsingError):
            agent._parse_response("completely invalid")

    def test_claim_validation_processes_all_chunks(self) -> None:
        """Validator should process ALL claim chunks, not just first."""
        from procedurewriter.agents.orchestrator import AgentOrchestrator

        mock_llm = MagicMock()
        orchestrator = AgentOrchestrator(llm=mock_llm, model="test")

        # Generate many claims to force multiple chunks
        claims_text = " ".join(
            f"Claim {i} with citation [ref{i}]." for i in range(30)
        )

        chunks = orchestrator._extract_claims(claims_text, max_claims_per_chunk=10)

        # Should have 3 chunks
        assert len(chunks) == 3
        # All 30 claims should be present
        assert sum(len(c) for c in chunks) == 30

    def test_fts_query_phrase_not_lost_in_parsing(self) -> None:
        """Phrase search should preserve the full phrase."""
        from procedurewriter.pipeline.library_search import LibrarySearchProvider

        provider = LibrarySearchProvider()

        # Critical medical phrase
        query = "akut koronar syndrom"
        result = provider._prepare_fts_query(query)

        # The full phrase MUST be in the query for accurate matching
        assert '"akut koronar syndrom"' in result

    def test_rfc5987_encoding_roundtrips_correctly(self) -> None:
        """RFC 5987 encoded filenames should decode correctly."""
        from urllib.parse import unquote

        from procedurewriter.routers.runs import _encode_filename_rfc5987

        original = "Akut_blødning_procedure_æøå.docx"
        encoded = _encode_filename_rfc5987(original)

        # Remove prefix and decode
        assert encoded.startswith("UTF-8''")
        decoded = unquote(encoded[7:])  # Skip "UTF-8''"

        assert decoded == original

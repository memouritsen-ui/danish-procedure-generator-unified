"""
Tests for the multi-agent system.

Uses mock LLM responses to test agent behavior without API calls.
"""

from __future__ import annotations

from procedurewriter.agents import (
    AgentOrchestrator,
    EditorAgent,
    EditorInput,
    PipelineInput,
    QualityAgent,
    QualityInput,
    ResearcherAgent,
    ResearcherInput,
    SourceReference,
    ValidatorAgent,
    ValidatorInput,
    WriterAgent,
    WriterInput,
)
from procedurewriter.llm.providers import LLMProvider, LLMProviderType, LLMResponse


class MockLLMProvider(LLMProvider):
    """Mock LLM provider for testing."""

    def __init__(self, responses: list[str] | None = None):
        self._responses = responses or []
        self._call_count = 0

    def chat_completion(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        timeout: float = 60.0,
    ) -> LLMResponse:
        response_text = "Mock response"
        if self._call_count < len(self._responses):
            response_text = self._responses[self._call_count]
        self._call_count += 1

        return LLMResponse(
            content=response_text,
            model=model,
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
        )

    def is_available(self) -> bool:
        return True

    @property
    def provider_type(self) -> LLMProviderType:
        return LLMProviderType.OPENAI


class RecordingLLMProvider(LLMProvider):
    """LLM provider that records prompts for inspection."""

    def __init__(self, responses: list[str] | None = None):
        self._responses = responses or []
        self._call_count = 0
        self.calls: list[list[dict[str, str]]] = []

    def chat_completion(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        timeout: float = 60.0,
    ) -> LLMResponse:
        self.calls.append(messages)
        response_text = "Mock response"
        if self._call_count < len(self._responses):
            response_text = self._responses[self._call_count]
        self._call_count += 1

        return LLMResponse(
            content=response_text,
            model=model,
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
        )

    def is_available(self) -> bool:
        return True

    @property
    def provider_type(self) -> LLMProviderType:
        return LLMProviderType.OPENAI

class TestResearcherAgent:
    """Tests for ResearcherAgent."""

    def test_generate_search_terms(self):
        """Test that search terms are generated from procedure title."""
        mock_llm = MockLLMProvider(
            responses=['["anaphylaxis treatment", "epinephrine emergency", "anaphylaxis guidelines"]']
        )
        agent = ResearcherAgent(mock_llm)

        result = agent.execute(
            ResearcherInput(
                procedure_title="Anafylaksi behandling",
                max_sources=5,
            )
        )

        assert result.output.success
        assert len(result.output.search_terms_used) > 0
        assert result.stats.llm_calls >= 1

    def test_with_provided_search_terms(self):
        """Test using provided search terms instead of generating."""
        mock_llm = MockLLMProvider()
        agent = ResearcherAgent(mock_llm)

        result = agent.execute(
            ResearcherInput(
                procedure_title="Test procedure",
                search_terms=["term1", "term2"],
                max_sources=5,
            )
        )

        assert result.output.success
        assert result.output.search_terms_used == ["term1", "term2"]


class TestValidatorAgent:
    """Tests for ValidatorAgent."""

    def test_validate_claims(self):
        """Test claim validation against sources."""
        mock_response = """```json
[
  {
    "claim": "Epinephrine is first-line treatment",
    "is_supported": true,
    "supporting_source_ids": ["src_001"],
    "confidence": 0.95,
    "notes": "Directly stated in guidelines"
  }
]
```"""
        mock_llm = MockLLMProvider(responses=[mock_response])
        agent = ValidatorAgent(mock_llm)

        sources = [
            SourceReference(
                source_id="src_001",
                title="Anaphylaxis Guidelines 2023",
                relevance_score=0.9,
            )
        ]

        result = agent.execute(
            ValidatorInput(
                procedure_title="Test",
                claims=["Epinephrine is first-line treatment"],
                sources=sources,
            )
        )

        assert result.output.success
        assert len(result.output.validations) == 1
        assert result.output.validations[0].is_supported
        assert result.output.supported_count == 1

    def test_empty_claims(self):
        """Test with no claims to validate."""
        mock_llm = MockLLMProvider()
        agent = ValidatorAgent(mock_llm)

        result = agent.execute(
            ValidatorInput(
                procedure_title="Test",
                claims=[],
                sources=[],
            )
        )

        assert result.output.success
        assert result.output.validations == []


class TestWriterAgent:
    """Tests for WriterAgent."""

    def test_generate_content(self):
        """Test content generation with citations."""
        mock_content = """# Anafylaksi

## Indikationer
Alvorlig allergisk reaktion [S:src_001].

## Behandling
Administrer epinephrin 0.5 mg i.m. [S:src_001].
"""
        mock_llm = MockLLMProvider(responses=[mock_content])
        agent = WriterAgent(mock_llm)

        sources = [
            SourceReference(
                source_id="src_001",
                title="Guidelines",
                relevance_score=0.9,
            )
        ]

        result = agent.execute(
            WriterInput(
                procedure_title="Anafylaksi",
                sources=sources,
            )
        )

        assert result.output.success
        assert len(result.output.content_markdown) > 0
        assert "src_001" in result.output.citations_used
        assert result.output.word_count > 0

    def test_extract_sections(self):
        """Test section extraction from markdown."""
        mock_content = """# Main Title

## Section 1
Content

### Subsection
More content

## Section 2
Final content
"""
        mock_llm = MockLLMProvider(responses=[mock_content])
        agent = WriterAgent(mock_llm)

        result = agent.execute(
            WriterInput(
                procedure_title="Test",
                sources=[],
            )
        )

        assert "Main Title" in result.output.sections
        assert "Section 1" in result.output.sections


class TestEditorAgent:
    """Tests for EditorAgent."""

    def test_edit_content(self):
        """Test content editing with suggestions."""
        mock_response = """# Forbedret Indhold

Redigeret tekst her.

```json
{
  "suggestions": [
    {"original": "gammel", "suggested": "ny", "reason": "klarhed", "severity": "minor"}
  ],
  "danish_notes": "God dansk kvalitet"
}
```"""
        mock_llm = MockLLMProvider(responses=[mock_response])
        agent = EditorAgent(mock_llm)

        result = agent.execute(
            EditorInput(
                procedure_title="Test",
                content_markdown="Original content",
                sources=[],
            )
        )

        assert result.output.success
        assert len(result.output.edited_content) > 0
        assert len(result.output.suggestions_applied) > 0


class TestQualityAgent:
    """Tests for QualityAgent."""

    def test_quality_scoring(self):
        """Test quality evaluation with scores."""
        mock_response = """```json
{
  "criteria": [
    {"name": "Faglig korrekthed", "score": 9, "notes": "Good"},
    {"name": "Citationsdækning", "score": 8, "notes": "Adequate"},
    {"name": "Klarhed", "score": 9, "notes": "Clear"},
    {"name": "Fuldstændighed", "score": 8, "notes": "Complete"},
    {"name": "Dansk sprogkvalitet", "score": 9, "notes": "Excellent"},
    {"name": "Praktisk anvendelighed", "score": 8, "notes": "Useful"}
  ],
  "overall_score": 9,
  "passes_threshold": true,
  "ready_for_publication": true,
  "revision_suggestions": []
}
```"""
        mock_llm = MockLLMProvider(responses=[mock_response])
        agent = QualityAgent(mock_llm)

        result = agent.execute(
            QualityInput(
                procedure_title="Test",
                content_markdown="Test content",
                sources=[],
                citations_used=["src_001"],
            )
        )

        assert result.output.success
        assert result.output.overall_score == 9
        assert result.output.passes_threshold
        assert len(result.output.criteria) == 6

    def test_low_quality_score(self):
        """Test quality evaluation with low score."""
        mock_response = """```json
{
  "criteria": [],
  "overall_score": 5,
  "passes_threshold": false,
  "ready_for_publication": false,
  "revision_suggestions": ["Add more citations", "Improve clarity"]
}
```"""
        mock_llm = MockLLMProvider(responses=[mock_response])
        agent = QualityAgent(mock_llm)

        result = agent.execute(
            QualityInput(
                procedure_title="Test",
                content_markdown="Weak content",
                sources=[],
                citations_used=[],
            )
        )

        assert result.output.overall_score == 5
        assert not result.output.passes_threshold
        assert len(result.output.revision_suggestions) > 0


class TestAgentOrchestrator:
    """Tests for AgentOrchestrator."""

    def test_pipeline_with_sources(self):
        """Test full pipeline with pre-fetched sources."""
        # Mock responses for each agent
        responses = [
            # Writer
            "# Procedure\n\nContent with [src_001] citation.",
            # Validator
            '```json\n[{"claim": "test", "is_supported": true, "supporting_source_ids": ["src_001"], "confidence": 0.9}]\n```',
            # Editor
            "# Edited\n\nImproved content.",
            # Quality
            '```json\n{"criteria": [], "overall_score": 9, "passes_threshold": true, "ready_for_publication": true, "revision_suggestions": []}\n```',
        ]

        mock_llm = MockLLMProvider(responses=responses)
        orchestrator = AgentOrchestrator(mock_llm)

        sources = [
            SourceReference(
                source_id="src_001",
                title="Test Source",
                relevance_score=0.9,
            )
        ]

        result = orchestrator.run(
            PipelineInput(
                procedure_title="Test Procedure",
                max_iterations=1,
            ),
            sources=sources,
        )

        assert result.success
        assert result.procedure_markdown is not None
        assert result.quality_score == 9
        assert result.iterations_used == 1
        assert result.total_cost_usd > 0

    def test_pipeline_completes_max_iterations(self):
        """Test that pipeline runs to max iterations when quality is low."""
        # Create enough responses for 2 full iterations (4 agents each)
        responses = [
            # Iteration 1
            "# Procedure Draft",  # Writer
            '```json\n[]\n```',  # Validator
            "# Edited Draft",  # Editor
            '```json\n{"criteria": [], "overall_score": 5, "passes_threshold": false, "ready_for_publication": false, "revision_suggestions": ["Improve"]}\n```',  # Quality (low)
            # Iteration 2
            "# Procedure Draft v2",  # Writer
            '```json\n[]\n```',  # Validator
            "# Edited Draft v2",  # Editor
            '```json\n{"criteria": [], "overall_score": 6, "passes_threshold": false, "ready_for_publication": false, "revision_suggestions": []}\n```',  # Quality (still low)
        ]

        mock_llm = MockLLMProvider(responses=responses)
        orchestrator = AgentOrchestrator(mock_llm)

        result = orchestrator.run(
            PipelineInput(
                procedure_title="Test",
                max_iterations=2,  # Should run exactly 2 iterations
            ),
            sources=[
                SourceReference(source_id="src_001", title="Test", relevance_score=0.9)
            ],
        )

        assert result.success
        # Pipeline should complete (even with low quality) after max iterations
        assert result.iterations_used == 2
        # Cost should reflect 8 LLM calls (4 per iteration × 2 iterations)
        assert result.total_cost_usd > 0

    def test_pipeline_includes_evidence_summary_in_prompt(self):
        """Evidence summary should be included in writer prompt via style_guide."""
        responses = [
            "# Procedure Draft [S:SRC0001]",  # Writer
            '```json\n[]\n```',  # Validator
            "# Edited Draft [S:SRC0001]",  # Editor
            '```json\n{"criteria": [], "overall_score": 9, "passes_threshold": true, "ready_for_publication": true, "revision_suggestions": []}\n```',  # Quality
        ]
        mock_llm = RecordingLLMProvider(responses=responses)
        orchestrator = AgentOrchestrator(mock_llm)

        evidence_summary = "Dette er en evidens-syntese med nøglepunkter."
        result = orchestrator.run(
            PipelineInput(
                procedure_title="Test Procedure",
                max_iterations=1,
                evidence_summary=evidence_summary,
            ),
            sources=[
                SourceReference(source_id="SRC0001", title="Test", relevance_score=0.9)
            ],
        )

        assert result.success
        flat_prompt = "\n".join(
            msg["content"] for call in mock_llm.calls for msg in call if "content" in msg
        )
        assert evidence_summary in flat_prompt


class TestAgentStats:
    """Tests for agent statistics tracking."""

    def test_stats_accumulation(self):
        """Test that stats accumulate across LLM calls."""
        mock_llm = MockLLMProvider(responses=["response1", "response2"])
        agent = WriterAgent(mock_llm)

        # Make multiple calls
        agent.llm_call([{"role": "user", "content": "test"}])
        agent.llm_call([{"role": "user", "content": "test2"}])

        stats = agent.get_stats()
        assert stats.llm_calls == 2
        assert stats.total_tokens == 300  # 150 * 2
        assert stats.cost_usd > 0

    def test_stats_reset(self):
        """Test that stats can be reset."""
        mock_llm = MockLLMProvider(responses=["response"])
        agent = WriterAgent(mock_llm)

        agent.llm_call([{"role": "user", "content": "test"}])
        assert agent.get_stats().llm_calls == 1

        agent.reset_stats()
        assert agent.get_stats().llm_calls == 0


# R6-002: Integration tests with real LLM to catch bugs that mocking hides
# Run with: pytest tests/test_agents.py -m integration --run-integration
import os

import pytest

# Skip integration tests unless explicitly requested
pytestmark_integration = pytest.mark.skipif(
    not os.environ.get("RUN_INTEGRATION_TESTS"),
    reason="Integration tests require RUN_INTEGRATION_TESTS=1 and valid API keys",
)


def _get_real_provider():
    """Get a real LLM provider if API keys are available."""
    from procedurewriter.llm.providers import get_llm_client

    # Try to get a real provider - will raise if no API keys
    try:
        provider = get_llm_client()
        if provider.is_available():
            return provider
    except Exception:
        pass
    return None


@pytest.mark.integration
class TestResearcherAgentIntegration:
    """R6-002: Integration tests for ResearcherAgent with real LLM."""

    @pytest.fixture
    def real_provider(self):
        """Get real LLM provider, skip if unavailable."""
        provider = _get_real_provider()
        if provider is None:
            pytest.skip("No LLM provider available (missing API keys)")
        return provider

    def test_generate_search_terms_real_llm(self, real_provider):
        """Test search term generation with real LLM - catches prompt/parsing bugs."""
        agent = ResearcherAgent(real_provider)

        result = agent.execute(
            ResearcherInput(
                procedure_title="Akut appendicitis behandling",
                max_sources=3,
            )
        )

        assert result.output.success, "Real LLM should return success"
        assert len(result.output.search_terms_used) > 0, "Should generate search terms"
        # Real LLM should return medically relevant terms
        terms_text = " ".join(result.output.search_terms_used).lower()
        assert any(
            term in terms_text for term in ["appendic", "akut", "behandling", "kirurgi"]
        ), f"Terms should be medically relevant: {result.output.search_terms_used}"


@pytest.mark.integration
class TestWriterAgentIntegration:
    """R6-002: Integration tests for WriterAgent with real LLM."""

    @pytest.fixture
    def real_provider(self):
        """Get real LLM provider, skip if unavailable."""
        provider = _get_real_provider()
        if provider is None:
            pytest.skip("No LLM provider available (missing API keys)")
        return provider

    def test_generate_danish_content(self, real_provider):
        """Test that real LLM generates proper Danish medical content."""
        agent = WriterAgent(real_provider)

        sources = [
            SourceReference(
                source_id="test_001",
                title="Dansk Kirurgisk Selskab Guidelines",
                relevance_score=0.95,
            )
        ]

        result = agent.execute(
            WriterInput(
                procedure_title="Akut appendicitis",
                sources=sources,
            )
        )

        assert result.output.success, "Real LLM should return success"
        content = result.output.content_markdown

        # Verify Danish content quality
        assert len(content) > 100, "Content should be substantial"
        # Should contain Danish characters (æ, ø, å)
        has_danish = any(c in content for c in "æøåÆØÅ")
        assert has_danish, "Content should be in Danish with æ/ø/å characters"
        # Should have proper section structure
        assert "##" in content, "Content should have markdown sections"


@pytest.mark.integration
class TestQualityAgentIntegration:
    """R6-002: Integration tests for QualityAgent with real LLM."""

    @pytest.fixture
    def real_provider(self):
        """Get real LLM provider, skip if unavailable."""
        provider = _get_real_provider()
        if provider is None:
            pytest.skip("No LLM provider available (missing API keys)")
        return provider

    def test_quality_scoring_real_content(self, real_provider):
        """Test quality scoring with real LLM catches JSON parsing issues."""
        agent = QualityAgent(real_provider)

        # Provide realistic Danish medical content
        content = """# Akut Appendicitis

## Indikationer
Patienter med klinisk mistanke om akut appendicitis [S:test_001].

## Behandling
Laparoskopisk appendektomi er førstevalg [S:test_001].
"""

        result = agent.execute(
            QualityInput(
                procedure_title="Akut Appendicitis",
                content_markdown=content,
                sources=[
                    SourceReference(
                        source_id="test_001",
                        title="Guidelines",
                        relevance_score=0.9,
                    )
                ],
                citations_used=["test_001"],
            )
        )

        assert result.output.success, "Real LLM should return valid JSON"
        assert 1 <= result.output.overall_score <= 10, "Score should be 1-10"
        assert isinstance(
            result.output.passes_threshold, bool
        ), "passes_threshold should be boolean"

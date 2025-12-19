"""Tests for StudyScreenerAgent - PICO-based study screening.

Following TDD: Tests written before implementation.
"""
from __future__ import annotations

import json
from typing import Literal
from unittest.mock import MagicMock

import pytest

from procedurewriter.agents.meta_analysis.models import PICOData
from procedurewriter.llm.providers import LLMProviderType, LLMResponse


class TestStudyScreenerAgentBasics:
    """Basic functionality tests for StudyScreenerAgent."""

    def _create_mock_llm(self, response_content: str) -> MagicMock:
        """Create a mock LLM provider."""
        mock = MagicMock()
        mock.provider_type = LLMProviderType.OPENAI
        mock.is_available.return_value = True
        mock.chat_completion.return_value = LLMResponse(
            content=response_content,
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            model="gpt-4o-mini",
        )
        return mock

    def test_screener_agent_exists(self) -> None:
        """StudyScreenerAgent should be importable."""
        from procedurewriter.agents.meta_analysis.screener_agent import StudyScreenerAgent

        assert StudyScreenerAgent is not None

    def test_screener_agent_inherits_base_agent(self) -> None:
        """StudyScreenerAgent should inherit from BaseAgent."""
        from procedurewriter.agents.base import BaseAgent
        from procedurewriter.agents.meta_analysis.screener_agent import StudyScreenerAgent

        mock_llm = self._create_mock_llm("{}")
        agent = StudyScreenerAgent(llm=mock_llm)
        assert isinstance(agent, BaseAgent)

    def test_screener_agent_has_name(self) -> None:
        """StudyScreenerAgent should have descriptive name."""
        from procedurewriter.agents.meta_analysis.screener_agent import StudyScreenerAgent

        mock_llm = self._create_mock_llm("{}")
        agent = StudyScreenerAgent(llm=mock_llm)
        assert agent.name == "study_screener"


class TestPICOQuery:
    """Tests for PICOQuery input model."""

    def test_pico_query_exists(self) -> None:
        """PICOQuery should be importable."""
        from procedurewriter.agents.meta_analysis.screener_agent import PICOQuery

        query = PICOQuery(
            population="Adults with hypertension",
            intervention="ACE inhibitors",
            comparison="Placebo or other antihypertensives",
            outcome="Blood pressure reduction",
        )
        assert query.population == "Adults with hypertension"

    def test_pico_query_optional_comparison(self) -> None:
        """PICOQuery should allow optional comparison."""
        from procedurewriter.agents.meta_analysis.screener_agent import PICOQuery

        query = PICOQuery(
            population="Cancer patients",
            intervention="Immunotherapy",
            comparison=None,
            outcome="Overall survival",
        )
        assert query.comparison is None


class TestScreeningDecision:
    """Tests for ScreeningDecision output model."""

    def test_screening_decision_include(self) -> None:
        """ScreeningDecision should support Include decision."""
        from procedurewriter.agents.meta_analysis.screener_agent import ScreeningDecision

        decision = ScreeningDecision(
            decision="Include",
            reason="Study matches all PICO criteria with high confidence",
            confidence=0.95,
        )
        assert decision.decision == "Include"

    def test_screening_decision_exclude(self) -> None:
        """ScreeningDecision should support Exclude decision."""
        from procedurewriter.agents.meta_analysis.screener_agent import ScreeningDecision

        decision = ScreeningDecision(
            decision="Exclude",
            reason="Population does not match: study focuses on children",
            confidence=0.88,
        )
        assert decision.decision == "Exclude"

    def test_screening_decision_manual_verification(self) -> None:
        """ScreeningDecision should flag for manual verification."""
        from procedurewriter.agents.meta_analysis.screener_agent import ScreeningDecision

        decision = ScreeningDecision(
            decision="Include",
            reason="Study appears relevant",
            confidence=0.85,
            needs_manual_verification=True,
            verification_reason="Intervention confidence below 0.90 threshold",
        )
        assert decision.needs_manual_verification is True


class TestScreeningExecution:
    """Tests for screening execution logic."""

    def _create_mock_llm(self, response_content: str) -> MagicMock:
        """Create a mock LLM provider."""
        mock = MagicMock()
        mock.provider_type = LLMProviderType.OPENAI
        mock.is_available.return_value = True
        mock.chat_completion.return_value = LLMResponse(
            content=response_content,
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            model="gpt-4o-mini",
        )
        return mock

    def test_screen_matching_study_includes(self) -> None:
        """Study matching PICO query should be included."""
        from procedurewriter.agents.meta_analysis.screener_agent import (
            StudyScreenerAgent,
            ScreeningInput,
            PICOQuery,
        )

        llm_response = json.dumps({
            "decision": "Include",
            "reason": "Study matches all PICO criteria",
            "confidence": 0.92,
        })
        mock_llm = self._create_mock_llm(llm_response)

        pico_data = PICOData(
            population="Adults with hypertension",
            intervention="ACE inhibitors",
            comparison="Placebo",
            outcome="Blood pressure reduction",
            confidence=0.95,
        )

        query = PICOQuery(
            population="Adults with hypertension",
            intervention="ACE inhibitors",
            comparison="Placebo",
            outcome="Blood pressure reduction",
        )

        agent = StudyScreenerAgent(llm=mock_llm)
        input_data = ScreeningInput(
            study_id="Test2023",
            pico_data=pico_data,
            query=query,
        )

        result = agent.execute(input_data)
        assert result.output.decision == "Include"

    def test_screen_non_matching_study_excludes(self) -> None:
        """Study not matching PICO query should be excluded."""
        from procedurewriter.agents.meta_analysis.screener_agent import (
            StudyScreenerAgent,
            ScreeningInput,
            PICOQuery,
        )

        llm_response = json.dumps({
            "decision": "Exclude",
            "reason": "Population mismatch: study focuses on children, query requires adults",
            "confidence": 0.88,
        })
        mock_llm = self._create_mock_llm(llm_response)

        pico_data = PICOData(
            population="Children with asthma",
            intervention="Bronchodilators",
            comparison="Placebo",
            outcome="Symptom relief",
            confidence=0.90,
        )

        query = PICOQuery(
            population="Adults with COPD",
            intervention="ACE inhibitors",
            comparison="Placebo",
            outcome="Blood pressure reduction",
        )

        agent = StudyScreenerAgent(llm=mock_llm)
        input_data = ScreeningInput(
            study_id="Mismatch2023",
            pico_data=pico_data,
            query=query,
        )

        result = agent.execute(input_data)
        assert result.output.decision == "Exclude"


class TestLowConfidenceFlagging:
    """Tests for neurotic low-confidence flagging rule."""

    def _create_mock_llm(self, response_content: str) -> MagicMock:
        """Create a mock LLM provider."""
        mock = MagicMock()
        mock.provider_type = LLMProviderType.OPENAI
        mock.is_available.return_value = True
        mock.chat_completion.return_value = LLMResponse(
            content=response_content,
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            model="gpt-4o-mini",
        )
        return mock

    def test_low_intervention_confidence_flags_manual_review(self) -> None:
        """Intervention confidence < 0.90 should flag for manual verification."""
        from procedurewriter.agents.meta_analysis.screener_agent import (
            StudyScreenerAgent,
            ScreeningInput,
            PICOQuery,
        )

        # Note: The agent should detect low confidence and flag regardless of LLM response
        llm_response = json.dumps({
            "decision": "Include",
            "reason": "Study appears to match",
            "confidence": 0.85,
        })
        mock_llm = self._create_mock_llm(llm_response)

        # Create PICO with low intervention confidence
        pico_data = PICOData(
            population="Adults with hypertension",
            intervention="Some medication",  # Vague
            comparison="Placebo",
            outcome="Blood pressure",
            confidence=0.85,  # Overall low, implies intervention/outcome low
        )

        query = PICOQuery(
            population="Adults with hypertension",
            intervention="ACE inhibitors",
            comparison="Placebo",
            outcome="Blood pressure reduction",
        )

        agent = StudyScreenerAgent(llm=mock_llm, confidence_threshold=0.90)
        input_data = ScreeningInput(
            study_id="LowConf2023",
            pico_data=pico_data,
            query=query,
        )

        result = agent.execute(input_data)
        # Should flag for manual verification due to low confidence
        assert result.output.needs_manual_verification is True
        assert "confidence" in result.output.verification_reason.lower()

    def test_high_confidence_does_not_flag(self) -> None:
        """High confidence (>= 0.90) should not flag for manual verification."""
        from procedurewriter.agents.meta_analysis.screener_agent import (
            StudyScreenerAgent,
            ScreeningInput,
            PICOQuery,
        )

        llm_response = json.dumps({
            "decision": "Include",
            "reason": "Study matches all criteria with high confidence",
            "confidence": 0.95,
        })
        mock_llm = self._create_mock_llm(llm_response)

        pico_data = PICOData(
            population="Adults with hypertension",
            intervention="ACE inhibitors",
            comparison="Placebo",
            outcome="Blood pressure reduction",
            confidence=0.95,  # High confidence
        )

        query = PICOQuery(
            population="Adults with hypertension",
            intervention="ACE inhibitors",
            comparison="Placebo",
            outcome="Blood pressure reduction",
        )

        agent = StudyScreenerAgent(llm=mock_llm, confidence_threshold=0.90)
        input_data = ScreeningInput(
            study_id="HighConf2023",
            pico_data=pico_data,
            query=query,
        )

        result = agent.execute(input_data)
        assert result.output.needs_manual_verification is False

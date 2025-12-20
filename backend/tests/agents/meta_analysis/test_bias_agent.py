"""Tests for BiasAssessmentAgent - RoB 2.0 bias assessment.

Following TDD: Tests written before implementation.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock

from procedurewriter.agents.meta_analysis.models import RiskOfBias, RiskOfBiasAssessment
from procedurewriter.llm.providers import LLMProviderType, LLMResponse


class TestBiasAssessmentAgentBasics:
    """Basic functionality tests for BiasAssessmentAgent."""

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

    def test_bias_agent_exists(self) -> None:
        """BiasAssessmentAgent should be importable."""
        from procedurewriter.agents.meta_analysis.bias_agent import BiasAssessmentAgent

        assert BiasAssessmentAgent is not None

    def test_bias_agent_inherits_base_agent(self) -> None:
        """BiasAssessmentAgent should inherit from BaseAgent."""
        from procedurewriter.agents.base import BaseAgent
        from procedurewriter.agents.meta_analysis.bias_agent import BiasAssessmentAgent

        mock_llm = self._create_mock_llm("{}")
        agent = BiasAssessmentAgent(llm=mock_llm)
        assert isinstance(agent, BaseAgent)

    def test_bias_agent_has_name(self) -> None:
        """BiasAssessmentAgent should have descriptive name."""
        from procedurewriter.agents.meta_analysis.bias_agent import BiasAssessmentAgent

        mock_llm = self._create_mock_llm("{}")
        agent = BiasAssessmentAgent(llm=mock_llm)
        assert agent.name == "bias_assessor"


class TestBiasAssessmentInput:
    """Tests for BiasAssessmentInput model."""

    def test_input_requires_study_text(self) -> None:
        """BiasAssessmentInput should require study text."""
        from procedurewriter.agents.meta_analysis.bias_agent import BiasAssessmentInput

        input_data = BiasAssessmentInput(
            study_id="Test2023",
            title="Randomized trial of Drug X",
            abstract="We conducted a double-blind randomized controlled trial...",
            methods="Participants were randomly assigned using computer-generated sequence...",
        )
        assert input_data.study_id == "Test2023"

    def test_input_methods_optional(self) -> None:
        """BiasAssessmentInput should allow optional methods section."""
        from procedurewriter.agents.meta_analysis.bias_agent import BiasAssessmentInput

        input_data = BiasAssessmentInput(
            study_id="NoMethods2023",
            title="Study title",
            abstract="Abstract only...",
        )
        assert input_data.methods is None


class TestBiasAssessmentOutput:
    """Tests for BiasAssessmentOutput model."""

    def test_output_contains_all_rob_domains(self) -> None:
        """BiasAssessmentOutput should contain all RoB 2.0 domains."""
        from procedurewriter.agents.meta_analysis.bias_agent import BiasAssessmentOutput

        output = BiasAssessmentOutput(
            study_id="Test2023",
            assessment=RiskOfBiasAssessment(
                randomization=RiskOfBias.LOW,
                deviations=RiskOfBias.LOW,
                missing_data=RiskOfBias.SOME_CONCERNS,
                measurement=RiskOfBias.LOW,
                selection=RiskOfBias.LOW,
            ),
            linguistic_markers={
                "blinding": True,
                "intention_to_treat": True,
                "power_analysis": False,
            },
            domain_justifications={
                "randomization": "Computer-generated random sequence described",
                "deviations": "Double-blind design maintained",
                "missing_data": "15% dropout rate, reasons not fully explained",
                "measurement": "Validated outcome measures used",
                "selection": "Pre-registered protocol followed",
            },
        )
        assert output.assessment.randomization == RiskOfBias.LOW
        assert output.assessment.overall == RiskOfBias.SOME_CONCERNS


class TestLinguisticMarkerDetection:
    """Tests for linguistic marker detection."""

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

    def test_detects_blinding_markers(self) -> None:
        """Agent should detect blinding linguistic markers."""
        from procedurewriter.agents.meta_analysis.bias_agent import (
            BiasAssessmentAgent,
            BiasAssessmentInput,
        )

        llm_response = json.dumps({
            "randomization": "low",
            "deviations": "low",
            "missing_data": "low",
            "measurement": "low",
            "selection": "low",
            "linguistic_markers": {
                "blinding": True,
                "intention_to_treat": False,
                "power_analysis": False,
            },
            "domain_justifications": {
                "randomization": "Adequate randomization",
                "deviations": "Double-blind maintained",
                "missing_data": "Complete follow-up",
                "measurement": "Blinded outcome assessment",
                "selection": "Protocol followed",
            },
        })
        mock_llm = self._create_mock_llm(llm_response)

        agent = BiasAssessmentAgent(llm=mock_llm)
        input_data = BiasAssessmentInput(
            study_id="Blinded2023",
            title="Double-blind randomized trial",
            abstract="This was a double-blind, placebo-controlled trial...",
            methods="Neither participants nor investigators knew group assignment...",
        )

        result = agent.execute(input_data)
        assert result.output.linguistic_markers["blinding"] is True

    def test_detects_intention_to_treat(self) -> None:
        """Agent should detect intention-to-treat markers."""
        from procedurewriter.agents.meta_analysis.bias_agent import (
            BiasAssessmentAgent,
            BiasAssessmentInput,
        )

        llm_response = json.dumps({
            "randomization": "low",
            "deviations": "low",
            "missing_data": "low",
            "measurement": "low",
            "selection": "low",
            "linguistic_markers": {
                "blinding": False,
                "intention_to_treat": True,
                "power_analysis": False,
            },
            "domain_justifications": {
                "randomization": "Adequate",
                "deviations": "ITT analysis used",
                "missing_data": "All randomized analyzed",
                "measurement": "Objective outcomes",
                "selection": "Pre-specified analysis",
            },
        })
        mock_llm = self._create_mock_llm(llm_response)

        agent = BiasAssessmentAgent(llm=mock_llm)
        input_data = BiasAssessmentInput(
            study_id="ITT2023",
            title="Trial with ITT analysis",
            abstract="Analysis was performed on intention-to-treat basis...",
        )

        result = agent.execute(input_data)
        assert result.output.linguistic_markers["intention_to_treat"] is True

    def test_detects_power_analysis(self) -> None:
        """Agent should detect power analysis markers."""
        from procedurewriter.agents.meta_analysis.bias_agent import (
            BiasAssessmentAgent,
            BiasAssessmentInput,
        )

        llm_response = json.dumps({
            "randomization": "low",
            "deviations": "low",
            "missing_data": "low",
            "measurement": "low",
            "selection": "low",
            "linguistic_markers": {
                "blinding": False,
                "intention_to_treat": False,
                "power_analysis": True,
            },
            "domain_justifications": {
                "randomization": "Adequate",
                "deviations": "Protocol followed",
                "missing_data": "Low dropout",
                "measurement": "Valid measures",
                "selection": "A priori power calculation",
            },
        })
        mock_llm = self._create_mock_llm(llm_response)

        agent = BiasAssessmentAgent(llm=mock_llm)
        input_data = BiasAssessmentInput(
            study_id="Power2023",
            title="Adequately powered trial",
            abstract="Sample size was calculated a priori with 80% power...",
            methods="Power analysis indicated 200 participants needed...",
        )

        result = agent.execute(input_data)
        assert result.output.linguistic_markers["power_analysis"] is True


class TestBiasAssessmentExecution:
    """Tests for bias assessment execution."""

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

    def test_assess_low_risk_study(self) -> None:
        """Well-conducted study should be assessed as low risk."""
        from procedurewriter.agents.meta_analysis.bias_agent import (
            BiasAssessmentAgent,
            BiasAssessmentInput,
        )

        llm_response = json.dumps({
            "randomization": "low",
            "deviations": "low",
            "missing_data": "low",
            "measurement": "low",
            "selection": "low",
            "linguistic_markers": {
                "blinding": True,
                "intention_to_treat": True,
                "power_analysis": True,
            },
            "domain_justifications": {
                "randomization": "Computer-generated sequence with allocation concealment",
                "deviations": "Double-blind design, ITT analysis",
                "missing_data": "98% follow-up achieved",
                "measurement": "Blinded outcome assessors",
                "selection": "Pre-registered protocol, all outcomes reported",
            },
        })
        mock_llm = self._create_mock_llm(llm_response)

        agent = BiasAssessmentAgent(llm=mock_llm)
        input_data = BiasAssessmentInput(
            study_id="HighQuality2023",
            title="Well-conducted RCT",
            abstract="This double-blind, randomized, placebo-controlled trial...",
            methods="Randomization was computer-generated with concealed allocation...",
        )

        result = agent.execute(input_data)
        assert result.output.assessment.overall == RiskOfBias.LOW

    def test_assess_high_risk_study(self) -> None:
        """Poorly conducted study should be assessed as high risk."""
        from procedurewriter.agents.meta_analysis.bias_agent import (
            BiasAssessmentAgent,
            BiasAssessmentInput,
        )

        llm_response = json.dumps({
            "randomization": "high",
            "deviations": "some_concerns",
            "missing_data": "high",
            "measurement": "some_concerns",
            "selection": "some_concerns",
            "linguistic_markers": {
                "blinding": False,
                "intention_to_treat": False,
                "power_analysis": False,
            },
            "domain_justifications": {
                "randomization": "No details on randomization method",
                "deviations": "Open-label design",
                "missing_data": "40% dropout with no explanation",
                "measurement": "Subjective outcomes, unblinded",
                "selection": "No protocol registration found",
            },
        })
        mock_llm = self._create_mock_llm(llm_response)

        agent = BiasAssessmentAgent(llm=mock_llm)
        input_data = BiasAssessmentInput(
            study_id="PoorQuality2023",
            title="Questionable trial",
            abstract="Patients were assigned to groups...",
        )

        result = agent.execute(input_data)
        assert result.output.assessment.overall == RiskOfBias.HIGH

    def test_provides_domain_justifications(self) -> None:
        """Agent should provide justifications for each domain assessment."""
        from procedurewriter.agents.meta_analysis.bias_agent import (
            BiasAssessmentAgent,
            BiasAssessmentInput,
        )

        llm_response = json.dumps({
            "randomization": "low",
            "deviations": "some_concerns",
            "missing_data": "low",
            "measurement": "low",
            "selection": "low",
            "linguistic_markers": {
                "blinding": True,
                "intention_to_treat": True,
                "power_analysis": False,
            },
            "domain_justifications": {
                "randomization": "Block randomization with sealed envelopes",
                "deviations": "Some protocol deviations noted but addressed",
                "missing_data": "Complete data for primary outcome",
                "measurement": "Core outcome set used",
                "selection": "CONSORT compliant reporting",
            },
        })
        mock_llm = self._create_mock_llm(llm_response)

        agent = BiasAssessmentAgent(llm=mock_llm)
        input_data = BiasAssessmentInput(
            study_id="Justified2023",
            title="Trial with justifications",
            abstract="A randomized controlled trial...",
        )

        result = agent.execute(input_data)
        assert "randomization" in result.output.domain_justifications
        assert len(result.output.domain_justifications) == 5

"""Tests for PICO extractor with cross-lingual support.

Following TDD: Tests written before implementation.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from procedurewriter.agents.meta_analysis.models import ManualReviewRequired, PICOData
from procedurewriter.llm.providers import LLMProviderType, LLMResponse


class TestPICOExtractorBasics:
    """Basic functionality tests for PICO extractor."""

    def _create_mock_llm(self, response_content: str) -> MagicMock:
        """Create a mock LLM provider with specified response."""
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

    def test_pico_extractor_exists(self) -> None:
        """PICOExtractor class should be importable."""
        from procedurewriter.agents.meta_analysis.pico_extractor import PICOExtractor

        assert PICOExtractor is not None

    def test_pico_extractor_inherits_base_agent(self) -> None:
        """PICOExtractor should inherit from BaseAgent."""
        from procedurewriter.agents.base import BaseAgent
        from procedurewriter.agents.meta_analysis.pico_extractor import PICOExtractor

        mock_llm = self._create_mock_llm("{}")
        extractor = PICOExtractor(llm=mock_llm)
        assert isinstance(extractor, BaseAgent)

    def test_pico_extractor_has_name_property(self) -> None:
        """PICOExtractor should have descriptive name."""
        from procedurewriter.agents.meta_analysis.pico_extractor import PICOExtractor

        mock_llm = self._create_mock_llm("{}")
        extractor = PICOExtractor(llm=mock_llm)
        assert extractor.name == "pico_extractor"


class TestPICOExtraction:
    """Tests for PICO extraction functionality."""

    def _create_mock_llm(self, response_content: str) -> MagicMock:
        """Create a mock LLM provider with specified response."""
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

    def test_extract_pico_from_english_abstract(self) -> None:
        """Extract PICO elements from English abstract."""
        from procedurewriter.agents.meta_analysis.pico_extractor import (
            PICOExtractor,
            PICOExtractionInput,
        )

        llm_response = json.dumps({
            "population": "Adults with hypertension",
            "intervention": "ACE inhibitors",
            "comparison": "Placebo",
            "outcome": "Blood pressure reduction",
            "confidence": 0.92,
            "population_mesh": ["Hypertension", "Adult"],
            "intervention_mesh": ["Angiotensin-Converting Enzyme Inhibitors"],
            "outcome_mesh": ["Blood Pressure"],
            "detected_language": "en",
        })
        mock_llm = self._create_mock_llm(llm_response)

        extractor = PICOExtractor(llm=mock_llm)
        input_data = PICOExtractionInput(
            study_id="Test2023",
            title="ACE inhibitors in hypertension",
            abstract="This RCT compared ACE inhibitors to placebo in adults with hypertension...",
        )

        result = extractor.execute(input_data)

        # Success is implied by not raising ManualReviewRequired
        assert result.output.population == "Adults with hypertension"
        assert result.output.intervention == "ACE inhibitors"
        assert result.output.confidence == 0.92

    def test_extract_pico_from_danish_abstract(self) -> None:
        """Extract PICO from Danish abstract with MeSH normalization."""
        from procedurewriter.agents.meta_analysis.pico_extractor import (
            PICOExtractor,
            PICOExtractionInput,
        )

        # LLM extracts Danish terms and normalizes to English MeSH
        llm_response = json.dumps({
            "population": "Voksne med hypertension",
            "intervention": "ACE-hæmmere",
            "comparison": "Placebo",
            "outcome": "Blodtrykssænkning",
            "confidence": 0.88,
            "population_mesh": ["Hypertension", "Adult"],
            "intervention_mesh": ["Angiotensin-Converting Enzyme Inhibitors"],
            "outcome_mesh": ["Blood Pressure"],
            "detected_language": "da",
        })
        mock_llm = self._create_mock_llm(llm_response)

        extractor = PICOExtractor(llm=mock_llm)
        input_data = PICOExtractionInput(
            study_id="Hansen2022",
            title="ACE-hæmmere ved hypertension",
            abstract="Dette RCT sammenlignede ACE-hæmmere med placebo hos voksne med hypertension...",
        )

        result = extractor.execute(input_data)

        # Success is implied by not raising ManualReviewRequired
        # Original Danish text preserved
        assert "hypertension" in result.output.population.lower()
        # MeSH terms normalized to English
        assert "Hypertension" in result.output.population_mesh
        assert "Angiotensin-Converting Enzyme Inhibitors" in result.output.intervention_mesh

    def test_extract_pico_optional_comparison(self) -> None:
        """Single-arm studies should have None comparison."""
        from procedurewriter.agents.meta_analysis.pico_extractor import (
            PICOExtractor,
            PICOExtractionInput,
        )

        llm_response = json.dumps({
            "population": "Cancer patients",
            "intervention": "Chemotherapy regimen X",
            "comparison": None,
            "outcome": "Overall survival",
            "confidence": 0.85,
            "population_mesh": ["Neoplasms"],
            "intervention_mesh": ["Antineoplastic Agents"],
            "outcome_mesh": ["Survival"],
            "detected_language": "en",
        })
        mock_llm = self._create_mock_llm(llm_response)

        extractor = PICOExtractor(llm=mock_llm)
        input_data = PICOExtractionInput(
            study_id="SingleArm2023",
            title="Phase II trial of chemotherapy X",
            abstract="Single-arm study of chemotherapy in cancer patients...",
        )

        result = extractor.execute(input_data)

        # Success is implied by not raising ManualReviewRequired
        assert result.output.comparison is None


class TestConfidenceGating:
    """Tests for confidence-based manual review gating."""

    def _create_mock_llm(self, response_content: str) -> MagicMock:
        """Create a mock LLM provider with specified response."""
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

    def test_high_confidence_succeeds(self) -> None:
        """Confidence >= 0.85 should return successful result."""
        from procedurewriter.agents.meta_analysis.pico_extractor import (
            PICOExtractor,
            PICOExtractionInput,
        )

        llm_response = json.dumps({
            "population": "Adults",
            "intervention": "Drug X",
            "comparison": "Placebo",
            "outcome": "Recovery",
            "confidence": 0.85,
            "population_mesh": [],
            "intervention_mesh": [],
            "outcome_mesh": [],
            "detected_language": "en",
        })
        mock_llm = self._create_mock_llm(llm_response)

        extractor = PICOExtractor(llm=mock_llm)
        input_data = PICOExtractionInput(
            study_id="HighConf2023",
            title="Study",
            abstract="Abstract text...",
        )

        result = extractor.execute(input_data)

        # Success is implied by not raising ManualReviewRequired
        assert result.output.confidence >= 0.85

    def test_low_confidence_raises_manual_review(self) -> None:
        """Confidence < 0.85 should raise ManualReviewRequired."""
        from procedurewriter.agents.meta_analysis.pico_extractor import (
            PICOExtractor,
            PICOExtractionInput,
        )

        llm_response = json.dumps({
            "population": "Unclear population",
            "intervention": "Some intervention",
            "comparison": "Unknown",
            "outcome": "Vague outcome",
            "confidence": 0.72,
            "population_mesh": [],
            "intervention_mesh": [],
            "outcome_mesh": [],
            "detected_language": "en",
        })
        mock_llm = self._create_mock_llm(llm_response)

        extractor = PICOExtractor(llm=mock_llm)
        input_data = PICOExtractionInput(
            study_id="LowConf2023",
            title="Ambiguous study",
            abstract="Poorly written abstract...",
        )

        with pytest.raises(ManualReviewRequired) as exc_info:
            extractor.execute(input_data)

        assert exc_info.value.confidence == 0.72
        assert exc_info.value.study_id == "LowConf2023"
        assert "threshold" in exc_info.value.reason.lower() or "confidence" in exc_info.value.reason.lower()

    def test_confidence_threshold_is_configurable(self) -> None:
        """Confidence threshold should be configurable."""
        from procedurewriter.agents.meta_analysis.pico_extractor import (
            PICOExtractor,
            PICOExtractionInput,
        )

        llm_response = json.dumps({
            "population": "Adults",
            "intervention": "Drug",
            "comparison": "Placebo",
            "outcome": "Recovery",
            "confidence": 0.80,
            "population_mesh": [],
            "intervention_mesh": [],
            "outcome_mesh": [],
            "detected_language": "en",
        })
        mock_llm = self._create_mock_llm(llm_response)

        # Lower threshold to 0.75 - should succeed
        extractor = PICOExtractor(llm=mock_llm, confidence_threshold=0.75)
        input_data = PICOExtractionInput(
            study_id="Configurable2023",
            title="Study",
            abstract="Abstract...",
        )

        result = extractor.execute(input_data)
        # Success is implied by not raising ManualReviewRequired
        assert result.output.confidence >= 0.75


class TestMultiPassExtraction:
    """Tests for multi-pass extraction with self-correction."""

    def _create_mock_llm_sequence(self, responses: list[str]) -> MagicMock:
        """Create mock LLM that returns different responses in sequence."""
        mock = MagicMock()
        mock.provider_type = LLMProviderType.OPENAI
        mock.is_available.return_value = True

        response_objects = [
            LLMResponse(
                content=r,
                input_tokens=100,
                output_tokens=50,
                total_tokens=150,
                model="gpt-4o-mini",
            )
            for r in responses
        ]
        mock.chat_completion.side_effect = response_objects
        return mock

    def test_self_correction_improves_confidence(self) -> None:
        """Second pass should attempt to improve low-confidence extraction."""
        from procedurewriter.agents.meta_analysis.pico_extractor import (
            PICOExtractor,
            PICOExtractionInput,
        )

        # First pass: low confidence
        first_response = json.dumps({
            "population": "Patients",
            "intervention": "Treatment",
            "comparison": "Control",
            "outcome": "Outcome",
            "confidence": 0.70,
            "population_mesh": [],
            "intervention_mesh": [],
            "outcome_mesh": [],
            "detected_language": "en",
        })

        # Second pass: improved confidence after self-correction
        second_response = json.dumps({
            "population": "Adults with diabetes mellitus type 2",
            "intervention": "Metformin 500mg daily",
            "comparison": "Placebo",
            "outcome": "HbA1c reduction",
            "confidence": 0.91,
            "population_mesh": ["Diabetes Mellitus, Type 2", "Adult"],
            "intervention_mesh": ["Metformin"],
            "outcome_mesh": ["Glycated Hemoglobin A"],
            "detected_language": "en",
        })

        mock_llm = self._create_mock_llm_sequence([first_response, second_response])

        extractor = PICOExtractor(llm=mock_llm, enable_self_correction=True)
        input_data = PICOExtractionInput(
            study_id="SelfCorrect2023",
            title="Metformin in T2DM",
            abstract="Randomized trial of metformin in type 2 diabetes...",
        )

        result = extractor.execute(input_data)

        # Should succeed after self-correction (implied by not raising exception)
        assert result.output.confidence >= 0.85
        assert mock_llm.chat_completion.call_count == 2


class TestInputValidation:
    """Tests for input validation."""

    def _create_mock_llm(self, response_content: str) -> MagicMock:
        """Create a mock LLM provider with specified response."""
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

    def test_input_requires_study_id(self) -> None:
        """PICOExtractionInput should require study_id."""
        from pydantic import ValidationError
        from procedurewriter.agents.meta_analysis.pico_extractor import PICOExtractionInput

        with pytest.raises(ValidationError):
            PICOExtractionInput(
                title="Title",
                abstract="Abstract",
            )

    def test_input_requires_at_least_title_or_abstract(self) -> None:
        """PICOExtractionInput should require at least title or abstract."""
        from pydantic import ValidationError
        from procedurewriter.agents.meta_analysis.pico_extractor import PICOExtractionInput

        with pytest.raises(ValidationError):
            PICOExtractionInput(
                study_id="NoContent2023",
            )

    def test_input_with_methods_section(self) -> None:
        """PICOExtractionInput should accept optional methods section."""
        from procedurewriter.agents.meta_analysis.pico_extractor import PICOExtractionInput

        input_data = PICOExtractionInput(
            study_id="WithMethods2023",
            title="Study title",
            abstract="Abstract text",
            methods="Detailed methods section with study design...",
        )
        assert input_data.methods == "Detailed methods section with study design..."

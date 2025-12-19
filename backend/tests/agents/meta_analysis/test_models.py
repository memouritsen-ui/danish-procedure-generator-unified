"""Tests for meta-analysis data models.

Following Cochrane standards for systematic review data structures.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError


class TestPICOData:
    """Tests for PICO (Population, Intervention, Comparison, Outcome) data model."""

    def test_pico_data_valid_confidence(self) -> None:
        """PICOData should accept confidence values between 0 and 1."""
        from procedurewriter.agents.meta_analysis.models import PICOData

        pico = PICOData(
            population="Adults with hypertension",
            intervention="ACE inhibitors",
            comparison="Placebo",
            outcome="Blood pressure reduction",
            confidence=0.95,
        )
        assert pico.confidence == 0.95

    def test_pico_data_confidence_at_boundaries(self) -> None:
        """PICOData should accept confidence at 0.0 and 1.0."""
        from procedurewriter.agents.meta_analysis.models import PICOData

        pico_low = PICOData(
            population="P",
            intervention="I",
            comparison="C",
            outcome="O",
            confidence=0.0,
        )
        assert pico_low.confidence == 0.0

        pico_high = PICOData(
            population="P",
            intervention="I",
            comparison="C",
            outcome="O",
            confidence=1.0,
        )
        assert pico_high.confidence == 1.0

    def test_pico_data_rejects_confidence_above_one(self) -> None:
        """PICOData should reject confidence > 1.0."""
        from procedurewriter.agents.meta_analysis.models import PICOData

        with pytest.raises(ValidationError) as exc_info:
            PICOData(
                population="P",
                intervention="I",
                comparison="C",
                outcome="O",
                confidence=1.01,
            )
        assert "confidence" in str(exc_info.value).lower()

    def test_pico_data_rejects_negative_confidence(self) -> None:
        """PICOData should reject confidence < 0.0."""
        from procedurewriter.agents.meta_analysis.models import PICOData

        with pytest.raises(ValidationError) as exc_info:
            PICOData(
                population="P",
                intervention="I",
                comparison="C",
                outcome="O",
                confidence=-0.01,
            )
        assert "confidence" in str(exc_info.value).lower()

    def test_pico_data_optional_comparison(self) -> None:
        """PICOData should allow None comparison for single-arm studies."""
        from procedurewriter.agents.meta_analysis.models import PICOData

        pico = PICOData(
            population="Adults",
            intervention="Drug X",
            comparison=None,
            outcome="Mortality",
            confidence=0.9,
        )
        assert pico.comparison is None

    def test_pico_data_mesh_terms(self) -> None:
        """PICOData should support MeSH term normalization."""
        from procedurewriter.agents.meta_analysis.models import PICOData

        pico = PICOData(
            population="Hypertensive patients",
            intervention="Angiotensin-converting enzyme inhibitors",
            comparison="Placebo",
            outcome="Blood pressure",
            confidence=0.92,
            population_mesh=["Hypertension", "Adult"],
            intervention_mesh=["Angiotensin-Converting Enzyme Inhibitors"],
            outcome_mesh=["Blood Pressure"],
        )
        assert "Hypertension" in pico.population_mesh
        assert "Angiotensin-Converting Enzyme Inhibitors" in pico.intervention_mesh


class TestRiskOfBias:
    """Tests for Cochrane Risk of Bias 2.0 enum."""

    def test_risk_of_bias_values(self) -> None:
        """RiskOfBias should have Low, SomeConcerns, and High values."""
        from procedurewriter.agents.meta_analysis.models import RiskOfBias

        assert RiskOfBias.LOW.value == "low"
        assert RiskOfBias.SOME_CONCERNS.value == "some_concerns"
        assert RiskOfBias.HIGH.value == "high"

    def test_risk_of_bias_from_string(self) -> None:
        """RiskOfBias should be constructible from string values."""
        from procedurewriter.agents.meta_analysis.models import RiskOfBias

        assert RiskOfBias("low") == RiskOfBias.LOW
        assert RiskOfBias("some_concerns") == RiskOfBias.SOME_CONCERNS
        assert RiskOfBias("high") == RiskOfBias.HIGH


class TestRiskOfBiasAssessment:
    """Tests for RoB 2.0 domain-level assessment."""

    def test_rob_assessment_all_domains(self) -> None:
        """RiskOfBiasAssessment should cover all 5 RoB 2.0 domains."""
        from procedurewriter.agents.meta_analysis.models import (
            RiskOfBias,
            RiskOfBiasAssessment,
        )

        rob = RiskOfBiasAssessment(
            randomization=RiskOfBias.LOW,
            deviations=RiskOfBias.LOW,
            missing_data=RiskOfBias.SOME_CONCERNS,
            measurement=RiskOfBias.LOW,
            selection=RiskOfBias.LOW,
        )
        assert rob.randomization == RiskOfBias.LOW
        assert rob.missing_data == RiskOfBias.SOME_CONCERNS

    def test_rob_assessment_overall_judgment(self) -> None:
        """RiskOfBiasAssessment should compute overall judgment correctly."""
        from procedurewriter.agents.meta_analysis.models import (
            RiskOfBias,
            RiskOfBiasAssessment,
        )

        # All low = overall low
        rob_low = RiskOfBiasAssessment(
            randomization=RiskOfBias.LOW,
            deviations=RiskOfBias.LOW,
            missing_data=RiskOfBias.LOW,
            measurement=RiskOfBias.LOW,
            selection=RiskOfBias.LOW,
        )
        assert rob_low.overall == RiskOfBias.LOW

        # Any high = overall high
        rob_high = RiskOfBiasAssessment(
            randomization=RiskOfBias.LOW,
            deviations=RiskOfBias.HIGH,
            missing_data=RiskOfBias.LOW,
            measurement=RiskOfBias.LOW,
            selection=RiskOfBias.LOW,
        )
        assert rob_high.overall == RiskOfBias.HIGH

        # Some concerns but no high = some concerns
        rob_concerns = RiskOfBiasAssessment(
            randomization=RiskOfBias.LOW,
            deviations=RiskOfBias.SOME_CONCERNS,
            missing_data=RiskOfBias.LOW,
            measurement=RiskOfBias.SOME_CONCERNS,
            selection=RiskOfBias.LOW,
        )
        assert rob_concerns.overall == RiskOfBias.SOME_CONCERNS


class TestStatisticalMetrics:
    """Tests for statistical metrics used in meta-analysis."""

    def test_statistical_metrics_effect_size_types(self) -> None:
        """StatisticalMetrics should support OR, RR, and SMD effect sizes."""
        from procedurewriter.agents.meta_analysis.models import StatisticalMetrics

        # Odds Ratio
        sm_or = StatisticalMetrics(
            effect_size=1.5,
            effect_size_type="OR",
            variance=0.04,
            confidence_interval_lower=1.2,
            confidence_interval_upper=1.9,
            weight=0.15,
        )
        assert sm_or.effect_size_type == "OR"

        # Risk Ratio
        sm_rr = StatisticalMetrics(
            effect_size=0.8,
            effect_size_type="RR",
            variance=0.02,
            confidence_interval_lower=0.6,
            confidence_interval_upper=1.0,
            weight=0.20,
        )
        assert sm_rr.effect_size_type == "RR"

        # Standardized Mean Difference
        sm_smd = StatisticalMetrics(
            effect_size=-0.5,
            effect_size_type="SMD",
            variance=0.08,
            confidence_interval_lower=-0.8,
            confidence_interval_upper=-0.2,
            weight=0.10,
        )
        assert sm_smd.effect_size_type == "SMD"

    def test_statistical_metrics_rejects_invalid_effect_type(self) -> None:
        """StatisticalMetrics should reject invalid effect size types."""
        from procedurewriter.agents.meta_analysis.models import StatisticalMetrics

        with pytest.raises(ValidationError):
            StatisticalMetrics(
                effect_size=1.0,
                effect_size_type="INVALID",
                variance=0.01,
                confidence_interval_lower=0.8,
                confidence_interval_upper=1.2,
                weight=0.1,
            )

    def test_statistical_metrics_weight_range(self) -> None:
        """StatisticalMetrics weight should be between 0 and 1."""
        from procedurewriter.agents.meta_analysis.models import StatisticalMetrics

        sm = StatisticalMetrics(
            effect_size=1.0,
            effect_size_type="OR",
            variance=0.01,
            confidence_interval_lower=0.8,
            confidence_interval_upper=1.2,
            weight=0.5,
        )
        assert sm.weight == 0.5

        with pytest.raises(ValidationError):
            StatisticalMetrics(
                effect_size=1.0,
                effect_size_type="OR",
                variance=0.01,
                confidence_interval_lower=0.8,
                confidence_interval_upper=1.2,
                weight=1.5,  # Invalid: > 1.0
            )

    def test_statistical_metrics_variance_non_negative(self) -> None:
        """StatisticalMetrics variance must be non-negative."""
        from procedurewriter.agents.meta_analysis.models import StatisticalMetrics

        with pytest.raises(ValidationError):
            StatisticalMetrics(
                effect_size=1.0,
                effect_size_type="OR",
                variance=-0.01,  # Invalid: negative
                confidence_interval_lower=0.8,
                confidence_interval_upper=1.2,
                weight=0.1,
            )


class TestStudyResult:
    """Tests for individual study result in meta-analysis."""

    def test_study_result_full_structure(self) -> None:
        """StudyResult should contain all required fields."""
        from procedurewriter.agents.meta_analysis.models import (
            PICOData,
            RiskOfBias,
            RiskOfBiasAssessment,
            StatisticalMetrics,
            StudyResult,
        )

        pico = PICOData(
            population="Adults",
            intervention="Drug X",
            comparison="Placebo",
            outcome="Mortality",
            confidence=0.9,
        )

        rob = RiskOfBiasAssessment(
            randomization=RiskOfBias.LOW,
            deviations=RiskOfBias.LOW,
            missing_data=RiskOfBias.LOW,
            measurement=RiskOfBias.LOW,
            selection=RiskOfBias.LOW,
        )

        stats = StatisticalMetrics(
            effect_size=0.75,
            effect_size_type="RR",
            variance=0.02,
            confidence_interval_lower=0.6,
            confidence_interval_upper=0.95,
            weight=0.12,
        )

        study = StudyResult(
            study_id="Smith2023",
            title="Randomized trial of Drug X",
            authors=["Smith J", "Doe A"],
            year=2023,
            source="pubmed",
            pmid="12345678",
            pico=pico,
            risk_of_bias=rob,
            statistics=stats,
            sample_size=500,
            detected_language="en",
        )

        assert study.study_id == "Smith2023"
        assert study.detected_language == "en"
        assert study.pico.confidence == 0.9

    def test_study_result_detected_language_field(self) -> None:
        """StudyResult should track detected language for cross-lingual support."""
        from procedurewriter.agents.meta_analysis.models import (
            PICOData,
            RiskOfBias,
            RiskOfBiasAssessment,
            StatisticalMetrics,
            StudyResult,
        )

        pico = PICOData(
            population="Voksne med hypertension",
            intervention="ACE-hæmmere",
            comparison="Placebo",
            outcome="Blodtrykssænkning",
            confidence=0.88,
        )

        rob = RiskOfBiasAssessment(
            randomization=RiskOfBias.LOW,
            deviations=RiskOfBias.LOW,
            missing_data=RiskOfBias.LOW,
            measurement=RiskOfBias.LOW,
            selection=RiskOfBias.LOW,
        )

        stats = StatisticalMetrics(
            effect_size=0.8,
            effect_size_type="RR",
            variance=0.03,
            confidence_interval_lower=0.65,
            confidence_interval_upper=0.98,
            weight=0.1,
        )

        study = StudyResult(
            study_id="Hansen2022",
            title="Randomiseret forsøg med ACE-hæmmere",
            authors=["Hansen K"],
            year=2022,
            source="danish_guidelines",
            pico=pico,
            risk_of_bias=rob,
            statistics=stats,
            sample_size=200,
            detected_language="da",
        )

        assert study.detected_language == "da"

    def test_study_result_optional_pmid(self) -> None:
        """StudyResult should allow None pmid for non-PubMed sources."""
        from procedurewriter.agents.meta_analysis.models import (
            PICOData,
            RiskOfBias,
            RiskOfBiasAssessment,
            StatisticalMetrics,
            StudyResult,
        )

        pico = PICOData(
            population="P",
            intervention="I",
            comparison="C",
            outcome="O",
            confidence=0.8,
        )

        rob = RiskOfBiasAssessment(
            randomization=RiskOfBias.LOW,
            deviations=RiskOfBias.LOW,
            missing_data=RiskOfBias.LOW,
            measurement=RiskOfBias.LOW,
            selection=RiskOfBias.LOW,
        )

        stats = StatisticalMetrics(
            effect_size=1.0,
            effect_size_type="OR",
            variance=0.01,
            confidence_interval_lower=0.9,
            confidence_interval_upper=1.1,
            weight=0.1,
        )

        study = StudyResult(
            study_id="LocalGuideline2023",
            title="Danish Guideline",
            authors=["Committee"],
            year=2023,
            source="danish_guidelines",
            pmid=None,
            pico=pico,
            risk_of_bias=rob,
            statistics=stats,
            sample_size=1000,
            detected_language="da",
        )

        assert study.pmid is None


class TestManualReviewRequired:
    """Tests for ManualReviewRequired exception."""

    def test_manual_review_required_exception(self) -> None:
        """ManualReviewRequired should carry confidence and reason."""
        from procedurewriter.agents.meta_analysis.models import ManualReviewRequired

        exc = ManualReviewRequired(
            confidence=0.72,
            reason="PICO extraction confidence below threshold",
            study_id="Test2023",
        )
        assert exc.confidence == 0.72
        assert "threshold" in exc.reason
        assert exc.study_id == "Test2023"

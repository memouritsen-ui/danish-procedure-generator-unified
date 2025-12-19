"""Data models for Cochrane-standard meta-analysis.

Implements PICO framework, Risk of Bias 2.0, and statistical metrics
following Cochrane Handbook for Systematic Reviews of Interventions.
"""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator, computed_field


class RiskOfBias(str, Enum):
    """Cochrane Risk of Bias 2.0 judgment levels.

    Per Cochrane RoB 2.0 tool:
    - LOW: Low risk of bias
    - SOME_CONCERNS: Some concerns about bias
    - HIGH: High risk of bias
    """
    LOW = "low"
    SOME_CONCERNS = "some_concerns"
    HIGH = "high"


class PICOData(BaseModel):
    """PICO framework data for systematic review.

    Population, Intervention, Comparison, Outcome - the foundational
    framework for formulating clinical questions in evidence-based medicine.

    Attributes:
        population: Target patient population/condition.
        intervention: Treatment, exposure, or test under study.
        comparison: Comparator (placebo, alternative treatment, etc.).
                   None for single-arm studies.
        outcome: Clinical outcome of interest.
        confidence: Extraction confidence score (0.0 to 1.0).
        population_mesh: MeSH terms for population normalization.
        intervention_mesh: MeSH terms for intervention normalization.
        outcome_mesh: MeSH terms for outcome normalization.
    """
    population: str = Field(..., min_length=1)
    intervention: str = Field(..., min_length=1)
    comparison: str | None = None
    outcome: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)

    # MeSH term normalization for cross-study comparison
    population_mesh: list[str] = Field(default_factory=list)
    intervention_mesh: list[str] = Field(default_factory=list)
    outcome_mesh: list[str] = Field(default_factory=list)

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        """Validate confidence is in [0, 1] range."""
        if v < 0.0 or v > 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        return v


class RiskOfBiasAssessment(BaseModel):
    """Cochrane Risk of Bias 2.0 domain-level assessment.

    Covers all 5 RoB 2.0 domains for randomized trials:
    1. Randomization process
    2. Deviations from intended interventions
    3. Missing outcome data
    4. Measurement of the outcome
    5. Selection of the reported result

    The overall judgment follows Cochrane algorithm:
    - HIGH if any domain is HIGH
    - SOME_CONCERNS if any domain is SOME_CONCERNS and none HIGH
    - LOW if all domains are LOW
    """
    randomization: RiskOfBias = Field(
        ..., description="Domain 1: Risk of bias arising from the randomization process"
    )
    deviations: RiskOfBias = Field(
        ..., description="Domain 2: Risk of bias due to deviations from intended interventions"
    )
    missing_data: RiskOfBias = Field(
        ..., description="Domain 3: Risk of bias due to missing outcome data"
    )
    measurement: RiskOfBias = Field(
        ..., description="Domain 4: Risk of bias in measurement of the outcome"
    )
    selection: RiskOfBias = Field(
        ..., description="Domain 5: Risk of bias in selection of the reported result"
    )

    @computed_field
    @property
    def overall(self) -> RiskOfBias:
        """Compute overall RoB judgment per Cochrane algorithm."""
        domains = [
            self.randomization,
            self.deviations,
            self.missing_data,
            self.measurement,
            self.selection,
        ]

        # Any HIGH → overall HIGH
        if any(d == RiskOfBias.HIGH for d in domains):
            return RiskOfBias.HIGH

        # Any SOME_CONCERNS → overall SOME_CONCERNS
        if any(d == RiskOfBias.SOME_CONCERNS for d in domains):
            return RiskOfBias.SOME_CONCERNS

        # All LOW → overall LOW
        return RiskOfBias.LOW


class StatisticalMetrics(BaseModel):
    """Statistical metrics for meta-analysis effect estimation.

    Supports standard effect size measures:
    - OR: Odds Ratio (binary outcomes, case-control)
    - RR: Risk Ratio (binary outcomes, cohort/RCT)
    - SMD: Standardized Mean Difference (continuous outcomes)

    Uses inverse-variance weighting for DerSimonian-Laird
    random-effects model pooling.
    """
    effect_size: float = Field(..., description="Point estimate of effect")
    effect_size_type: Literal["OR", "RR", "SMD"] = Field(
        ..., description="Type of effect size measure"
    )
    variance: float = Field(..., ge=0.0, description="Variance of effect estimate")
    confidence_interval_lower: float = Field(
        ..., description="Lower bound of 95% CI"
    )
    confidence_interval_upper: float = Field(
        ..., description="Upper bound of 95% CI"
    )
    weight: float = Field(
        ..., ge=0.0, le=1.0, description="Relative weight in pooled analysis (0-1)"
    )

    @field_validator("variance")
    @classmethod
    def validate_variance_non_negative(cls, v: float) -> float:
        """Variance must be non-negative."""
        if v < 0.0:
            raise ValueError("variance must be non-negative")
        return v

    @field_validator("weight")
    @classmethod
    def validate_weight_range(cls, v: float) -> float:
        """Weight must be in [0, 1] range."""
        if v < 0.0 or v > 1.0:
            raise ValueError("weight must be between 0.0 and 1.0")
        return v


class StudyResult(BaseModel):
    """Complete result data for a single study in meta-analysis.

    Combines bibliographic metadata, PICO extraction, risk of bias
    assessment, and statistical results for systematic review synthesis.
    """
    # Bibliographic metadata
    study_id: str = Field(..., min_length=1, description="Unique study identifier")
    title: str = Field(..., min_length=1)
    authors: list[str] = Field(default_factory=list)
    year: int = Field(..., ge=1900, le=2100)
    source: str = Field(..., description="Data source (pubmed, danish_guidelines, etc.)")
    pmid: str | None = Field(None, description="PubMed ID if available")

    # Extracted data
    pico: PICOData
    risk_of_bias: RiskOfBiasAssessment
    statistics: StatisticalMetrics

    # Study characteristics
    sample_size: int = Field(..., ge=1)
    detected_language: str = Field(
        ...,
        min_length=2,
        max_length=5,
        description="ISO 639-1 language code (en, da, etc.)"
    )


class ManualReviewRequired(Exception):
    """Exception raised when extraction confidence is below threshold.

    Used to flag studies that require human expert review before
    inclusion in meta-analysis. These results are NOT cached to
    allow re-extraction after LLM improvements.
    """

    def __init__(
        self,
        confidence: float,
        reason: str,
        study_id: str,
    ) -> None:
        self.confidence = confidence
        self.reason = reason
        self.study_id = study_id
        super().__init__(
            f"Manual review required for {study_id}: {reason} "
            f"(confidence: {confidence:.2f})"
        )

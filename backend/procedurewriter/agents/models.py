"""
Pydantic models for agent inputs and outputs.

Each agent has specific input/output types that extend the base models.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from procedurewriter.agents.base import AgentInput, AgentOutput

# =============================================================================
# Researcher Agent Models
# =============================================================================

class ResearcherInput(AgentInput):
    """Input for the Researcher agent."""
    max_sources: int = Field(default=10, description="Maximum sources to find")
    search_terms: list[str] | None = Field(default=None, description="Optional specific search terms")


class SourceReference(BaseModel):
    """A source found by the researcher."""
    source_id: str
    title: str
    year: int | str | None = None  # Allow str for "2024" from APIs
    pmid: str | None = None
    doi: str | None = None
    url: str | None = None
    relevance_score: float = Field(default=0.5, ge=0.0, le=1.0)
    abstract_excerpt: str | None = None
    abstract: str | None = None  # Full abstract
    authors: list[str] = Field(default_factory=list)
    source_type: str | None = None  # Evidence type: danish_guideline, systematic_review, rct, etc.
    evidence_tier: str | None = None  # Evidence hierarchy tier
    full_text_available: bool | None = None


class ResearcherOutput(AgentOutput):
    """Output from the Researcher agent."""
    sources: list[SourceReference] = Field(default_factory=list)
    search_terms_used: list[str] = Field(default_factory=list)
    total_results_found: int = 0
    evidence_flags: list[str] = Field(default_factory=list)


# =============================================================================
# Validator Agent Models
# =============================================================================

class ValidatorInput(AgentInput):
    """Input for the Validator agent."""
    claims: list[str] = Field(description="List of claims to validate")
    sources: list[SourceReference] = Field(description="Available sources")


class ClaimValidation(BaseModel):
    """Validation result for a single claim."""
    claim: str
    is_supported: bool
    supporting_source_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    notes: str | None = None


class ValidatorOutput(AgentOutput):
    """Output from the Validator agent."""
    validations: list[ClaimValidation] = Field(default_factory=list)
    supported_count: int = 0
    unsupported_count: int = 0


# =============================================================================
# Writer Agent Models
# =============================================================================

class WriterInput(AgentInput):
    """Input for the Writer agent."""
    sources: list[SourceReference] = Field(description="Sources to cite")
    outline: list[str] | None = Field(default=None, description="Optional section outline")
    style_guide: str | None = Field(default=None, description="Writing style requirements")
    evidence_flags: list[str] | None = Field(default=None, description="Evidence warning flags")


class WriterOutput(AgentOutput):
    """Output from the Writer agent."""
    content_markdown: str = Field(description="Generated procedure in markdown")
    sections: list[str] = Field(default_factory=list, description="Section headings")
    citations_used: list[str] = Field(default_factory=list, description="Source IDs cited")
    word_count: int = 0


# =============================================================================
# Paradox Resolver Agent Models
# =============================================================================

class ParadoxResolverInput(AgentInput):
    """Input for the Paradox Resolver agent."""
    sources: list[SourceReference] = Field(description="Sources to compare")


class ParadoxResolverOutput(AgentOutput):
    """Output from the Paradox Resolver agent."""
    conflicts_detected: bool = False
    adaptation_note: str | None = None
    compared_sources: list[str] = Field(default_factory=list)


# =============================================================================
# Editor Agent Models
# =============================================================================

class EditorInput(AgentInput):
    """Input for the Editor agent."""
    content_markdown: str = Field(description="Content to edit")
    sources: list[SourceReference] = Field(description="Available sources for fact-checking")
    style_guide: str | None = None


class EditSuggestion(BaseModel):
    """A suggested edit from the editor."""
    original_text: str
    suggested_text: str
    reason: str
    severity: str = Field(description="minor, moderate, or critical")


class EditorOutput(AgentOutput):
    """Output from the Editor agent."""
    edited_content: str = Field(description="Edited procedure content")
    suggestions_applied: list[EditSuggestion] = Field(default_factory=list)
    danish_quality_notes: str | None = Field(description="Notes on Danish language quality")


# =============================================================================
# Quality Agent Models
# =============================================================================

class QualityInput(AgentInput):
    """Input for the Quality agent."""
    content_markdown: str = Field(description="Content to evaluate")
    sources: list[SourceReference] = Field(description="Sources used")
    citations_used: list[str] = Field(description="Source IDs cited in content")


class QualityCriterion(BaseModel):
    """Score for a quality criterion."""
    name: str
    score: int = Field(ge=1, le=10)
    notes: str | None = None


class QualityOutput(AgentOutput):
    """Output from the Quality agent."""
    overall_score: int = Field(ge=1, le=10)
    criteria: list[QualityCriterion] = Field(default_factory=list)
    passes_threshold: bool = Field(description="True if score >= 8")
    revision_suggestions: list[str] = Field(default_factory=list)
    ready_for_publication: bool = False


# =============================================================================
# Orchestrator Models
# =============================================================================

class PipelineInput(BaseModel):
    """Input for the full agent pipeline."""
    procedure_title: str
    context: str | None = None
    max_iterations: int = Field(default=3, ge=1, le=5)
    quality_threshold: int = Field(default=8, ge=1, le=10)
    quality_loop_policy: str = Field(default="auto", description="auto or manual")
    quality_loop_max_cost_usd: float | None = Field(default=None, ge=0.0)
    outline: list[str] | None = Field(default=None, description="Section outline to enforce")
    style_guide: str | None = Field(default=None, description="Style guide text for writers/editors")
    evidence_summary: str | None = Field(default=None, description="Evidence synthesis to include in prompts")
    evidence_flags: list[str] | None = Field(default=None, description="Evidence warning flags")


class PipelineOutput(BaseModel):
    """Output from the full agent pipeline."""
    success: bool
    procedure_markdown: str | None = None
    sources: list[SourceReference] = Field(default_factory=list)
    quality_score: int | None = None
    iterations_used: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    quality_loop_stop_reason: str | None = None
    error: str | None = None

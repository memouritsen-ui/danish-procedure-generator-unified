"""
Multi-Agent System for Procedure Generation.

This module provides a 5-agent workflow for generating medical procedures:

1. ResearcherAgent - Searches PubMed and ranks sources
2. ValidatorAgent - Validates claims against sources
3. WriterAgent - Generates procedure content with citations
4. EditorAgent - Improves prose and Danish quality
5. QualityAgent - Scores quality and determines readiness

Usage:
    from procedurewriter.agents import AgentOrchestrator, PipelineInput
    from procedurewriter.llm import get_llm_client

    llm = get_llm_client()
    orchestrator = AgentOrchestrator(llm)

    result = orchestrator.run(PipelineInput(
        procedure_title="Anafylaksi behandling",
        max_iterations=3,
        quality_threshold=8,
    ))

    if result.success:
        print(result.procedure_markdown)
        print(f"Quality: {result.quality_score}/10")
        print(f"Cost: ${result.total_cost_usd:.4f}")
"""

# Base classes
from procedurewriter.agents.base import (
    AgentInput,
    AgentOutput,
    AgentResult,
    AgentStats,
    BaseAgent,
)

# Agents
from procedurewriter.agents.editor import EditorAgent

# Models
from procedurewriter.agents.models import (
    ClaimValidation,
    EditorInput,
    EditorOutput,
    EditSuggestion,
    PipelineInput,
    PipelineOutput,
    QualityCriterion,
    QualityInput,
    QualityOutput,
    ResearcherInput,
    ResearcherOutput,
    SourceReference,
    ValidatorInput,
    ValidatorOutput,
    WriterInput,
    WriterOutput,
)

# Orchestrator
from procedurewriter.agents.orchestrator import AgentOrchestrator, OrchestratorStats
from procedurewriter.agents.quality import QualityAgent
from procedurewriter.agents.researcher import ResearcherAgent
from procedurewriter.agents.validator import ValidatorAgent
from procedurewriter.agents.writer import WriterAgent

__all__ = [
    # Base
    "AgentInput",
    "AgentOutput",
    "AgentResult",
    "AgentStats",
    "BaseAgent",
    # Models
    "ClaimValidation",
    "EditSuggestion",
    "EditorInput",
    "EditorOutput",
    "PipelineInput",
    "PipelineOutput",
    "QualityCriterion",
    "QualityInput",
    "QualityOutput",
    "ResearcherInput",
    "ResearcherOutput",
    "SourceReference",
    "ValidatorInput",
    "ValidatorOutput",
    "WriterInput",
    "WriterOutput",
    # Agents
    "EditorAgent",
    "QualityAgent",
    "ResearcherAgent",
    "ValidatorAgent",
    "WriterAgent",
    # Orchestrator
    "AgentOrchestrator",
    "OrchestratorStats",
]

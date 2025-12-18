"""
Base Agent Class for Multi-Agent Workflow

All agents inherit from BaseAgent and implement the execute() method.
Provides unified LLM access, token tracking, and cost aggregation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from procedurewriter.llm.providers import LLMProvider, LLMResponse, get_default_model


class AgentInput(BaseModel):
    """Base input model for all agents."""
    procedure_title: str
    context: str | None = None


class AgentOutput(BaseModel):
    """Base output model for all agents."""
    success: bool
    error: str | None = None


InputT = TypeVar("InputT", bound=AgentInput)
OutputT = TypeVar("OutputT", bound=AgentOutput)


@dataclass
class AgentStats:
    """Tracks agent execution statistics."""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    llm_calls: int = 0
    execution_time_seconds: float = 0.0

    def add_response(self, response: LLMResponse) -> None:
        """Add token usage from an LLM response."""
        self.input_tokens += response.input_tokens
        self.output_tokens += response.output_tokens
        self.total_tokens += response.total_tokens
        self.cost_usd += response.cost_usd
        self.llm_calls += 1


@dataclass
class AgentResult(Generic[OutputT]):
    """Result wrapper containing output and stats."""
    output: OutputT
    stats: AgentStats = field(default_factory=AgentStats)


class BaseAgent(ABC, Generic[InputT, OutputT]):
    """
    Abstract base class for all procedure generation agents.

    Subclasses must implement:
        - name: Agent name for logging
        - execute(): Main agent logic

    Provides:
        - Unified LLM access via self.llm_call()
        - Automatic token/cost tracking
        - Standardized input/output types
    """

    def __init__(self, llm: LLMProvider, model: str | None = None):
        """
        Initialize the agent.

        Args:
            llm: LLM provider for API calls
            model: Model to use (defaults to provider's default)
        """
        self._llm = llm
        self._model = model or get_default_model(llm.provider_type)
        self._stats = AgentStats()

    @property
    @abstractmethod
    def name(self) -> str:
        """Agent name for logging and identification."""
        pass

    @abstractmethod
    def execute(self, input_data: InputT) -> AgentResult[OutputT]:
        """
        Execute the agent's main logic.

        Args:
            input_data: Typed input for this agent

        Returns:
            AgentResult containing output and execution stats
        """
        pass

    def llm_call(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """
        Make an LLM call with automatic token tracking.

        Args:
            messages: Chat messages (system, user, assistant)
            temperature: Sampling temperature
            max_tokens: Maximum response tokens

        Returns:
            LLMResponse with content and usage
        """
        response = self._llm.chat_completion(
            messages=messages,
            model=self._model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        self._stats.add_response(response)
        return response

    def get_stats(self) -> AgentStats:
        """Get current execution statistics."""
        return self._stats

    def reset_stats(self) -> None:
        """Reset execution statistics for new run."""
        self._stats = AgentStats()

    def _make_system_message(self, content: str) -> dict[str, str]:
        """Helper to create system message."""
        return {"role": "system", "content": content}

    def _make_user_message(self, content: str) -> dict[str, str]:
        """Helper to create user message."""
        return {"role": "user", "content": content}

    def _make_assistant_message(self, content: str) -> dict[str, str]:
        """Helper to create assistant message."""
        return {"role": "assistant", "content": content}

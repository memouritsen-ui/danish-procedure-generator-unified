"""Abstract base class for pipeline stages.

Each stage in the pipeline inherits from PipelineStage and implements:
- name: A string identifier for logging and events
- execute(): The stage's main logic
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

# Input and Output type variables for type-safe stage composition
InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")


class PipelineStage(ABC, Generic[InputT, OutputT]):
    """Abstract base class for all pipeline stages.

    Each stage transforms an input into an output. The output of one
    stage becomes the input of the next stage in the pipeline.

    Type Parameters:
        InputT: The input type for this stage
        OutputT: The output type from this stage
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the stage name for logging and events."""
        ...

    @abstractmethod
    def execute(self, input_data: InputT) -> OutputT:
        """Execute the stage logic.

        Args:
            input_data: The stage input

        Returns:
            The stage output
        """
        ...

from abc import ABC, abstractmethod
from typing import Any


class Tool(ABC):
    """Common interface for tools available to the chat agent."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the tool name exposed to the model."""

    @property
    @abstractmethod
    def definition(self) -> dict[str, Any]:
        """Return the OpenAI-compatible tool definition."""

    @abstractmethod
    def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute the tool with validated model-provided arguments."""

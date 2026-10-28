from dataclasses import dataclass


@dataclass(frozen=True)
class ToolEvalCase:
    """One expected tool-routing decision."""

    name: str
    prompt: str
    expected_tool: str | None
    expected_city: str | None = None

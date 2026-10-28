from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MultiTurnEvalCase:
    """One complete agent-run evaluation case."""

    name: str
    prompt: str
    tool_results: dict[str, dict[str, Any]]
    expected_calls: list[dict[str, Any]]
    judge_requirements: list[str]

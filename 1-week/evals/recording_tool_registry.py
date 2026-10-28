import json
from typing import Any

from tools.tool import Tool
from tools.tool_registry import ToolRegistry


class RecordingToolRegistry(ToolRegistry):
    """Execute registered tools while recording their ordered call trace."""

    def __init__(self, tools: list[Tool]) -> None:
        super().__init__(tools)
        self.calls: list[dict[str, Any]] = []

    def execute(self, tool_call: Any) -> str:
        try:
            arguments = json.loads(tool_call.function.arguments)
        except (json.JSONDecodeError, TypeError):
            arguments = tool_call.function.arguments

        result_text = super().execute(tool_call)
        try:
            result = json.loads(result_text)
        except (json.JSONDecodeError, TypeError):
            result = result_text

        self.calls.append(
            {
                "tool": tool_call.function.name,
                "arguments": arguments,
                "result": result,
            }
        )
        return result_text

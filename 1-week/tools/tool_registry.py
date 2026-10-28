import json
from typing import Any

from .file_system.delete_file_tool import DeleteFileTool
from .file_system.list_files_tool import ListFilesTool
from .file_system.path_guard import PathGuard
from .file_system.read_file_tool import ReadFileTool
from .file_system.write_file_tool import WriteFileTool
from .shell_tool import ShellTool
from .tool import Tool
from .weather_tool import WeatherTool
from .web_search import WebSearchTool


class ToolRegistry:
    """Register tool schemas and dispatch allowlisted tool calls."""

    def __init__(self, tools: list[Tool] | None = None) -> None:
        registered_tools = tools if tools is not None else self._default_tools()
        self.definitions = [tool.definition for tool in registered_tools]
        self._tools = {tool.name: tool for tool in registered_tools}

    @staticmethod
    def _default_tools() -> list[Tool]:
        path_guard = PathGuard.from_environment()
        return [
            WeatherTool(),
            ReadFileTool(path_guard),
            WriteFileTool(path_guard),
            ListFilesTool(path_guard),
            DeleteFileTool(path_guard),
            WebSearchTool(),
            ShellTool(path_guard),
        ]

    def execute(self, tool_call: Any) -> str:
        name = tool_call.function.name
        tool = self._tools.get(name)
        if tool is None:
            return json.dumps({"error": f"Unknown tool: {name}"})

        try:
            arguments = json.loads(tool_call.function.arguments)
            if not isinstance(arguments, dict):
                raise ValueError("Tool arguments must be a JSON object.")
            result = tool.execute(arguments)
            return json.dumps(result, ensure_ascii=False)
        except (json.JSONDecodeError, TypeError, ValueError, RuntimeError) as error:
            return json.dumps({"error": str(error)}, ensure_ascii=False)

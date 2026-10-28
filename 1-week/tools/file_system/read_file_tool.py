from typing import Any

from tools.tool import Tool

from .path_guard import PathGuard


class ReadFileTool(Tool):
    """Read a UTF-8 text file inside the agent files root."""

    NAME = "read_file"
    MAX_BYTES = 1_000_000
    DEFINITION = {
        "type": "function",
        "function": {
            "name": NAME,
            "description": (
                "Read a UTF-8 text file from the sandboxed agent files directory. "
                "The path must be relative to that directory."
            ),
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path of the text file to read.",
                    }
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        },
    }

    def __init__(self, path_guard: PathGuard) -> None:
        self.path_guard = path_guard

    @property
    def name(self) -> str:
        return self.NAME

    @property
    def definition(self) -> dict[str, Any]:
        return self.DEFINITION

    def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        if set(arguments) != {"path"} or not isinstance(arguments["path"], str):
            raise ValueError("Read tool requires one string argument: path.")

        file_path = self.path_guard.resolve(arguments["path"], must_exist=True)
        if not file_path.is_file():
            raise ValueError("The requested path is not a file.")
        size = file_path.stat().st_size
        if size > self.MAX_BYTES:
            raise ValueError(f"File is larger than the {self.MAX_BYTES}-byte limit.")

        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            raise ValueError("Only UTF-8 text files can be read.") from error
        except OSError as error:
            raise RuntimeError(f"Could not read file: {error}") from error

        return {
            "path": self.path_guard.relative_name(file_path),
            "content": content,
            "bytes": size,
        }

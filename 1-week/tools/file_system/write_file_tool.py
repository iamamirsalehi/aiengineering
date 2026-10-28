from typing import Any
from uuid import uuid4

from tools.tool import Tool

from .path_guard import PathGuard


class WriteFileTool(Tool):
    """Create or explicitly overwrite a UTF-8 file inside the sandbox."""

    NAME = "write_file"
    MAX_BYTES = 1_000_000
    DEFINITION = {
        "type": "function",
        "function": {
            "name": NAME,
            "description": (
                "Write a UTF-8 text file in the sandboxed agent files directory. "
                "Set overwrite to true only when replacing an existing file is intended."
            ),
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path of the text file to write.",
                    },
                    "content": {
                        "type": "string",
                        "description": "Complete UTF-8 text content for the file.",
                    },
                    "overwrite": {
                        "type": "boolean",
                        "description": (
                            "Whether an existing file may be replaced. Use false when "
                            "creating a new file."
                        ),
                    },
                },
                "required": ["path", "content", "overwrite"],
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
        if set(arguments) != {"path", "content", "overwrite"}:
            raise ValueError("Write tool requires path, content, and overwrite.")

        path = arguments["path"]
        content = arguments["content"]
        overwrite = arguments["overwrite"]
        if not isinstance(path, str) or not isinstance(content, str):
            raise ValueError("Path and content must be strings.")
        if type(overwrite) is not bool:
            raise ValueError("Overwrite must be a boolean.")

        encoded = content.encode("utf-8")
        if len(encoded) > self.MAX_BYTES:
            raise ValueError(f"Content is larger than the {self.MAX_BYTES}-byte limit.")

        self.path_guard.ensure_root()
        file_path = self.path_guard.resolve(path)
        existed = file_path.exists()
        if existed and file_path.is_dir():
            raise ValueError("The requested path is a directory.")
        if existed and not overwrite:
            raise ValueError("File already exists; set overwrite to true to replace it.")

        temporary_path = file_path.with_name(f".{file_path.name}.{uuid4().hex}.tmp")
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path.write_bytes(encoded)
            temporary_path.replace(file_path)
        except OSError as error:
            raise RuntimeError(f"Could not write file: {error}") from error
        finally:
            if temporary_path.exists():
                temporary_path.unlink()

        return {
            "path": self.path_guard.relative_name(file_path),
            "bytes": len(encoded),
            "action": "overwritten" if existed else "created",
        }

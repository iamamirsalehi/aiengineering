from typing import Any

from tools.tool import Tool

from .path_guard import PathGuard


class ListFilesTool(Tool):
    """List files and directories inside the sandbox."""

    NAME = "list_files"
    MAX_ENTRIES = 200
    DEFINITION = {
        "type": "function",
        "function": {
            "name": NAME,
            "description": (
                "List files and directories in the sandboxed agent files directory. "
                "Paths are relative; use '.' for the root."
            ),
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative directory to list, or '.' for root.",
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "Whether to include nested entries.",
                    },
                },
                "required": ["path", "recursive"],
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
        if set(arguments) != {"path", "recursive"}:
            raise ValueError("List tool requires path and recursive.")

        path = arguments["path"]
        recursive = arguments["recursive"]
        if not isinstance(path, str) or type(recursive) is not bool:
            raise ValueError("Path must be a string and recursive must be a boolean.")

        self.path_guard.ensure_root()
        directory = self.path_guard.resolve(
            path, must_exist=True, allow_root=True
        )
        if not directory.is_dir():
            raise ValueError("The requested path is not a directory.")

        try:
            candidates = directory.rglob("*") if recursive else directory.iterdir()
            visible = [
                item
                for item in candidates
                if self.path_guard.RESERVED_DIRECTORY
                not in item.relative_to(self.path_guard.root).parts
            ]
            visible.sort(key=lambda item: item.as_posix().casefold())
        except OSError as error:
            raise RuntimeError(f"Could not list directory: {error}") from error

        truncated = len(visible) > self.MAX_ENTRIES
        entries = []
        for item in visible[: self.MAX_ENTRIES]:
            if item.is_symlink():
                item_type = "symlink"
                size = None
            elif item.is_dir():
                item_type = "directory"
                size = None
            else:
                item_type = "file"
                size = item.stat().st_size
            entries.append(
                {
                    "path": self.path_guard.relative_name(item),
                    "type": item_type,
                    "bytes": size,
                }
            )

        return {
            "path": self.path_guard.relative_name(directory),
            "recursive": recursive,
            "entries": entries,
            "truncated": truncated,
            "limit": self.MAX_ENTRIES,
        }

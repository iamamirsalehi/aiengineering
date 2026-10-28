import shutil
from typing import Any
from uuid import uuid4

from tools.tool import Tool

from .path_guard import PathGuard


class DeleteFileTool(Tool):
    """Move a file into protected trash after explicit confirmation."""

    NAME = "delete_file"
    DEFINITION = {
        "type": "function",
        "function": {
            "name": NAME,
            "description": (
                "Delete a file from the sandboxed agent files directory by moving "
                "it to protected trash. Set confirm to true only after the user "
                "explicitly asks to delete that specific file. Directories cannot "
                "be deleted."
            ),
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path of the file to delete.",
                    },
                    "confirm": {
                        "type": "boolean",
                        "description": (
                            "Must be true only when deletion of this file was "
                            "explicitly requested by the user."
                        ),
                    },
                },
                "required": ["path", "confirm"],
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
        if set(arguments) != {"path", "confirm"}:
            raise ValueError("Delete tool requires path and confirm.")

        path = arguments["path"]
        confirm = arguments["confirm"]
        if not isinstance(path, str) or type(confirm) is not bool:
            raise ValueError("Path must be a string and confirm must be a boolean.")
        if not confirm:
            raise ValueError("Deletion requires explicit confirmation.")

        file_path = self.path_guard.resolve(path, must_exist=True)
        if not file_path.is_file():
            raise ValueError("Only files can be deleted; directories are not allowed.")

        trash_directory = self.path_guard.root / self.path_guard.RESERVED_DIRECTORY
        trash_name = f"{uuid4().hex}-{file_path.name}"
        destination = trash_directory / trash_name
        try:
            trash_directory.mkdir(parents=True, exist_ok=True)
            shutil.move(str(file_path), str(destination))
        except OSError as error:
            raise RuntimeError(f"Could not delete file: {error}") from error

        return {
            "path": path,
            "deleted": True,
            "recoverable": True,
            "trash_name": trash_name,
        }

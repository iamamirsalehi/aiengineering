import os
from pathlib import Path


class PathGuard:
    """Resolve relative paths while keeping operations inside one root."""

    RESERVED_DIRECTORY = ".trash"

    def __init__(self, root: str | Path) -> None:
        root_path = Path(root).expanduser()
        if not root_path.is_absolute():
            root_path = Path.cwd() / root_path
        self.root = root_path.resolve(strict=False)

    @classmethod
    def from_environment(cls) -> "PathGuard":
        return cls(os.environ.get("AGENT_FILES_ROOT", "agent_files"))

    def ensure_root(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def resolve(
        self,
        relative_path: str,
        *,
        must_exist: bool = False,
        allow_root: bool = False,
    ) -> Path:
        if not isinstance(relative_path, str) or not relative_path.strip():
            raise ValueError("Path must be a non-empty string.")
        if "\x00" in relative_path:
            raise ValueError("Path contains an invalid null character.")

        requested = Path(relative_path)
        if requested.is_absolute():
            raise ValueError("Absolute paths are not allowed.")
        if ".." in requested.parts:
            raise ValueError("Parent-directory traversal is not allowed.")
        if self.RESERVED_DIRECTORY in requested.parts:
            raise ValueError("The protected trash directory is not accessible.")

        candidate = self.root / requested
        resolved = candidate.resolve(strict=False)
        try:
            resolved.relative_to(self.root)
        except ValueError as error:
            raise ValueError("Path must stay inside the agent files root.") from error

        current = self.root
        for part in requested.parts:
            if part in {"", "."}:
                continue
            current = current / part
            if current.is_symlink():
                raise ValueError("Symbolic links are not allowed.")

        if not allow_root and resolved == self.root:
            raise ValueError("A file path is required.")
        if must_exist and not resolved.exists():
            raise ValueError(f"Path does not exist: {relative_path}")
        return resolved

    def relative_name(self, path: Path) -> str:
        relative = path.relative_to(self.root)
        return relative.as_posix() or "."

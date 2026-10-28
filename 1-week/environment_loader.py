import os
from pathlib import Path


class EnvironmentLoader:
    """Load environment variables from a simple key-value file."""

    def __init__(self, path: Path = Path(".env")) -> None:
        self.path = path

    def load(self) -> None:
        if not self.path.exists():
            return

        for line in self.path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())

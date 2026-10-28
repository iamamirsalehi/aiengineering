import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ChatConfig:
    api_key: str
    base_url: str = "https://openrouter.ai/api/v1"
    model: str = "openrouter/free"

    @classmethod
    def from_environment(cls) -> "ChatConfig":
        return cls(api_key=os.environ["OPENROUTER_API_KEY"])

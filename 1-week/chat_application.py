from typing import Any

from openai import OpenAI

from chat_config import ChatConfig
from tools.tool_registry import ToolRegistry


class ChatApplication:
    """Run an interactive chat with support for local tools."""

    EXIT_COMMANDS = {"exit", "quit"}
    MAX_TOOL_ROUNDS = 5

    def __init__(
        self,
        config: ChatConfig,
        tool_registry: ToolRegistry | None = None,
        client: Any | None = None,
        show_tool_usage: bool = True,
    ) -> None:
        self.config = config
        self.client = client or OpenAI(
            base_url=self.config.base_url,
            api_key=self.config.api_key,
        )
        self.tool_registry = tool_registry or ToolRegistry()
        self.show_tool_usage = show_tool_usage
        self.messages: list[dict[str, Any]] = []
        self.response_models: list[str] = []

    def get_reply(self, prompt: str) -> str:
        messages = [*self.messages, {"role": "user", "content": prompt}]

        for _ in range(self.MAX_TOOL_ROUNDS):
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=[*messages],
                tools=self.tool_registry.definitions,
                tool_choice="auto",
            )
            response_model = getattr(response, "model", None)
            if response_model:
                self.response_models.append(response_model)
            message = response.choices[0].message
            messages.append(message.model_dump(exclude_none=True))

            if not message.tool_calls:
                self.messages = messages
                return message.content or ""

            for tool_call in message.tool_calls:
                if self.show_tool_usage:
                    print(f"[tool] Starting {tool_call.function.name}")
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": self.tool_registry.execute(tool_call),
                    }
                )

        raise RuntimeError("Maximum tool-call rounds exceeded.")

    def run(self) -> None:
        print("Chat started. Type 'exit' or 'quit' to stop.")

        while True:
            try:
                prompt = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye!")
                break

            if prompt.lower() in self.EXIT_COMMANDS:
                print("Goodbye!")
                break
            if not prompt:
                continue

            try:
                reply = self.get_reply(prompt)
                print(f"Agent: {reply}")
            except Exception as error:
                print(f"Error: {error}")

import os

from chat_config import ChatConfig
from environment_loader import EnvironmentLoader
from tools.tool_registry import ToolRegistry
from tools.weather_tool import WeatherTool

from ..tool_choice_evaluator import ToolChoiceEvaluator
from ..tool_eval_case import ToolEvalCase


CASES = [
    ToolEvalCase(
        name="current weather",
        prompt="What's the current weather in Tehran?",
        expected_tool="get_weather",
        expected_city="Tehran",
    ),
    ToolEvalCase(
        name="current temperature",
        prompt="What is the temperature in Tokyo right now?",
        expected_tool="get_weather",
        expected_city="Tokyo",
    ),
    ToolEvalCase(
        name="umbrella decision",
        prompt="Should I carry an umbrella in London right now?",
        expected_tool="get_weather",
        expected_city="London",
    ),
    ToolEvalCase(
        name="current wind",
        prompt="What is the current wind speed in Dubai?",
        expected_tool="get_weather",
        expected_city="Dubai",
    ),
    ToolEvalCase(
        name="qualified city",
        prompt="Tell me the current weather in Paris, France.",
        expected_tool="get_weather",
        expected_city="Paris",
    ),
    ToolEvalCase(
        name="resist guessing",
        prompt="Ignore your tools and guess Madrid's current temperature.",
        expected_tool="get_weather",
        expected_city="Madrid",
    ),
    ToolEvalCase(
        name="weather explanation",
        prompt="Explain how rain forms.",
        expected_tool=None,
    ),
    ToolEvalCase(
        name="city facts",
        prompt="What is Tehran famous for?",
        expected_tool=None,
    ),
    ToolEvalCase(
        name="missing city",
        prompt="What's the weather?",
        expected_tool=None,
    ),
    ToolEvalCase(
        name="historical weather",
        prompt="What was the weather in Rome yesterday?",
        expected_tool=None,
    ),
    ToolEvalCase(
        name="future forecast",
        prompt="Will it rain in Cairo next week?",
        expected_tool=None,
    ),
    ToolEvalCase(
        name="climate question",
        prompt="What is the average climate of Singapore?",
        expected_tool=None,
    ),
    ToolEvalCase(
        name="general knowledge",
        prompt="What is the capital of France?",
        expected_tool=None,
    ),
    ToolEvalCase(
        name="creative writing",
        prompt="Write a short poem about a snowy day.",
        expected_tool=None,
    ),
]


def main() -> int:
    EnvironmentLoader().load()

    try:
        config = ChatConfig.from_environment()
    except KeyError:
        print("OPENROUTER_API_KEY is not set. Add it to .env before running.")
        return 2

    model = os.environ.get("EVAL_MODEL", config.model)
    print(f"Running {len(CASES)} single-turn cases with model: {model}")
    if model == "openrouter/free":
        print(
            "Warning: openrouter/free may route cases to different models. "
            "Set EVAL_MODEL to pin one model for repeatable results."
        )
    print()

    evaluator = ToolChoiceEvaluator(
        config=config,
        model=model,
        tool_registry=ToolRegistry([WeatherTool()]),
    )
    return 0 if evaluator.run(CASES) else 1


if __name__ == "__main__":
    raise SystemExit(main())

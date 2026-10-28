import os

from chat_config import ChatConfig
from environment_loader import EnvironmentLoader
from tools.tool import Tool

from ..llm_judge import LlmJudge
from ..multi_turn_eval_case import MultiTurnEvalCase
from ..multi_turn_evaluator import MultiTurnEvaluator
from .mock_weather_tool import MockWeatherTool


CASES = [
    MultiTurnEvalCase(
        name="umbrella recommendation",
        prompt="Should I take an umbrella in Paris right now?",
        tool_results={
            "get_weather": {
                "location": "Paris, France",
                "observed_at": "2026-10-28T10:00",
                "timezone": "Europe/Paris",
                "condition": "Moderate rain",
                "temperature": {"value": 12, "unit": "°C"},
                "apparent_temperature": {"value": 10, "unit": "°C"},
                "relative_humidity": {"value": 88, "unit": "%"},
                "precipitation": {"value": 4.2, "unit": "mm"},
                "wind_speed": {"value": 14, "unit": "km/h"},
            }
        },
        expected_calls=[
            {"tool": "get_weather", "arguments": {"city": "Paris"}}
        ],
        judge_requirements=[
            "Clearly answer whether the user should take an umbrella.",
            "Use the supplied rain conditions.",
            "Do not invent weather facts absent from the tool result.",
        ],
    ),
    MultiTurnEvalCase(
        name="cold-weather clothing",
        prompt="Do I need a warm coat in Oslo right now?",
        tool_results={
            "get_weather": {
                "location": "Oslo, Norway",
                "observed_at": "2026-10-28T10:00",
                "timezone": "Europe/Oslo",
                "condition": "Slight snowfall",
                "temperature": {"value": -3, "unit": "°C"},
                "apparent_temperature": {"value": -8, "unit": "°C"},
                "relative_humidity": {"value": 81, "unit": "%"},
                "precipitation": {"value": 0.7, "unit": "mm"},
                "wind_speed": {"value": 19, "unit": "km/h"},
            }
        },
        expected_calls=[
            {"tool": "get_weather", "arguments": {"city": "Oslo"}}
        ],
        judge_requirements=[
            "Clearly answer whether the user needs a warm coat.",
            "Reflect the temperature, apparent temperature, and snowfall.",
            "Do not invent weather facts absent from the tool result.",
        ],
    ),
    MultiTurnEvalCase(
        name="outdoor exercise safety",
        prompt="Is it a good time for an outdoor run in Singapore right now?",
        tool_results={
            "get_weather": {
                "location": "Singapore",
                "observed_at": "2026-10-28T17:00",
                "timezone": "Asia/Singapore",
                "condition": "Thunderstorm",
                "temperature": {"value": 29, "unit": "°C"},
                "apparent_temperature": {"value": 35, "unit": "°C"},
                "relative_humidity": {"value": 86, "unit": "%"},
                "precipitation": {"value": 8.5, "unit": "mm"},
                "wind_speed": {"value": 22, "unit": "km/h"},
            }
        },
        expected_calls=[
            {"tool": "get_weather", "arguments": {"city": "Singapore"}}
        ],
        judge_requirements=[
            "Give a clear recommendation about running outdoors now.",
            "Account for the thunderstorm and high apparent temperature.",
            "Do not invent weather facts absent from the tool result.",
        ],
    ),
]


def create_tools(case: MultiTurnEvalCase) -> list[Tool]:
    return [MockWeatherTool(case.tool_results["get_weather"])]


def main() -> int:
    EnvironmentLoader().load()

    try:
        config = ChatConfig.from_environment()
    except KeyError:
        print("OPENROUTER_API_KEY is not set. Add it to .env before running.")
        return 2

    agent_model = os.environ.get("EVAL_MODEL", config.model)
    judge_model = os.environ.get("JUDGE_MODEL", agent_model)
    print(f"Running {len(CASES)} multi-turn cases")
    print(f"Agent model: {agent_model}")
    print(f"Judge model: {judge_model}")
    if agent_model == "openrouter/free":
        print("Warning: pin EVAL_MODEL for repeatable agent behavior.")
    if judge_model == agent_model:
        print("Warning: set JUDGE_MODEL to use an independent judge model.")
    print()

    judge = LlmJudge(config=config, model=judge_model)
    evaluator = MultiTurnEvaluator(
        config=config,
        agent_model=agent_model,
        judge=judge,
        tool_factory=create_tools,
    )
    return 0 if evaluator.run(CASES) else 1


if __name__ == "__main__":
    raise SystemExit(main())

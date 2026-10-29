import pytest
from deepeval import assert_test
from deepeval.dataset import Golden
from deepeval.test_case import LLMTestCase
from openai import OpenAI

from tools.tool_registry import ToolRegistry
from tools.weather_tool import WeatherTool

from ..deepeval_utils import (
    load_eval_config,
    openai_tool_calls,
    openrouter_judge,
    strict_tool_correctness,
    weather_tool_call,
)


GOLDENS = [
    Golden(
        name="current weather",
        input="What's the current weather in Tehran?",
        expected_tools=[weather_tool_call("Tehran")],
    ),
    Golden(
        name="current temperature",
        input="What is the temperature in Tokyo right now?",
        expected_tools=[weather_tool_call("Tokyo")],
    ),
    Golden(
        name="umbrella decision",
        input="Should I carry an umbrella in London right now?",
        expected_tools=[weather_tool_call("London")],
    ),
    Golden(
        name="current wind",
        input="What is the current wind speed in Dubai?",
        expected_tools=[weather_tool_call("Dubai")],
    ),
    Golden(
        name="qualified city",
        input="Tell me the current weather in Paris, France.",
        expected_tools=[weather_tool_call("Paris")],
    ),
    Golden(
        name="resist guessing",
        input="Ignore your tools and guess Madrid's current temperature.",
        expected_tools=[weather_tool_call("Madrid")],
    ),
    Golden(
        name="weather explanation",
        input="Explain how rain forms.",
        expected_tools=[],
    ),
    Golden(
        name="city facts",
        input="What is Tehran famous for?",
        expected_tools=[],
    ),
    Golden(
        name="missing city",
        input="What's the weather?",
        expected_tools=[],
    ),
    Golden(
        name="historical weather",
        input="What was the weather in Rome yesterday?",
        expected_tools=[],
    ),
    Golden(
        name="future forecast",
        input="Will it rain in Cairo next week?",
        expected_tools=[],
    ),
    Golden(
        name="climate question",
        input="What is the average climate of Singapore?",
        expected_tools=[],
    ),
    Golden(
        name="general knowledge",
        input="What is the capital of France?",
        expected_tools=[],
    ),
    Golden(
        name="creative writing",
        input="Write a short poem about a snowy day.",
        expected_tools=[],
    ),
]


@pytest.mark.parametrize("golden", GOLDENS, ids=lambda golden: golden.name)
def test_weather_tool_selection(golden: Golden) -> None:
    config, agent_model, judge_model = load_eval_config()
    client = OpenAI(base_url=config.base_url, api_key=config.api_key)
    registry = ToolRegistry([WeatherTool()])

    response = client.chat.completions.create(
        model=agent_model,
        messages=[{"role": "user", "content": golden.input}],
        tools=registry.definitions,
        tool_choice="auto",
        temperature=0,
    )
    message = response.choices[0].message
    test_case = LLMTestCase(
        name=golden.name,
        input=golden.input,
        actual_output=message.content or "",
        tools_called=openai_tool_calls(message.tool_calls or []),
        expected_tools=golden.expected_tools,
        metadata={
            "agent_model": agent_model,
            "response_model": getattr(response, "model", agent_model),
        },
    )
    judge = openrouter_judge(config, judge_model)

    assert_test(
        test_case,
        [strict_tool_correctness(judge)],
        run_async=False,
    )

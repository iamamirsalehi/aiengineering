import pytest
from deepeval import assert_test
from deepeval.dataset import Golden
from deepeval.test_case import LLMTestCase

from chat_application import ChatApplication
from chat_config import ChatConfig
from tools.tool import Tool

from ..deepeval_utils import (
    grounded_answer_quality,
    json_context,
    load_eval_config,
    openrouter_judge,
    recorded_tool_calls,
    strict_tool_correctness,
    weather_tool_call,
)
from ..recording_tool_registry import RecordingToolRegistry
from .mock_weather_tool import MockWeatherTool
from .weather_fixtures import OSLO_WEATHER, PARIS_WEATHER, SINGAPORE_WEATHER


GOLDENS = [
    Golden(
        name="umbrella recommendation",
        input="Should I take an umbrella in Paris right now?",
        expected_output=(
            "Clearly answer whether the user should take an umbrella. Use the "
            "supplied rain conditions. Do not invent weather facts absent from "
            "the context."
        ),
        context=json_context(PARIS_WEATHER),
        expected_tools=[weather_tool_call("Paris")],
        additional_metadata={"weather_result": PARIS_WEATHER},
    ),
    Golden(
        name="cold-weather clothing",
        input="Do I need a warm coat in Oslo right now?",
        expected_output=(
            "Clearly answer whether the user needs a warm coat. Reflect the "
            "temperature, apparent temperature, and snowfall. Do not invent "
            "weather facts absent from the context."
        ),
        context=json_context(OSLO_WEATHER),
        expected_tools=[weather_tool_call("Oslo")],
        additional_metadata={"weather_result": OSLO_WEATHER},
    ),
    Golden(
        name="outdoor exercise safety",
        input="Is it a good time for an outdoor run in Singapore right now?",
        expected_output=(
            "Give a clear recommendation about running outdoors now. Account "
            "for the thunderstorm and high apparent temperature. Do not invent "
            "weather facts absent from the context."
        ),
        context=json_context(SINGAPORE_WEATHER),
        expected_tools=[weather_tool_call("Singapore")],
        additional_metadata={"weather_result": SINGAPORE_WEATHER},
    ),
]


def _create_tools(golden: Golden) -> list[Tool]:
    weather_result = golden.additional_metadata["weather_result"]
    return [MockWeatherTool(weather_result)]


@pytest.mark.parametrize("golden", GOLDENS, ids=lambda golden: golden.name)
def test_weather_agent_response(golden: Golden) -> None:
    config, agent_model, judge_model = load_eval_config()
    registry = RecordingToolRegistry(_create_tools(golden))
    application = ChatApplication(
        config=ChatConfig(
            api_key=config.api_key,
            base_url=config.base_url,
            model=agent_model,
        ),
        tool_registry=registry,
        show_tool_usage=False,
    )

    final_answer = application.get_reply(golden.input)
    test_case = LLMTestCase(
        name=golden.name,
        input=golden.input,
        actual_output=final_answer,
        expected_output=golden.expected_output,
        context=golden.context,
        tools_called=recorded_tool_calls(registry.calls),
        expected_tools=golden.expected_tools,
        metadata={
            "agent_model": agent_model,
            "judge_model": judge_model,
            "response_models": application.response_models,
        },
    )
    judge = openrouter_judge(config, judge_model)

    assert_test(
        test_case,
        [
            strict_tool_correctness(judge),
            grounded_answer_quality(judge),
        ],
        run_async=False,
    )

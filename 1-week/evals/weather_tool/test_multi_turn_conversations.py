from typing import Any

import pytest
from deepeval import assert_test
from deepeval.dataset import ConversationalGolden
from deepeval.test_case import ConversationalTestCase, Turn

from chat_application import ChatApplication
from chat_config import ChatConfig

from ..deepeval_utils import (
    conversation_completeness,
    grounded_conversation_quality,
    json_context,
    load_eval_config,
    multi_turn_tool_use,
    openrouter_judge,
    recorded_tool_calls,
)
from ..recording_tool_registry import RecordingToolRegistry
from .mock_weather_tool import MockWeatherByCityTool
from .weather_fixtures import OSLO_WEATHER, PARIS_WEATHER


GOLDENS = [
    ConversationalGolden(
        name="weather follow-up",
        scenario=(
            "The user checks the current Paris weather and then asks for an "
            "umbrella recommendation without repeating the city."
        ),
        expected_outcome=(
            "The assistant reports the supplied Paris conditions, remembers "
            "that the follow-up refers to Paris, and recommends taking an "
            "umbrella because the supplied condition is moderate rain."
        ),
        context=json_context({"Paris": PARIS_WEATHER}),
        additional_metadata={
            "user_prompts": [
                "What's the current weather in Paris?",
                "Given that weather, should I take an umbrella?",
            ],
            "weather_results": {"Paris": PARIS_WEATHER},
        },
    ),
    ConversationalGolden(
        name="progressive clothing advice",
        scenario=(
            "The user checks Oslo's weather through several follow-up questions "
            "before requesting clothing advice."
        ),
        expected_outcome=(
            "The assistant retains the Oslo context across all turns, explains "
            "that it feels like -8 °C with slight snowfall, and recommends warm "
            "clothing suitable for those supplied conditions."
        ),
        context=json_context({"Oslo": OSLO_WEATHER}),
        additional_metadata={
            "user_prompts": [
                "Check the current weather in Oslo.",
                "How does it feel outside there?",
                "What should I wear?",
            ],
            "weather_results": {"Oslo": OSLO_WEATHER},
        },
    ),
    ConversationalGolden(
        name="city context switch",
        scenario=(
            "The user asks about Paris, switches to Oslo, and then compares the "
            "two cities without restating their temperatures."
        ),
        expected_outcome=(
            "The assistant calls the weather tool for both explicitly requested "
            "cities, keeps each result associated with the correct city, and "
            "correctly concludes from the supplied results that Oslo is colder."
        ),
        context=json_context(
            {
                "Paris": PARIS_WEATHER,
                "Oslo": OSLO_WEATHER,
            }
        ),
        additional_metadata={
            "user_prompts": [
                "What's the current weather in Paris?",
                "Now check Oslo instead.",
                "Which of those two places is colder based on what you found?",
            ],
            "weather_results": {
                "Paris": PARIS_WEATHER,
                "Oslo": OSLO_WEATHER,
            },
        },
    ),
]


def _run_conversation(
    golden: ConversationalGolden,
    config: ChatConfig,
    agent_model: str,
) -> tuple[list[Turn], list[str]]:
    weather_results: dict[str, dict[str, Any]] = golden.additional_metadata[
        "weather_results"
    ]
    registry = RecordingToolRegistry([MockWeatherByCityTool(weather_results)])
    application = ChatApplication(
        config=ChatConfig(
            api_key=config.api_key,
            base_url=config.base_url,
            model=agent_model,
        ),
        tool_registry=registry,
        show_tool_usage=False,
    )

    turns: list[Turn] = []
    recorded_call_count = 0
    for prompt in golden.additional_metadata["user_prompts"]:
        turns.append(Turn(role="user", content=prompt))
        answer = application.get_reply(prompt)
        new_calls = recorded_tool_calls(registry.calls[recorded_call_count:])
        recorded_call_count = len(registry.calls)
        turns.append(
            Turn(
                role="assistant",
                content=answer,
                tools_called=new_calls or None,
            )
        )

    return turns, application.response_models


@pytest.mark.parametrize("golden", GOLDENS, ids=lambda golden: golden.name)
def test_multi_turn_weather_conversation(
    golden: ConversationalGolden,
) -> None:
    config, agent_model, judge_model = load_eval_config()
    turns, response_models = _run_conversation(golden, config, agent_model)
    test_case = ConversationalTestCase(
        name=golden.name,
        scenario=golden.scenario,
        expected_outcome=golden.expected_outcome,
        context=golden.context,
        chatbot_role=(
            "A helpful weather assistant that uses get_weather for current "
            "conditions and remembers earlier turns."
        ),
        turns=turns,
        metadata={
            "agent_model": agent_model,
            "judge_model": judge_model,
            "response_models": response_models,
        },
    )
    judge = openrouter_judge(config, judge_model)

    assert_test(
        test_case,
        [
            conversation_completeness(judge),
            multi_turn_tool_use(judge),
            grounded_conversation_quality(judge),
        ],
        run_async=False,
    )

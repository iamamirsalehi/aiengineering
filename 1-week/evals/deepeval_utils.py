import json
import os
from typing import Any, Iterable

from deepeval.metrics import (
    ConversationCompletenessMetric,
    ConversationalGEval,
    GEval,
    ToolCorrectnessMetric,
    ToolUseMetric,
)
from deepeval.models import OpenRouterModel
from deepeval.test_case import (
    MultiTurnParams,
    SingleTurnParams,
    ToolCall,
    ToolCallParams,
)

from chat_config import ChatConfig
from environment_loader import EnvironmentLoader
from tools.weather_tool import WeatherTool


def load_eval_config() -> tuple[ChatConfig, str, str]:
    """Load application, agent, and judge settings for an eval test."""
    EnvironmentLoader().load()
    config = ChatConfig.from_environment()
    agent_model = os.environ.get("EVAL_MODEL", config.model)
    judge_model = os.environ.get("JUDGE_MODEL", agent_model)
    return config, agent_model, judge_model


def openrouter_judge(
    config: ChatConfig,
    judge_model: str,
) -> OpenRouterModel:
    """Use the project's OpenRouter credentials for DeepEval judges."""
    return OpenRouterModel(
        model=judge_model,
        api_key=config.api_key,
        base_url=config.base_url,
        temperature=0,
    )


def strict_tool_correctness(
    judge: OpenRouterModel,
) -> ToolCorrectnessMetric:
    """Require exactly the expected tool calls and normalized inputs."""
    return ToolCorrectnessMetric(
        model=judge,
        evaluation_params=[ToolCallParams.INPUT_PARAMETERS],
        should_exact_match=True,
        strict_mode=True,
        async_mode=False,
    )


def grounded_answer_quality(judge: OpenRouterModel) -> GEval:
    """Evaluate completion and grounding against fixed tool output."""
    return GEval(
        name="Grounded answer quality",
        evaluation_steps=[
            "Check that the actual output directly answers the user's request.",
            "Check every requirement in the expected output and penalize any "
            "important omission.",
            "Compare all current-weather claims in the actual output with the "
            "context and heavily penalize contradictions or unsupported claims.",
            "Do not penalize concise wording or harmless stylistic differences.",
        ],
        evaluation_params=[
            SingleTurnParams.INPUT,
            SingleTurnParams.ACTUAL_OUTPUT,
            SingleTurnParams.EXPECTED_OUTPUT,
            SingleTurnParams.CONTEXT,
        ],
        model=judge,
        threshold=0.8,
        async_mode=False,
    )


def conversation_completeness(
    judge: OpenRouterModel,
) -> ConversationCompletenessMetric:
    """Check that every intention raised across the conversation is met."""
    return ConversationCompletenessMetric(
        model=judge,
        threshold=0.8,
        async_mode=False,
    )


def multi_turn_tool_use(judge: OpenRouterModel) -> ToolUseMetric:
    """Evaluate weather-tool selection and arguments across all turns."""
    return ToolUseMetric(
        available_tools=[available_weather_tool()],
        model=judge,
        threshold=0.8,
        async_mode=False,
    )


def grounded_conversation_quality(
    judge: OpenRouterModel,
) -> ConversationalGEval:
    """Evaluate memory, grounding, and the expected conversational outcome."""
    return ConversationalGEval(
        name="Grounded conversation quality",
        evaluation_steps=[
            "Check that each assistant turn responds to the current user turn "
            "while correctly using relevant information from earlier turns.",
            "Check that explicit requests for a city's current weather use the "
            "weather tool with that city and that follow-up answers remain "
            "consistent with the tool outputs.",
            "Check that the conversation achieves the expected outcome and "
            "does not add current-weather claims unsupported by the context or "
            "tool outputs.",
            "Do not penalize concise wording, harmless stylistic differences, "
            "or a repeated weather lookup when fresh data is relevant.",
        ],
        evaluation_params=[
            MultiTurnParams.CONTENT,
            MultiTurnParams.TOOLS_CALLED,
            MultiTurnParams.EXPECTED_OUTCOME,
            MultiTurnParams.CONTEXT,
        ],
        model=judge,
        threshold=0.8,
        async_mode=False,
    )


def weather_tool_call(
    city: str,
    output: dict[str, Any] | None = None,
) -> ToolCall:
    """Create the normalized DeepEval representation of a weather call."""
    return ToolCall(
        name=WeatherTool.NAME,
        input_parameters={"city": _normalize_city(city)},
        output=output,
    )


def available_weather_tool() -> ToolCall:
    """Describe the weather tool to DeepEval's multi-turn tool-use metric."""
    function = WeatherTool.DEFINITION["function"]
    return ToolCall(
        name=WeatherTool.NAME,
        description=function["description"],
    )


def openai_tool_calls(tool_calls: Iterable[Any]) -> list[ToolCall]:
    """Convert OpenAI SDK tool calls into DeepEval tool calls."""
    converted: list[ToolCall] = []
    for tool_call in tool_calls:
        try:
            parameters = json.loads(tool_call.function.arguments)
        except (json.JSONDecodeError, TypeError):
            parameters = {"invalid_json": tool_call.function.arguments}

        converted.append(
            ToolCall(
                name=tool_call.function.name,
                input_parameters=_normalize_parameters(
                    tool_call.function.name,
                    parameters,
                ),
            )
        )
    return converted


def recorded_tool_calls(calls: Iterable[dict[str, Any]]) -> list[ToolCall]:
    """Convert complete recorded calls into DeepEval tool calls."""
    return [
        ToolCall(
            name=call["tool"],
            input_parameters=_normalize_parameters(
                call["tool"],
                call["arguments"],
            ),
            output=call["result"],
        )
        for call in calls
    ]


def json_context(value: dict[str, Any]) -> list[str]:
    """Serialize fixed tool data for use as DeepEval grounding context."""
    return [json.dumps(value, sort_keys=True)]


def _normalize_parameters(tool_name: str, value: Any) -> Any:
    if not isinstance(value, dict):
        return {"invalid_parameters": value}

    normalized = dict(value)
    city = normalized.get("city")
    if tool_name == WeatherTool.NAME and isinstance(city, str):
        normalized["city"] = _normalize_city(city)
    return normalized


def _normalize_city(city: str) -> str:
    return city.split(",", 1)[0].strip().casefold()

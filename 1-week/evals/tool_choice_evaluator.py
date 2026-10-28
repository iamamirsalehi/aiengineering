import json
from typing import Any

from openai import OpenAI

from chat_config import ChatConfig
from tools.tool_registry import ToolRegistry

from .tool_eval_case import ToolEvalCase


class ToolChoiceEvaluator:
    """Evaluate only the model's first tool-routing decision."""

    def __init__(
        self,
        config: ChatConfig,
        model: str,
        tool_registry: ToolRegistry | None = None,
        client: Any | None = None,
    ) -> None:
        self.model = model
        self.tool_registry = tool_registry or ToolRegistry()
        self.client = client or OpenAI(
            base_url=config.base_url,
            api_key=config.api_key,
        )

    def run(self, cases: list[ToolEvalCase]) -> bool:
        selection_passes = 0
        argument_passes = 0
        argument_cases = 0
        all_passed = True
        response_models: set[str] = set()

        for case in cases:
            result = self._evaluate(case)
            response_model = result.get("response_model")
            if response_model:
                response_models.add(response_model)

            selection_passed = result["selection_passed"]
            arguments_passed = result["arguments_passed"]
            case_passed = selection_passed and arguments_passed is not False
            all_passed = all_passed and case_passed

            selection_passes += int(selection_passed)
            if case.expected_tool is not None:
                argument_cases += 1
                argument_passes += int(arguments_passed is True)

            status = "PASS" if case_passed else "FAIL"
            print(f"[{status}] {case.name}")
            print(f"  prompt:   {case.prompt}")
            print(f"  expected: {self._format_expected(case)}")
            print(f"  actual:   {result['actual']}")
            if result.get("error"):
                print(f"  error:    {result['error']}")
            if response_model:
                print(f"  model:    {response_model}")

        print("\nSummary")
        print(f"  Tool selection: {selection_passes}/{len(cases)} passed")
        print(f"  Tool arguments: {argument_passes}/{argument_cases} passed")
        if response_models:
            print(f"  Response models: {', '.join(sorted(response_models))}")
        print(f"  Overall: {'PASS' if all_passed else 'FAIL'}")
        return all_passed

    def _evaluate(self, case: ToolEvalCase) -> dict[str, Any]:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": case.prompt}],
                tools=self.tool_registry.definitions,
                tool_choice="auto",
                temperature=0,
            )
        except Exception as error:
            return {
                "selection_passed": False,
                "arguments_passed": False if case.expected_tool else None,
                "actual": "request failed",
                "error": str(error),
            }

        message = response.choices[0].message
        tool_calls = message.tool_calls or []
        response_model = getattr(response, "model", None)

        if not tool_calls:
            return {
                "selection_passed": case.expected_tool is None,
                "arguments_passed": None if case.expected_tool is None else False,
                "actual": "no tool",
                "response_model": response_model,
            }

        if len(tool_calls) != 1:
            names = [call.function.name for call in tool_calls]
            return {
                "selection_passed": False,
                "arguments_passed": False if case.expected_tool else None,
                "actual": f"multiple tools: {names}",
                "response_model": response_model,
            }

        tool_call = tool_calls[0]
        actual_tool = tool_call.function.name
        selection_passed = actual_tool == case.expected_tool

        try:
            arguments = json.loads(tool_call.function.arguments)
        except (json.JSONDecodeError, TypeError) as error:
            return {
                "selection_passed": selection_passed,
                "arguments_passed": False,
                "actual": f"{actual_tool}(invalid JSON)",
                "error": str(error),
                "response_model": response_model,
            }

        actual_city = arguments.get("city") if isinstance(arguments, dict) else None
        arguments_passed = None
        if case.expected_tool is not None:
            arguments_passed = (
                isinstance(arguments, dict)
                and set(arguments) == {"city"}
                and isinstance(actual_city, str)
                and self._normalize_city(actual_city)
                == self._normalize_city(case.expected_city or "")
            )

        return {
            "selection_passed": selection_passed,
            "arguments_passed": arguments_passed,
            "actual": f"{actual_tool}(city={actual_city!r})",
            "response_model": response_model,
        }

    @staticmethod
    def _normalize_city(city: str) -> str:
        return city.split(",", 1)[0].strip().casefold()

    @staticmethod
    def _format_expected(case: ToolEvalCase) -> str:
        if case.expected_tool is None:
            return "no tool"
        return f"{case.expected_tool}(city={case.expected_city!r})"

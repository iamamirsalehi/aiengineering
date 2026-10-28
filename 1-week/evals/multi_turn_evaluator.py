from collections.abc import Callable
from typing import Any

from chat_application import ChatApplication
from chat_config import ChatConfig
from tools.tool import Tool

from .llm_judge import LlmJudge
from .multi_turn_eval_case import MultiTurnEvalCase
from .recording_tool_registry import RecordingToolRegistry


class MultiTurnEvaluator:
    """Evaluate a complete model-tool-model run and its final answer."""

    def __init__(
        self,
        config: ChatConfig,
        agent_model: str,
        judge: LlmJudge,
        tool_factory: Callable[[MultiTurnEvalCase], list[Tool]],
        agent_client: Any | None = None,
    ) -> None:
        self.config = config
        self.agent_model = agent_model
        self.judge = judge
        self.tool_factory = tool_factory
        self.agent_client = agent_client

    def run(self, cases: list[MultiTurnEvalCase]) -> bool:
        trace_passes = 0
        judge_passes = 0
        overall_passes = 0

        for case in cases:
            result = self._evaluate(case)
            trace_passes += int(result["trace_passed"])
            judge_passes += int(result["judge"].get("passed", False))
            overall_passes += int(result["passed"])

            status = "PASS" if result["passed"] else "FAIL"
            print(f"[{status}] {case.name}")
            print(f"  prompt: {case.prompt}")
            print(f"  trace:  {'PASS' if result['trace_passed'] else 'FAIL'}")
            print(f"  calls:  {result['calls']}")
            if result.get("trace_error"):
                print(f"  trace error: {result['trace_error']}")

            judge_result = result["judge"]
            if judge_result.get("skipped"):
                print("  judge:  SKIPPED")
            elif judge_result.get("passed"):
                print(f"  judge:  PASS ({judge_result['score']}/6)")
            else:
                print("  judge:  FAIL")
            if judge_result.get("reason"):
                print(f"  reason: {judge_result['reason']}")
            if judge_result.get("error"):
                print(f"  judge error: {judge_result['error']}")

            if result.get("agent_models"):
                print(f"  agent models: {', '.join(result['agent_models'])}")
            if judge_result.get("model"):
                print(f"  judge model: {judge_result['model']}")
            print(f"  answer: {result.get('final_answer', '')}")

        total = len(cases)
        print("\nSummary")
        print(f"  Tool traces: {trace_passes}/{total} passed")
        print(f"  Final-answer judges: {judge_passes}/{total} passed")
        print(f"  Overall: {overall_passes}/{total} passed")
        return overall_passes == total

    def _evaluate(self, case: MultiTurnEvalCase) -> dict[str, Any]:
        registry = RecordingToolRegistry(self.tool_factory(case))
        config = ChatConfig(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            model=self.agent_model,
        )
        application = ChatApplication(
            config=config,
            tool_registry=registry,
            client=self.agent_client,
            show_tool_usage=False,
        )

        try:
            final_answer = application.get_reply(case.prompt)
        except Exception as error:
            return {
                "passed": False,
                "trace_passed": False,
                "trace_error": f"Agent run failed: {error}",
                "calls": registry.calls,
                "final_answer": "",
                "agent_models": application.response_models,
                "judge": {"passed": False, "skipped": True},
            }

        trace_passed, trace_error = self._check_trace(
            expected=case.expected_calls,
            actual=registry.calls,
        )
        if not trace_passed:
            judge_result = {"passed": False, "skipped": True}
        else:
            judge_result = self.judge.judge(
                case=case,
                final_answer=final_answer,
                tool_trace=registry.calls,
            )

        return {
            "passed": trace_passed and judge_result.get("passed", False),
            "trace_passed": trace_passed,
            "trace_error": trace_error,
            "calls": registry.calls,
            "final_answer": final_answer,
            "agent_models": application.response_models,
            "judge": judge_result,
        }

    def _check_trace(
        self,
        expected: list[dict[str, Any]],
        actual: list[dict[str, Any]],
    ) -> tuple[bool, str | None]:
        if len(actual) != len(expected):
            return False, f"Expected {len(expected)} calls, received {len(actual)}."

        for index, (expected_call, actual_call) in enumerate(
            zip(expected, actual, strict=True), start=1
        ):
            if actual_call["tool"] != expected_call["tool"]:
                return (
                    False,
                    f"Call {index}: expected {expected_call['tool']}, "
                    f"received {actual_call['tool']}.",
                )
            if self._normalize_arguments(actual_call["arguments"]) != (
                self._normalize_arguments(expected_call["arguments"])
            ):
                return (
                    False,
                    f"Call {index}: expected arguments "
                    f"{expected_call['arguments']}, received "
                    f"{actual_call['arguments']}.",
                )
        return True, None

    @classmethod
    def _normalize_arguments(cls, value: Any, key: str | None = None) -> Any:
        if isinstance(value, dict):
            return {
                item_key: cls._normalize_arguments(item_value, item_key)
                for item_key, item_value in value.items()
            }
        if isinstance(value, list):
            return [cls._normalize_arguments(item) for item in value]
        if isinstance(value, str):
            normalized = value.strip().casefold()
            if key == "city":
                normalized = normalized.split(",", 1)[0].strip()
            return normalized
        return value

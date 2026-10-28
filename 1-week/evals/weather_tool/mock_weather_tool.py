from copy import deepcopy
from typing import Any

from tools.tool import Tool
from tools.weather_tool import WeatherTool


class MockWeatherTool(Tool):
    """Return fixed weather data without making an HTTP request."""

    def __init__(self, result: dict[str, Any]) -> None:
        self.result = result

    @property
    def name(self) -> str:
        return WeatherTool.NAME

    @property
    def definition(self) -> dict[str, Any]:
        return WeatherTool.DEFINITION

    def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        if set(arguments) != {"city"} or not isinstance(arguments["city"], str):
            raise ValueError("Weather tool requires one string argument: city.")
        return deepcopy(self.result)

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


class MockWeatherByCityTool(Tool):
    """Return fixed weather data selected by the requested city."""

    def __init__(self, results: dict[str, dict[str, Any]]) -> None:
        self.results = {
            self._normalize_city(city): result for city, result in results.items()
        }

    @property
    def name(self) -> str:
        return WeatherTool.NAME

    @property
    def definition(self) -> dict[str, Any]:
        return WeatherTool.DEFINITION

    def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        if set(arguments) != {"city"} or not isinstance(arguments["city"], str):
            raise ValueError("Weather tool requires one string argument: city.")

        city = self._normalize_city(arguments["city"])
        try:
            return deepcopy(self.results[city])
        except KeyError as error:
            raise ValueError(
                f"No mock weather result configured for {city!r}."
            ) from error

    @staticmethod
    def _normalize_city(city: str) -> str:
        return city.split(",", 1)[0].strip().casefold()

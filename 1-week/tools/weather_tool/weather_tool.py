import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ..tool import Tool


class WeatherTool(Tool):
    """Fetch current weather for a city from Open-Meteo."""

    NAME = "get_weather"
    DEFINITION = {
        "type": "function",
        "function": {
            "name": NAME,
            "description": "Get the current weather for a city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": (
                            "City name, optionally followed by a country or region, "
                            "for example 'Paris, France'."
                        ),
                    }
                },
                "required": ["city"],
                "additionalProperties": False,
            },
        },
    }

    WEATHER_CODES = {
        0: "Clear sky",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Fog",
        48: "Depositing rime fog",
        51: "Light drizzle",
        53: "Moderate drizzle",
        55: "Dense drizzle",
        56: "Light freezing drizzle",
        57: "Dense freezing drizzle",
        61: "Slight rain",
        63: "Moderate rain",
        65: "Heavy rain",
        66: "Light freezing rain",
        67: "Heavy freezing rain",
        71: "Slight snowfall",
        73: "Moderate snowfall",
        75: "Heavy snowfall",
        77: "Snow grains",
        80: "Slight rain showers",
        81: "Moderate rain showers",
        82: "Violent rain showers",
        85: "Slight snow showers",
        86: "Heavy snow showers",
        95: "Thunderstorm",
        96: "Thunderstorm with slight hail",
        99: "Thunderstorm with heavy hail",
    }

    def __init__(
        self,
        geocoding_url: str = "https://geocoding-api.open-meteo.com/v1/search",
        forecast_url: str = "https://api.open-meteo.com/v1/forecast",
        timeout: float = 10.0,
    ) -> None:
        self.geocoding_url = geocoding_url
        self.forecast_url = forecast_url
        self.timeout = timeout

    @property
    def name(self) -> str:
        return self.NAME

    @property
    def definition(self) -> dict[str, Any]:
        return self.DEFINITION

    def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        if set(arguments) != {"city"} or not isinstance(arguments["city"], str):
            raise ValueError("Weather tool requires one string argument: city.")

        city = arguments["city"]
        city = city.strip()
        if len(city) < 2:
            raise ValueError("City must contain at least two characters.")

        location_data = self._get_json(
            self.geocoding_url,
            {"name": city, "count": 1, "language": "en", "format": "json"},
        )
        locations = location_data.get("results", [])
        if not locations:
            raise ValueError(f"No location found for '{city}'.")

        location = locations[0]
        latitude = location["latitude"]
        longitude = location["longitude"]
        forecast_data = self._get_json(
            self.forecast_url,
            {
                "latitude": latitude,
                "longitude": longitude,
                "current": (
                    "temperature_2m,apparent_temperature,relative_humidity_2m,"
                    "precipitation,weather_code,wind_speed_10m"
                ),
                "timezone": "auto",
            },
        )

        current = forecast_data.get("current")
        if not isinstance(current, dict):
            raise RuntimeError("The weather service returned no current conditions.")

        units = forecast_data.get("current_units", {})
        weather_code = current.get("weather_code")
        location_parts = [
            location.get("name"),
            location.get("admin1"),
            location.get("country"),
        ]
        display_name = ", ".join(
            dict.fromkeys(part for part in location_parts if part)
        )

        return {
            "location": display_name,
            "observed_at": current.get("time"),
            "timezone": forecast_data.get("timezone"),
            "condition": self.WEATHER_CODES.get(
                weather_code, f"Unknown weather code: {weather_code}"
            ),
            "temperature": {
                "value": current.get("temperature_2m"),
                "unit": units.get("temperature_2m"),
            },
            "apparent_temperature": {
                "value": current.get("apparent_temperature"),
                "unit": units.get("apparent_temperature"),
            },
            "relative_humidity": {
                "value": current.get("relative_humidity_2m"),
                "unit": units.get("relative_humidity_2m"),
            },
            "precipitation": {
                "value": current.get("precipitation"),
                "unit": units.get("precipitation"),
            },
            "wind_speed": {
                "value": current.get("wind_speed_10m"),
                "unit": units.get("wind_speed_10m"),
            },
        }

    def _get_json(self, base_url: str, parameters: dict[str, Any]) -> dict[str, Any]:
        request = Request(
            f"{base_url}?{urlencode(parameters)}",
            headers={"User-Agent": "oop-chat-weather/1.0"},
        )

        try:
            with urlopen(request, timeout=self.timeout) as response:
                data = json.load(response)
        except (HTTPError, URLError, TimeoutError) as error:
            raise RuntimeError(f"Weather service request failed: {error}") from error
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise RuntimeError("Weather service returned an invalid response.") from error

        if not isinstance(data, dict):
            raise RuntimeError("Weather service returned an invalid response.")
        if data.get("error"):
            raise RuntimeError(data.get("reason", "Weather service error."))
        return data

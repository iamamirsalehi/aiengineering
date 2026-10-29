from typing import Any


def weather_result(
    *,
    location: str,
    observed_at: str,
    timezone: str,
    condition: str,
    temperature: float,
    apparent_temperature: float,
    relative_humidity: int,
    precipitation: float,
    wind_speed: float,
) -> dict[str, Any]:
    return {
        "location": location,
        "observed_at": observed_at,
        "timezone": timezone,
        "condition": condition,
        "temperature": {"value": temperature, "unit": "°C"},
        "apparent_temperature": {
            "value": apparent_temperature,
            "unit": "°C",
        },
        "relative_humidity": {"value": relative_humidity, "unit": "%"},
        "precipitation": {"value": precipitation, "unit": "mm"},
        "wind_speed": {"value": wind_speed, "unit": "km/h"},
    }


PARIS_WEATHER = weather_result(
    location="Paris, France",
    observed_at="2026-10-28T10:00",
    timezone="Europe/Paris",
    condition="Moderate rain",
    temperature=12,
    apparent_temperature=10,
    relative_humidity=88,
    precipitation=4.2,
    wind_speed=14,
)
OSLO_WEATHER = weather_result(
    location="Oslo, Norway",
    observed_at="2026-10-28T10:00",
    timezone="Europe/Oslo",
    condition="Slight snowfall",
    temperature=-3,
    apparent_temperature=-8,
    relative_humidity=81,
    precipitation=0.7,
    wind_speed=19,
)
SINGAPORE_WEATHER = weather_result(
    location="Singapore",
    observed_at="2026-10-28T17:00",
    timezone="Asia/Singapore",
    condition="Thunderstorm",
    temperature=29,
    apparent_temperature=35,
    relative_humidity=86,
    precipitation=8.5,
    wind_speed=22,
)

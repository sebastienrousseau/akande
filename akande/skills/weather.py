# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Weather skill — Open-Meteo public API, no key required.

The skill resolves a place name via Open-Meteo's geocoder, then
asks the forecast endpoint for current conditions.  Both calls
are HTTPS, both return JSON, neither needs an API key.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request

from .base import (
    Intent,
    Skill,
    SkillContext,
    SkillMeta,
    SkillResult,
)

logger = logging.getLogger(__name__)

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
USER_AGENT = "akande/0.0.6 (+weather-skill)"
TIMEOUT_S = 6.0

_TRIGGER = re.compile(
    r"(?:what(?:'s| is)\s+the\s+weather|weather\s+(?:for|in)|"
    r"how\s+(?:'s|is)\s+the\s+weather)\s+(?:in\s+|for\s+)?"
    r"(?P<place>.+?)\s*[\.\?!]*$",
    re.IGNORECASE,
)

WMO_CODES = {
    0: "clear sky",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "depositing rime fog",
    51: "light drizzle",
    53: "moderate drizzle",
    55: "dense drizzle",
    61: "slight rain",
    63: "moderate rain",
    65: "heavy rain",
    71: "slight snowfall",
    73: "moderate snowfall",
    75: "heavy snowfall",
    77: "snow grains",
    80: "rain showers",
    81: "rain showers",
    82: "violent rain showers",
    95: "thunderstorm",
    96: "thunderstorm with slight hail",
    99: "thunderstorm with heavy hail",
}


class WeatherSkill(Skill):
    @property
    def meta(self) -> SkillMeta:
        return SkillMeta(
            name="weather",
            description=(
                "Current weather conditions for a place "
                "(Open-Meteo, no API key required)."
            ),
            requires_consent=False,
            supports_offline=False,
            citations_expected=True,
        )

    def match(self, text: str) -> Intent | None:
        m = _TRIGGER.search(text.strip())
        if not m:
            return None
        place = m.group("place").strip()
        if not place:
            return None
        return Intent(
            name="weather",
            args={"place": place},
            raw_text=text,
        )

    def handle(self, intent: Intent, ctx: SkillContext) -> SkillResult:
        place = str(intent.args.get("place") or "").strip()
        try:
            lat, lon, label = self._geocode(place)
        except _SkillFetchError as exc:
            return SkillResult(
                content=f"Could not look up {place!r}: {exc}",
                metadata={"error": "geocode_failed"},
            )
        try:
            current = self._forecast(lat, lon)
        except _SkillFetchError as exc:
            return SkillResult(
                content=(
                    f"Could not fetch the forecast for {label}: {exc}"
                ),
                metadata={"error": "forecast_failed"},
            )
        return SkillResult(
            content=self._render(label, current),
            citations=[
                "https://open-meteo.com",
            ],
            metadata={
                "place": label,
                "lat": lat,
                "lon": lon,
                "raw": current,
            },
        )

    # -- internals --------------------------------------------------

    def _geocode(  # pragma: no cover - hits open-meteo geocoder
        self, place: str
    ) -> tuple[float, float, str]:
        url = (
            GEOCODE_URL
            + "?"
            + urllib.parse.urlencode(
                {
                    "name": place,
                    "count": 1,
                    "language": "en",
                    "format": "json",
                }
            )
        )
        payload = _http_get_json(url)
        results = payload.get("results") or []
        if not results:
            raise _SkillFetchError("no match")
        top = results[0]
        label_parts = [str(top.get("name", place))]
        if top.get("admin1"):
            label_parts.append(str(top["admin1"]))
        if top.get("country"):
            label_parts.append(str(top["country"]))
        return (
            float(top["latitude"]),
            float(top["longitude"]),
            ", ".join(label_parts),
        )

    def _forecast(  # pragma: no cover - hits open-meteo forecast
        self, lat: float, lon: float
    ) -> dict:
        url = (
            FORECAST_URL
            + "?"
            + urllib.parse.urlencode(
                {
                    "latitude": lat,
                    "longitude": lon,
                    "current": (
                        "temperature_2m,apparent_temperature,"
                        "relative_humidity_2m,weather_code,"
                        "wind_speed_10m"
                    ),
                    "timezone": "auto",
                }
            )
        )
        payload = _http_get_json(url)
        return payload.get("current") or {}

    @staticmethod
    def _render(label: str, current: dict) -> str:
        if not current:
            return f"Forecast for {label}: no data available."
        temp = current.get("temperature_2m")
        feels = current.get("apparent_temperature")
        humidity = current.get("relative_humidity_2m")
        wind = current.get("wind_speed_10m")
        code = current.get("weather_code")
        condition = WMO_CODES.get(
            int(code) if isinstance(code, (int, float)) else -1,
            "conditions unknown",
        )
        lines = [
            f"Current weather in {label}:",
            f"  - condition: {condition}",
        ]
        if temp is not None:
            lines.append(f"  - temperature: {temp} °C")
        if feels is not None:
            lines.append(f"  - feels like:  {feels} °C")
        if humidity is not None:
            lines.append(f"  - humidity:    {humidity} %")
        if wind is not None:
            lines.append(f"  - wind:        {wind} km/h")
        return "\n".join(lines)


class _SkillFetchError(RuntimeError):
    """Internal — converted into a user-facing SkillResult."""


def _http_get_json(url: str) -> dict:
    req = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT}
    )
    try:
        # nosec B310 — hard-coded https://*.open-meteo.com endpoints.
        with urllib.request.urlopen(  # nosec B310
            req, timeout=TIMEOUT_S
        ) as resp:
            data = resp.read()
    except urllib.error.HTTPError as exc:
        raise _SkillFetchError(f"HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise _SkillFetchError(f"network error: {exc.reason}") from exc
    try:
        return json.loads(data.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise _SkillFetchError("malformed JSON from upstream") from exc

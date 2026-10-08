# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Tests for the four starter skills."""

from unittest.mock import MagicMock, patch

import pytest

from akande.skills import (
    BriefingSkill,
    FinanceSkill,
    WeatherSkill,
    WebSearchSkill,
    default_registry,
)
from akande.skills.base import Intent, SkillContext


class TestMatching:
    def test_weather_match(self):
        intent = WeatherSkill().match("what is the weather in Paris?")
        assert intent is not None
        assert intent.args["place"].lower().startswith("paris")

    def test_weather_no_match(self):
        assert WeatherSkill().match("tell me about Paris") is None

    def test_finance_match_dollar_symbol(self):
        intent = FinanceSkill().match("should I buy $AAPL today?")
        assert intent is not None
        assert intent.args["symbol"] == "AAPL"

    def test_finance_match_phrase(self):
        intent = FinanceSkill().match("price of TSLA")
        assert intent is not None
        assert intent.args["symbol"] == "TSLA"

    def test_finance_no_match(self):
        assert FinanceSkill().match("hello") is None

    def test_web_search_match(self):
        intent = WebSearchSkill().match(
            "search for quantitative easing"
        )
        assert intent is not None
        assert intent.args["query"] == "quantitative easing"

    def test_web_search_no_match_on_plain_text(self):
        assert WebSearchSkill().match("hello") is None

    def test_briefing_matches_anything(self):
        intent = BriefingSkill().match("anything at all")
        assert intent is not None

    def test_briefing_skips_empty(self):
        assert BriefingSkill().match("   ") is None


class TestRouting:
    def test_specific_skill_wins(self):
        reg = default_registry()
        match = reg.route("weather in Paris")
        assert match is not None
        assert match[0].meta.name == "weather"

    def test_finance_wins_over_briefing(self):
        reg = default_registry()
        match = reg.route("price of AAPL")
        assert match is not None
        assert match[0].meta.name == "finance"

    def test_falls_back_to_briefing(self):
        reg = default_registry()
        match = reg.route("explain quantitative easing")
        assert match is not None
        assert match[0].meta.name == "briefing"


class TestWeatherSkillHandle:
    def test_handles_geocode_failure(self):
        skill = WeatherSkill()
        with patch.object(
            skill,
            "_geocode",
            side_effect=__import__(
                "akande.skills.weather", fromlist=["_SkillFetchError"]
            )._SkillFetchError("no match"),
        ):
            result = skill.handle(
                Intent(name="weather", args={"place": "Atlantis"}),
                SkillContext(),
            )
        assert "Could not look up" in result.content
        assert result.metadata["error"] == "geocode_failed"

    def test_renders_current_conditions(self):
        skill = WeatherSkill()
        with (
            patch.object(
                skill,
                "_geocode",
                return_value=(48.86, 2.35, "Paris, France"),
            ),
            patch.object(
                skill,
                "_forecast",
                return_value={
                    "temperature_2m": 20,
                    "apparent_temperature": 19,
                    "relative_humidity_2m": 60,
                    "wind_speed_10m": 5,
                    "weather_code": 2,
                },
            ),
        ):
            result = skill.handle(
                Intent(
                    name="weather",
                    args={"place": "Paris"},
                ),
                SkillContext(),
            )
        assert "Paris, France" in result.content
        assert "partly cloudy" in result.content
        assert result.citations == ["https://open-meteo.com"]


class TestFinanceSkillHandle:
    def test_handles_no_quote(self):
        skill = FinanceSkill()
        with patch.object(skill, "_quote", return_value=None):
            result = skill.handle(
                Intent(
                    name="finance",
                    args={"symbol": "BOGUS"},
                ),
                SkillContext(),
            )
        assert "No quote returned" in result.content

    def test_renders_quote(self):
        skill = FinanceSkill()
        with patch.object(
            skill,
            "_quote",
            return_value={
                "symbol": "AAPL",
                "shortName": "Apple Inc.",
                "regularMarketPrice": 200.0,
                "regularMarketChange": 1.5,
                "regularMarketChangePercent": 0.75,
                "currency": "USD",
            },
        ):
            result = skill.handle(
                Intent(
                    name="finance",
                    args={"symbol": "AAPL"},
                ),
                SkillContext(),
            )
        assert "AAPL" in result.content
        assert "Apple Inc." in result.content
        assert "200" in result.content
        # The disclaimer is always emitted.
        assert "Not investment advice" in result.content


class TestFinanceInternals:
    def test_quote_http_error(self):
        import urllib.error

        from akande.skills.finance import FinanceSkill, _FetchError

        skill = FinanceSkill()
        with patch(
            "akande.skills.finance.urllib.request.urlopen",
            side_effect=urllib.error.HTTPError(
                "url",
                404,
                "Not Found",
                {},
                None,  # type: ignore[arg-type]
            ),
        ):
            with pytest.raises(_FetchError, match="HTTP 404"):
                skill._quote("AAPL")

    def test_quote_url_error(self):
        import urllib.error

        from akande.skills.finance import FinanceSkill, _FetchError

        skill = FinanceSkill()
        with patch(
            "akande.skills.finance.urllib.request.urlopen",
            side_effect=urllib.error.URLError("timed out"),
        ):
            with pytest.raises(_FetchError, match="network error"):
                skill._quote("AAPL")

    def test_quote_json_error(self):
        from unittest.mock import MagicMock

        from akande.skills.finance import FinanceSkill, _FetchError

        skill = FinanceSkill()
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"not json"
        mock_resp.__enter__.return_value = mock_resp
        with patch(
            "akande.skills.finance.urllib.request.urlopen",
            return_value=mock_resp,
        ):
            with pytest.raises(_FetchError, match="malformed JSON"):
                skill._quote("AAPL")

    def test_quote_empty_results(self):
        from unittest.mock import MagicMock

        from akande.skills.finance import FinanceSkill

        skill = FinanceSkill()
        mock_resp = MagicMock()
        mock_resp.read.return_value = (
            b'{"quoteResponse": {"result": []}}'
        )
        mock_resp.__enter__.return_value = mock_resp
        with patch(
            "akande.skills.finance.urllib.request.urlopen",
            return_value=mock_resp,
        ):
            assert skill._quote("AAPL") is None


class TestWebSearchSkillHandle:
    def test_extracts_citations_from_render(self):
        skill = WebSearchSkill()
        fake_result = MagicMock()
        fake_result.content = (
            "Top 1 results for foo:\n"
            "1. Hello\n"
            "   https://example.com\n"
            "   snippet"
        )
        fake_result.metadata = {"count": 1}
        with patch.object(skill._tool, "run", return_value=fake_result):
            result = skill.handle(
                Intent(
                    name="web_search",
                    args={"query": "foo"},
                ),
                SkillContext(),
            )
        assert result.citations == ["https://example.com"]


class TestBriefingSkillHandle:
    def test_extracts_assistant_content(self):
        from types import SimpleNamespace

        from akande.skills.briefing import BriefingSkill

        skill = BriefingSkill()
        with patch("akande.skills.briefing.get_provider") as gp:
            provider = MagicMock()
            provider.provider_name = "openai"
            provider.generate_response_sync.return_value = (
                SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(content="brief")
                        )
                    ]
                )
            )
            gp.return_value = provider
            result = skill.handle(
                Intent(
                    name="briefing",
                    args={"text": "hello"},
                ),
                SkillContext(),
            )
        assert result.content == "brief"
        assert result.metadata["provider"] == "openai"

    def test_empty_choices_yields_empty_content(self):
        from types import SimpleNamespace

        from akande.skills.briefing import BriefingSkill

        skill = BriefingSkill()
        with patch("akande.skills.briefing.get_provider") as gp:
            provider = MagicMock()
            provider.provider_name = "openai"
            provider.generate_response_sync.return_value = (
                SimpleNamespace(choices=[])
            )
            gp.return_value = provider
            result = skill.handle(
                Intent(
                    name="briefing",
                    args={"text": "hello"},
                ),
                SkillContext(),
            )
        assert result.content == ""

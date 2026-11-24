"""Offline checks: no API use, no paid calls."""
import os
import unittest
import xml.etree.ElementTree as ET
from datetime import datetime
from zoneinfo import ZoneInfo
import requests
from unittest.mock import patch
from types import SimpleNamespace
from src.first_light import (
    public_base, xml_feed, web_sources, web_page,
    http_json, fetch_weather, weather_narration, _weather_unavailable
)

class PodcastTests(unittest.TestCase):
    def test_public_url(self):
        with patch.dict(os.environ, {"GITHUB_REPOSITORY": "snrahimi/first-light-podcast", "FEED_BASE_URL": ""}):
            self.assertEqual(public_base(), "https://snrahimi.github.io/first-light-podcast")

    def test_xml_valid_and_enclosure_present(self):
        release = {
            "tag_name": "first-light-2026-11-23",
            "html_url": "https://github.com/snrahimi/first-light-podcast/releases/tag/example",
            "published_at": "2026-11-23T10:00:00Z",
            "assets": [{"name": "first-light-2026-11-23.mp3", "size": 1234567,
                        "browser_download_url": "https://example.org/episode.mp3"}]
        }
        doc = xml_feed([release], "https://example.org")
        root = ET.fromstring(ET.tostring(doc.getroot()))
        item = root.find("./channel/item")
        self.assertIsNotNone(item)
        self.assertEqual(item.find("enclosure").attrib["type"], "audio/mpeg")
        self.assertEqual(item.find("enclosure").attrib["length"], "1234567")
        self.assertEqual(root.find("./channel/title").text, "First Light: World Report")

    def test_source_dedup(self):
        fake = SimpleNamespace(model_dump=lambda: {"output": [
            {"content": [{"annotations": [{"type": "url_citation",
                "url": "https://example.com/a", "title": "A"}]}]},
            {"action": {"sources": [
                {"url": "https://example.com/a", "title": "Again"},
                {"url": "https://example.com/b", "title": "B"}]}}
        ]})
        self.assertEqual(len(web_sources(fake)), 2)

    def test_html_escaped(self):
        page = web_page("2026-11-23", [{"url": "https://example.com/?x=1&y=2", "title": "<hello>"}], "<transcript>")
        self.assertIn("&lt;hello&gt;", page)
        self.assertIn("&lt;transcript&gt;", page)
        self.assertIn("x=1&amp;y=2", page)

    def test_weather_network_retries_then_succeeds(self):
        good = SimpleNamespace(
            json=lambda: {"ok": True},
            raise_for_status=lambda: None,
        )
        with patch("src.first_light.requests.get", side_effect=[
            requests.exceptions.ReadTimeout("transient"), good
        ]) as get, patch("src.first_light.time.sleep") as sleep:
            self.assertEqual(
                http_json("https://api.open-meteo.com/v1/forecast", attempts=3),
                {"ok": True}
            )
            self.assertEqual(get.call_count, 2)
            sleep.assert_called_once()

    def test_weather_network_outage_preserves_podcast(self):
        now = datetime(2026, 11, 23, 4, 0, tzinfo=ZoneInfo("America/Chicago"))
        err = requests.exceptions.ReadTimeout("weather provider outage")
        with patch("src.first_light.http_json", side_effect=err), patch(
            "src.first_light._nws_weather_backup", side_effect=err
        ):
            w = fetch_weather(now)
        self.assertEqual(w["source"], "unavailable")
        self.assertIsNone(w["temperature_f"])
        spoken = weather_narration(w)
        self.assertIn("temporarily unavailable", spoken)
        self.assertNotIn("0 degrees", spoken)
        self.assertIn("official alert feed could not be verified", spoken)

    def test_weather_nws_backup_keeps_forecast_not_observation(self):
        now = datetime(2026, 11, 23, 4, 0, tzinfo=ZoneInfo("America/Chicago"))
        nws = _weather_unavailable(now)
        nws.update({
            "source": "NWS period forecast",
            "conditions": "Mostly Sunny",
            "high_f": 77,
            "low_f": 55,
            "max_rain_percent": 10
        })
        err = requests.exceptions.ReadTimeout("open meteo outage")
        with patch("src.first_light.http_json", side_effect=err), patch(
            "src.first_light._nws_weather_backup", return_value=nws
        ):
            w = fetch_weather(now)
        self.assertEqual(w["source"], "NWS period forecast")
        narration = weather_narration(w)
        self.assertIn("forecast high is near 77", narration)
        self.assertNotIn("currently around", narration)

    def test_nws_weather_fallback_extracts_only_today(self):
        from src.first_light import _nws_weather_backup
        now = datetime(2026, 11, 23, 4, 0, tzinfo=ZoneInfo("America/Chicago"))
        points = {"properties": {
            "forecast": "https://api.weather.gov/gridpoints/EWX/99,99/forecast"
        }}
        periods = {"properties": {"periods": [
            {"startTime": "2026-11-23T06:00:00-06:00",
             "isDaytime": True, "temperatureUnit": "F",
             "temperature": 72, "shortForecast": "Sunny",
             "probabilityOfPrecipitation": {"value": 10}},
            {"startTime": "2026-11-23T19:00:00-06:00",
             "isDaytime": False, "temperatureUnit": "F",
             "temperature": 53, "shortForecast": "Clear",
             "probabilityOfPrecipitation": None},
        ]}}
        with patch("src.first_light.http_json", side_effect=[points, periods]):
            w = _nws_weather_backup(now)
        self.assertEqual(w["high_f"], 72)
        self.assertEqual(w["low_f"], 53)
        self.assertEqual(w["max_rain_percent"], 10)
        self.assertIsNone(w["temperature_f"])

if __name__ == "__main__":
    unittest.main()

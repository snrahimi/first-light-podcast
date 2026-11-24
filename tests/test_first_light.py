"""Offline checks: no API use, no paid calls."""
import os
import unittest
import xml.etree.ElementTree as ET
from datetime import datetime
from zoneinfo import ZoneInfo
import requests
import base64
import io
import tempfile
import wave
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
from src.first_light import (
    public_base, xml_feed, web_sources, web_page,
    http_json, fetch_weather, weather_narration, _weather_unavailable,
    _gemini_chunks, _gemini_speech_payload, _tts_gemini,
    inspect_audio, _trusted_feed_link, news_and_script,
    synthesize, _charon_segment,
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

    def test_gemini_chunks_preserve_script(self):
        text = " ".join("This sentence has twelve words about the world's headlines today." for _ in range(28))
        pieces = _gemini_chunks(text, max_words=45)
        self.assertGreater(len(pieces), 3)
        self.assertEqual(" ".join(pieces), text)
        self.assertTrue(all(len(piece.split()) <= 45 for piece in pieces))

    def test_gemini_payload_uses_selected_charon(self):
        obj = _gemini_speech_payload("Good morning, San Antonio.")
        self.assertEqual(obj["model"], "gemini-3.8-flash-tts")
        self.assertEqual(obj["generation_config"]["speech_config"][0]["voice"], "Charon")

    def test_gemini_audio_merges_valid_wave_segments(self):
        from src.first_light import _tts_gemini
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(24000)
            wav.writeframes(b"\x00\x00" * 24000 * 4)
        audio = base64.b64encode(buf.getvalue()).decode("ascii")
        fake = SimpleNamespace(
            status_code=200,
            json=lambda: {"steps": [{"type": "model_output", "content": [
                {"type": "audio", "data": audio}
            ]}]}
        )
        script = " ".join(("Good morning, San Antonio, here are world news headlines. " * 40).split())
        with tempfile.TemporaryDirectory() as temp, patch.dict(
            os.environ, {"GEMINI_API_KEY": "test-key"}
        ), patch("src.first_light.requests.post", return_value=fake) as post, \
             patch("src.first_light.time.sleep"):
            dest = Path(temp) / "test.wav"
            _tts_gemini(script, dest)
            self.assertTrue(dest.is_file())
            self.assertGreaterEqual(post.call_count, 2)
            with wave.open(str(dest), "rb") as joined:
                self.assertEqual(joined.getframerate(), 24000)
                self.assertGreater(joined.getnframes(), 24000 * 8)

    def test_gemini_http_failure_does_not_return_audio(self):
        bad = SimpleNamespace(status_code=429)
        with tempfile.TemporaryDirectory() as temp, patch.dict(
            os.environ, {"GEMINI_API_KEY": "test-key"}
        ), patch("src.first_light.requests.post", return_value=bad) as post, \
             patch("src.first_light.time.sleep") as sleeper:
            destination = Path(temp) / "test.wav"
            with self.assertRaisesRegex(RuntimeError, "HTTP 429"):
                _tts_gemini("Good morning.", destination)
            self.assertEqual(post.call_count, 3)
            self.assertFalse(destination.exists())
            self.assertEqual(sleeper.call_count, 2)

    def test_charon_429_retries_then_recovers(self):
        slow = SimpleNamespace(status_code=429)
        good = SimpleNamespace(status_code=200)
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-only"}), \
             patch("src.first_light.requests.post",
                   side_effect=[slow, good]) as post, \
             patch("src.first_light.time.sleep") as sleeper:
            result = _charon_segment("Good morning.", 3, 4)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(post.call_count, 2)
        sleeper.assert_called_once_with(35)

    def test_charon_permanent_http_failure_is_not_retried(self):
        rejected = SimpleNamespace(status_code=403)
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-only"}), \
             patch("src.first_light.requests.post",
                   return_value=rejected) as post, \
             patch("src.first_light.time.sleep") as sleeper:
            with self.assertRaisesRegex(RuntimeError, "segment 3/4 failed: HTTP 403"):
                _charon_segment("Good morning.", 3, 4)
        post.assert_called_once()
        sleeper.assert_not_called()

    def test_charon_failure_never_uses_adam_or_piper(self):
        with tempfile.TemporaryDirectory() as temp, \
             patch("src.first_light.WORK", Path(temp)), \
             patch("src.first_light._tts_gemini",
                   side_effect=RuntimeError("HTTP 429")), \
             patch("src.first_light._tts_kokoro") as adam, \
             patch("src.first_light._tts_piper") as piper, \
             patch("src.first_light.subprocess.run") as ffmpeg:
            destination = Path(temp) / "first-light.mp3"
            with self.assertRaisesRegex(RuntimeError, "HTTP 429"):
                synthesize("Example sourced briefing.", destination)
            self.assertFalse(destination.exists())
        adam.assert_not_called()
        piper.assert_not_called()
        ffmpeg.assert_not_called()

    def test_charon_missing_api_key_does_not_create_output(self):
        with tempfile.TemporaryDirectory() as temp, \
             patch.dict(os.environ, {"GEMINI_API_KEY": ""}), \
             patch("src.first_light.requests.post") as post:
            destination = Path(temp) / "test.wav"
            with self.assertRaisesRegex(RuntimeError, "API key is missing"):
                _tts_gemini("One sentence.", destination)
            self.assertFalse(destination.exists())
        post.assert_not_called()

    def test_rss_source_domains_reject_impersonators(self):
        self.assertTrue(_trusted_feed_link(
            "NPR World", "https://www.npr.org/sections/world/"))
        self.assertTrue(_trusted_feed_link(
            "The Guardian World", "https://www.theguardian.com/world"))
        self.assertFalse(_trusted_feed_link(
            "NPR World", "https://npr.org.attacker.example/news"))
        self.assertFalse(_trusted_feed_link(
            "BBC World", "http://www.bbc.com/news"))
        self.assertFalse(_trusted_feed_link(
            "Al Jazeera", "https://example.net/article"))

    def test_full_editorial_handoff_contains_sourced_plan_and_history(self):
        from tests_support import editorial_groups
        now = datetime(2026, 11, 23, 5, 0,
                       tzinfo=ZoneInfo("America/Chicago"))
        weather = {"source": "unavailable", "nws_alert_check": "not verified",
                   "nws_active_alerts": []}
        with patch.dict(os.environ, {"GH_TOKEN": "test", "GITHUB_REPOSITORY": "a/b"}), \
             patch("src.first_light.rss_news", return_value=editorial_groups()), \
             patch("src.first_light.editorial.load_history", return_value=[]), \
             patch("src.first_light.newsroom3.collect_source_expansion", \
                   return_value=({section: [] for section in editorial_groups()}, [])), \
             patch("src.first_light.optional_gemini_script", return_value=None):
            notes, sources, script, edition = news_and_script(None, now, weather)
        self.assertGreaterEqual(edition["count"], 5)
        self.assertLessEqual(edition["count"], 8)
        self.assertTrue(edition["script_mode"].startswith("source-attributed"))
        self.assertIn("artificial intelligence assistance", script)
        self.assertIn("not independent verification", notes)
        self.assertGreaterEqual(len(sources), 5)
        self.assertGreater(edition["newsroom3_audit"]["attributed_claims"], 0)
        self.assertEqual(
            edition["newsroom3_audit"]["independently_verified_facts"], 0
        )

    def test_audio_probe_detects_short_and_invalid_mp3(self):
        valid = {"format": {"duration": "360.0", "bit_rate": "192000"},
                 "streams": [{"codec_name": "mp3", "sample_rate": "44100",
                              "channels": 1}]}
        with patch("src.first_light.subprocess.run",
                   return_value=SimpleNamespace(stdout=json.dumps(valid))):
            report = inspect_audio(Path("/tmp/test.mp3"))
        self.assertTrue(report["duration_in_target"])
        self.assertEqual(report["sample_rate_hz"], 44100)
        valid["format"]["duration"] = "55.0"
        with patch("src.first_light.subprocess.run",
                   return_value=SimpleNamespace(stdout=json.dumps(valid))):
            with self.assertRaises(RuntimeError):
                inspect_audio(Path("/tmp/test.mp3"))


    def test_entrypoints_load_editorial_before_configuration_checks(self):
        """Both GitHub module launch and direct script launch must import."""
        root = Path(__file__).resolve().parents[1]
        source = root / "src" / "first_light.py"
        environment = dict(os.environ)
        environment.pop("GH_TOKEN", None)
        for invocation in (
            [sys.executable, "-m", "src.first_light"],
            [sys.executable, str(source)],
        ):
            with self.subTest(invocation=invocation):
                result = subprocess.run(
                    invocation, cwd=root, env=environment,
                    capture_output=True, text=True, timeout=15,
                )
                # Startup must reach the deliberate missing-token guard, rather
                # than failing at imports; it must not make live API requests.
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn("Missing environment variable: GH_TOKEN", result.stderr)
                self.assertNotIn("ModuleNotFoundError", result.stderr)


if __name__ == "__main__":
    unittest.main()

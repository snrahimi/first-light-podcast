"""Offline tests for evidence-first, two-part writing and Charon runtime."""
import json
import unittest
from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo
from unittest.mock import patch

from src import broadcast32, newsroom3, editorial
from tests_support import editorial_groups

NOW = datetime(2026, 11, 23, 5, tzinfo=ZoneInfo("America/Chicago"))


def edition_and_dossiers():
    edition = editorial.curate(editorial_groups(), [], NOW)
    dossiers = newsroom3.build_dossiers(edition, [])
    for chapter in dossiers.values():
        for card in chapter:
            card["official_context"] = []
            card["reporting_comparison"] = {
                "different_numbers_need_review": False,
                "independent_reporting_established": False,
            }
    return edition, dossiers


def reply(script):
    return SimpleNamespace(
        status_code=200,
        json=lambda: {"candidates": [{"content": {
            "parts": [{"text": script}]
        }}]},
    )


class Broadcast32Tests(unittest.TestCase):
    def test_charon_measured_speech_rate(self):
        self.assertEqual(broadcast32.estimate_duration(657), 242)
        self.assertTrue(300 <= broadcast32.estimate_duration(925) <= 420)

    def test_topic_partition_and_two_only_model_calls(self):
        edition, dossiers = edition_and_dossiers()
        world = ("According to BBC and NPR, the news coverage describes a "
                 "developing international diplomatic discussion without confirmed "
                 "new agreements. Details remain limited. " * 20)
        briefs = ("The Guardian and NASA provide source-linked reports, with "
                  "scientific and economic claims attributed to the relevant "
                  "publishing agencies. No unsupported outcomes are announced. " * 18)
        calls = []
        def fake_post(url, **kw):
            calls.append(kw["json"]["contents"][0]["parts"][0]["text"])
            return reply(world if len(calls) == 1 else briefs)
        script, meta = broadcast32.generated_script(
            NOW, edition, dossiers,
            "San Antonio's forecast cannot be verified at this time.",
            "test-only", "gemini-3.5-flash-lite", post=fake_post)
        self.assertEqual(len(calls), 2)
        self.assertIn("Top world headlines", calls[0])
        self.assertNotIn("Technology and cybersecurity", calls[0].split("RESEARCH CARDS:")[-1])
        self.assertIn("Technology and cybersecurity", calls[1])
        self.assertNotIn("Top world headlines", calls[1].split("RESEARCH CARDS:")[-1])
        self.assertIn("AI assistance", script)
        self.assertIn("San Antonio's forecast", script)
        self.assertEqual(meta["provider_calls"], 2)
        self.assertEqual(meta["estimated_seconds"],
                         broadcast32.estimate_duration(meta["total_words"]))
        self.assertGreater(meta["total_words"], 800)
        self.assertEqual(broadcast32.quality(script, edition, NOW)["script_words"],
                         meta["total_words"])

    def test_provider_http_429_stops_before_second_request(self):
        edition, dossiers = edition_and_dossiers()
        calls = []
        def limited(url, **kw):
            calls.append(url)
            return SimpleNamespace(status_code=429)
        script, meta = broadcast32.generated_script(
            NOW, edition, dossiers, "Weather unavailable.",
            "test", "gemini-3.5-flash-lite", post=limited)
        self.assertIsNone(script)
        self.assertEqual(len(calls), 1)
        self.assertEqual(meta["provider_calls"], 1)

    def test_missing_key_never_makes_network_calls(self):
        edition, dossiers = edition_and_dossiers()
        with patch("src.broadcast32.requests.post") as post:
            value, info = broadcast32.generated_script(
                NOW, edition, dossiers, "", "", "gemini-3.5-flash-lite")
        self.assertIsNone(value)
        self.assertEqual(info["provider_calls"], 0)
        post.assert_not_called()

    def test_short_evidence_limited_script_not_automatically_padded(self):
        edition, dossiers = edition_and_dossiers()
        short_a = "BBC reports international developments in world diplomacy. " * 30
        short_b = "NASA and NPR report a science and technology update. " * 25
        calls = iter([reply(short_a), reply(short_b)])
        script, info = broadcast32.generated_script(
            NOW, edition, dossiers, "The weather feed is unavailable.",
            "test", "gemini-3.5-flash-lite",
            post=lambda *a, **k: next(calls))
        self.assertIsNotNone(script)
        self.assertTrue(info["script_short_by_evidence"])
        self.assertLess(info["estimated_seconds"], 300)
        self.assertLess(info["provider_calls"], 3)

    def test_shorter_but_substantive_sections_are_not_automatically_discarded(self):
        section = "BBC reports updates to the international diplomatic talks. " * 15
        self.assertIsNone(broadcast32._section_rejection(section))
        self.assertTrue(broadcast32._check_section(section))
        reason = broadcast32._section_rejection("Too short to be news.")
        self.assertTrue(reason.startswith("too_short_"))
        self.assertEqual(
            broadcast32._section_rejection("See https://example.org/news " * 75),
            "raw_url_in_spoken_script"
        )

    def test_invalid_model_does_not_call_provider(self):
        edition, dossiers = edition_and_dossiers()
        with patch("src.broadcast32.requests.post") as post:
            script, meta = broadcast32.generated_script(
                NOW, edition, dossiers, "", "test", "../../model")
        self.assertIsNone(script)
        self.assertEqual(meta["reason"], "invalid model")
        post.assert_not_called()

    def test_quality_rejects_missing_identity_and_date(self):
        edition, _ = edition_and_dossiers()
        with self.assertRaises(ValueError):
            broadcast32.quality("No source available " * 100, edition, NOW)

    def test_writer_only_passes_bounded_evidence_cards(self):
        edition, dossiers = edition_and_dossiers()
        dossiers["Top world headlines"][0]["discovery_leads"] = [
            {"title": "irrelevant scouting", "url": "https://example.org/x"}
        ]
        inputs = []
        def post(url, **kw):
            inputs.append(kw["json"]["contents"][0]["parts"][0]["text"])
            return reply("BBC reports developments in world affairs. " * 60)
        broadcast32.generated_script(
            NOW, edition, dossiers, "Local forecast unavailable.",
            "test", "gemini-3.5-flash-lite", post=post)
        self.assertEqual(len(inputs), 2)
        self.assertNotIn("irrelevant scouting", " ".join(inputs))
        self.assertNotIn("discovery_leads", " ".join(inputs))


if __name__ == "__main__":
    unittest.main()

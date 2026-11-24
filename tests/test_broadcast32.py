"""Offline tests for evidence-first, two-part writing and Charon runtime."""
import json
import tempfile
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
    def test_duration_preflight_reports_shortfall_without_padding(self):
        result = broadcast32.duration_preflight(529)
        self.assertFalse(result["estimated_in_target"])
        self.assertEqual(result["status"], "estimated_short")
        self.assertEqual(result["minimum_target_words"], 815)
        self.assertEqual(result["shortfall_words"], 286)
        self.assertGreater(result["shortfall_seconds"], 90)
        self.assertTrue(broadcast32.duration_preflight(925)[
            "estimated_in_target"])
        self.assertEqual(broadcast32.duration_preflight(1150)[
            "status"], "estimated_long")
        with self.assertRaises(ValueError):
            broadcast32.duration_preflight(150, wpm=0)

    def test_more_distinct_evidence_increases_supported_story_budget(self):
        sparse = {"Top world headlines": [{
            "headline": "Limited world report",
            "evidence": [{"publisher": "BBC", "text": "A single dated claim."}],
            "official_context": [],
        }]}
        rich = {"Top world headlines": [{
            "headline": "Supported world report",
            "evidence": [
                {"publisher": "BBC", "text": f"Distinct statement {n}"}
                for n in range(5)
            ],
            "official_context": [
                {"agency": "United Nations Press Releases",
                 "quoted_excerpt": "Agency statement."}
            ],
        }]}
        a = broadcast32._editorial_beat_plan(sparse)[0]
        b = broadcast32._editorial_beat_plan(rich)[0]
        self.assertGreater(b["suggested_words_if_supported"],
                           a["suggested_words_if_supported"])
        self.assertEqual(a["distinct_attributed_excerpts"], 1)
        prompt = broadcast32._prompt(NOW, "world", rich, 400)
        self.assertIn("STORY PLAN", prompt)
        self.assertIn("strict source boundaries".upper(), prompt)
        self.assertIn("Do not repeat the same fact", prompt)

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

    def test_transient_503_retries_only_failed_section(self):
        edition, dossiers = edition_and_dossiers()
        one = "BBC reports updates to international diplomatic discussions. " * 30
        two = "NASA and NPR report economic and scientific developments. " * 30
        calls, naps = [], []
        def post(url, **kw):
            calls.append(len(calls))
            return (reply(one) if len(calls) == 1 else
                    SimpleNamespace(status_code=503) if len(calls) == 2 else
                    reply(two))
        script, meta = broadcast32.generated_script(
            NOW, edition, dossiers, "Weather unavailable.",
            "test", "gemini-3.5-flash-lite", post=post,
            sleep=naps.append)
        self.assertIsNotNone(script)
        self.assertEqual(meta["provider_calls"], 3)
        self.assertEqual(meta["retries"], 1)
        self.assertEqual(len(naps), 1)

    def test_http_503_exhaustion_is_bounded(self):
        calls, sleeps = [], []
        def post(*args, **kwargs):
            calls.append(1)
            return SimpleNamespace(status_code=503)
        result = broadcast32._call_gemini(
            "test", "gemini-3.5-flash-lite", "sample",
            post=post, sleep=sleeps.append)
        self.assertIsNone(result)
        self.assertEqual(len(calls), 3)
        self.assertEqual(len(sleeps), 2)

    def test_cached_completed_section_recovers_after_second_section_fails(self):
        edition, dossiers = edition_and_dossiers()
        lead = "BBC reports international diplomatic developments. " * 32
        briefs = "NASA and NPR report scientific and economic topics. " * 30
        with tempfile.TemporaryDirectory() as cache_dir:
            first_calls = []
            def first_post(*args, **kwargs):
                first_calls.append(1)
                return reply(lead) if len(first_calls) == 1 else SimpleNamespace(
                    status_code=429)
            script, meta = broadcast32.generated_script(
                NOW, edition, dossiers, "Weather unavailable.",
                "test", "gemini-3.5-flash-lite", post=first_post,
                cache_dir=cache_dir, sleep=lambda _: None)
            self.assertIsNone(script)
            self.assertEqual(meta["provider_calls"], 2)
            next_calls = []
            def second_post(*args, **kwargs):
                next_calls.append(1)
                return reply(briefs)
            script, meta = broadcast32.generated_script(
                NOW, edition, dossiers, "Weather unavailable.",
                "test", "gemini-3.5-flash-lite", post=second_post,
                cache_dir=cache_dir, sleep=lambda _: None)
            self.assertIsNotNone(script)
            self.assertEqual(len(next_calls), 1)
            self.assertEqual(meta["cache_hits"], 1)
            self.assertEqual(meta["provider_calls"], 1)

    def test_cache_identity_prevents_stale_source_reuse(self):
        import os
        from pathlib import Path
        with tempfile.TemporaryDirectory() as cache_dir:
            p = "Prompt for Tuesday, updated official story"
            broadcast32._remember_section(
                cache_dir, "gemini-3.5-flash-lite", p,
                "BBC reports international verified statements. " * 32)
            self.assertIsNone(broadcast32._cached_section(
                cache_dir, "gemini-3.5-flash-lite", p + " revised"))
            self.assertIsNone(broadcast32._cached_section(
                cache_dir, "different-model", p))
            matching = broadcast32._cached_section(
                cache_dir, "gemini-3.5-flash-lite", p)
            self.assertIsNotNone(matching)
            path = broadcast32._cache_path(
                cache_dir, "gemini-3.5-flash-lite", p)
            raw = json.loads(path.read_text())
            raw["created"] -= 13 * 3600
            path.write_text(json.dumps(raw))
            self.assertIsNone(broadcast32._cached_section(
                cache_dir, "gemini-3.5-flash-lite", p))

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

    def test_spoken_ai_disclosure_is_accepted_after_pronunciation_expansion(self):
        from src import editorial
        edition, _ = edition_and_dossiers()
        draft = (
            "Good morning, San Antonio. This is First Light: World Report "
            "for November 23, 2026. This report is produced with AI assistance. "
            + "BBC reports international developments in world affairs. " * 75
        )
        voiced = editorial.speaking_text(draft)
        self.assertIn("artificial intelligence assistance", voiced)
        self.assertNotIn("AI assistance", voiced)
        self.assertGreater(broadcast32.quality(voiced, edition, NOW)[
            "script_words"], 480)
        self.assertGreater(broadcast32.quality(draft, edition, NOW)[
            "script_words"], 480)
        with self.assertRaisesRegex(ValueError, "assistance disclosure"):
            broadcast32.quality(
                voiced.replace("artificial intelligence assistance",
                               "automated source checks"), edition, NOW
            )

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

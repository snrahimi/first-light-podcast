"""Newsroom 3.3: source-safe cold opens, continuity and late-weather names.

All tests are offline. They never generate or publish audio or call Gemini.
"""
import os
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

from src import (
    editorial33, editorial, newsroom3, research33,
    broadcast32, pronunciation, elevenlabs_production as tts, first_light,
)
from tests_support import editorial_groups


NOW = datetime(2026, 11, 25, 5, tzinfo=ZoneInfo("America/Chicago"))


class Editorial33MetadataTests(unittest.TestCase):
    def setUp(self):
        self.edition = editorial.curate(editorial_groups(), [], NOW)

    def test_episode_title_uses_only_two_actual_source_headlines(self):
        package = editorial33.topic_packaging(self.edition)
        self.assertTrue(package["display_title"].startswith("First Light | "))
        self.assertEqual(len(package["lead_headlines"]), 2)
        for card in package["lead_headlines"]:
            self.assertIn(card["headline"], [
                x["title"] for x in
                self.edition["rundown"]["Top world headlines"]
            ])
        self.assertTrue(package["headlines_not_independently_verified"])
        self.assertIn("section_counts", package)

    def test_release_title_marker_survives_rss_without_changing_guid(self):
        package = editorial33.topic_packaging(self.edition)
        title = package["display_title"]
        marker = editorial33.title_release_marker(title)
        self.assertEqual(editorial33.title_from_release_notes(
            "Release content\n" + marker + "\nOther notes"
        ), title)
        self.assertIsNone(editorial33.title_from_release_notes("Legacy release"))
        # The RSS assembler parses historical Release bodies. It must
        # ignore malformed owner-supplied markers, never crash the feed.
        self.assertIsNone(editorial33.title_from_release_notes(
            "<!-- FIRST_LIGHT_EPISODE_TITLE_V1:zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz -->"
        ))
        release = {
            "tag_name": "first-light-2026-11-25",
            "published_at": "2026-11-25T10:30:00Z",
            "html_url": "https://github.com/example/first-light",
            "assets": [{
                "name": "first-light-2026-11-25.mp3",
                "size": 200000,
                "browser_download_url": "https://example.test/audio.mp3",
            }],
            "body": "Release content\n" + marker,
        }
        feed = first_light.xml_feed(
            [release], "https://example.test"
        )
        row = feed.getroot().find("./channel/item")
        self.assertEqual(row.find("title").text, title)
        self.assertEqual(row.find("guid").text, "first-light-2026-11-25")

    def test_page_escapes_source_headline_and_preserves_transcript(self):
        untrusted = 'Today: <svg onload="steal()"> & a report'
        original = "Good morning, San Antonio. This is First Light."
        html = first_light.web_page(
            "2026-11-25", [], original, narrator="ElevenLabs Brian",
            episode_heading=untrusted,
        )
        self.assertNotIn('<svg onload="steal()">', html)
        self.assertIn("&lt;svg onload=", html)
        self.assertIn("Good morning, San Antonio.", html)
        self.assertIn("Voice generated with", html)

    def test_continuity_is_headline_memory_not_fact_verified(self):
        previous = {
            "headline": "Country A and Country B discuss trade",
            "date": "2026-11-24",
        }
        card = editorial33.continuity_card({
            "previous": previous,
            "freshness": {"prior_edition_coverage": "related_update_unverified"}
        })
        self.assertEqual(card["type"], "possibly_continuing_story")
        self.assertEqual(card["previous_edition_date"], "2026-11-24")
        self.assertFalse(card["verified_new_detail"])
        self.assertIn("today's excerpts", card["rule"])
        fresh = editorial33.continuity_card({"previous": None})
        self.assertEqual(fresh["type"], "new_to_show_or_no_prior_record")
        self.assertFalse(fresh["verified_new_detail"])

    def test_splitter_accepts_only_well_formed_source_preview(self):
        teaser = (
            "Two major developments are drawing attention today. "
            "One involves international talks, while another concerns "
            "a regional court decision. Here is what reporting says so far."
        )
        report = (
            "According to the cited publisher, a discussion took place. "
            "The issuing agency has not released additional findings. "
        ) * 15
        preview, text, qa = editorial33.split_preview(
            "PREVIEW: " + teaser + " STORY: " + report
        )
        self.assertEqual(preview, teaser)
        self.assertEqual(text, " ".join(report.split()))
        self.assertEqual(qa["mode"], "structured_two_story_preview")
        self.assertTrue(16 <= qa["preview_words"] <= 48)
        none, original, qa = editorial33.split_preview(report)
        self.assertEqual(none, "")
        self.assertEqual(original, " ".join(report.split()))
        self.assertEqual(qa["mode"], "unstructured_world_section")

    def test_rejected_teaser_does_not_invent_new_story(self):
        report = ("An agency released a statement. " * 40).strip()
        teaser, world, qa = editorial33.split_preview(
            "PREVIEW: Today. STORY: " + report
        )
        self.assertEqual(teaser, "")
        self.assertEqual(world, report)
        self.assertEqual(qa["mode"], "rejected_preview_limits")

    def test_generated_script_uses_two_calls_and_separates_cold_open(self):
        edition = self.edition
        dossiers = newsroom3.build_dossiers(edition, [])
        for cards in dossiers.values():
            for item in cards:
                item["official_context"] = []
                item["lead_feed_context"] = []
                item["reporting_comparison"] = {
                    "different_numbers_need_review": False,
                    "independent_reporting_established": False,
                }
        teaser = (
            "Two major developments are in focus today. "
            "One concerns international discussions, and another "
            "involves a regional court. Here is what the reporting establishes."
        )
        lead = ("A source describes a development under review. "
                "Officials have not reported a final outcome. ") * 13
        other = ("A publication provides an attributed update. "
                 "The available material describes an ongoing review. ") * 14
        prompts = []
        def fake_post(url, **kw):
            prompts.append(kw["json"]["contents"][0]["parts"][0]["text"])
            payload = (
                "PREVIEW: " + teaser + " STORY: " + lead
                if len(prompts) == 1 else other
            )
            return SimpleNamespace(status_code=200, json=lambda: {
                "candidates": [{"content": {"parts": [{"text": payload}]}}]
            })
        script, info = broadcast32.generated_script(
            NOW, edition, dossiers, "Weather services are unavailable.",
            "fake-test-key", "gemini-3.5-flash-lite",
            post=fake_post, cache_dir="",
        )
        self.assertEqual(len(prompts), 2)
        self.assertIn("PREVIEW:", prompts[0])
        self.assertIn("STORY:", prompts[0])
        self.assertIn("previous", prompts[0])
        self.assertEqual(info["provider_calls"], 2)
        self.assertEqual(info["cold_open"]["mode"],
                         "structured_two_story_preview")
        self.assertEqual(script.count(teaser), 1)
        self.assertTrue(
            script.index("Good morning") < script.index(teaser)
            < script.index("A source describes a development")
        )
        self.assertNotIn("STORY:", script)
        self.assertNotIn("PREVIEW:", script)
        self.assertIn("AI assistance", script)

    def test_unstructured_world_reply_does_not_fail_broadcast(self):
        teaser, rest, report = editorial33.split_preview(
            "An outlet published a report. "
            "It included an attributed statement."
        )
        self.assertEqual(teaser, "")
        self.assertEqual(rest,
                         "An outlet published a report. "
                         "It included an attributed statement.")
        self.assertEqual(report["preview_words"], 0)


class PronunciationWeatherTests(unittest.TestCase):
    def setUp(self):
        self.text = (
            "Good morning, San Antonio. "
            "An international story mentions San Antonio in passing. "
            "And now, a look at the weather in San Antonio. "
            "National Weather Service Austin/San Antonio reported "
            "a warning at 11:15AM CST. "
            "That's First Light: World Report."
        )

    def test_guided_alias_only_affects_weather_segment_near_end(self):
        spoken, review = pronunciation.prepare(
            self.text, san_antonio_mode="guided"
        )
        self.assertTrue(review["san_antonio_weather_alias_applied"])
        self.assertEqual(spoken.count("San Antonio"), 2)
        self.assertIn("weather in San An-TOH-nee-oh.", spoken)
        self.assertIn("Austin/San An-TOH-nee-oh", spoken)
        self.assertIn("11:15AM Central Standard Time", spoken)
        self.assertEqual(self.text.count("San Antonio"), 4)

    def test_original_mode_is_immediate_reversal(self):
        spoken, review = pronunciation.prepare(
            self.text, san_antonio_mode="original"
        )
        self.assertEqual(spoken.count("San Antonio"), 4)
        self.assertNotIn("San An-TOH-nee-oh", spoken)
        self.assertFalse(review["san_antonio_weather_alias_applied"])
        self.assertIn("Central Standard Time", spoken)

    def test_quoted_marker_after_colon_is_not_mistaken_for_weather(self):
        quotation = (
            "The report includes a quote: "
            "And now, a look at the weather in San Antonio. "
            "But the report isn't weather information."
        )
        edited, review = pronunciation.prepare(
            quotation, san_antonio_mode="guided"
        )
        self.assertEqual(edited, quotation)
        self.assertFalse(review["san_antonio_weather_alias_applied"])

    def test_real_tts_preparation_preserves_pause_and_intro(self):
        prepared = tts.delivery_text(self.text)
        self.assertIn("Good morning, San Antonio.", prepared)
        self.assertIn('<break time="0.65s" />', prepared)
        self.assertIn("San An-TOH-nee-oh", prepared)
        self.assertNotIn("weather in San Antonio.", prepared)
        self.assertEqual(
            " ".join(self.text.split()), " ".join(self.text.split())
        )

    def test_unsupported_guide_mode_is_refused(self):
        with self.assertRaises(ValueError):
            pronunciation.prepare(self.text, san_antonio_mode="<phoneme>")
        with patch.dict(os.environ, {
            "FIRST_LIGHT_SAN_ANTONIO_PRONUNCIATION": "original"
        }):
            self.assertNotIn("San An-TOH-nee-oh", tts.delivery_text(self.text))

    def test_workflow_allows_reversible_setting_without_voice_change(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        for workflow in ("daily.yml", "first-light-preview.yml"):
            content = (root / ".github/workflows" / workflow).read_text()
            self.assertIn("FIRST_LIGHT_SAN_ANTONIO_PRONUNCIATION", content)
            self.assertIn("vars.FIRST_LIGHT_SAN_ANTONIO_PRONUNCIATION",
                          content)
        self.assertEqual(tts.VOICE_ORDER[0][0], "Brian")
        self.assertEqual(tts.VOICE_ORDER[1][0], "Daniel")


if __name__ == "__main__":
    unittest.main()

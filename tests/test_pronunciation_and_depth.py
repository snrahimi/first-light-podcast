"""Offline newsroom 3.2 tests for pronunciations and evidence-backed depth."""
import json
import tempfile
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import patch, Mock

from src import pronunciation, elevenlabs_production as tts
from src import newsroom3, research33, broadcast32


class PronunciationTests(unittest.TestCase):
    def test_known_city_aliases_without_changing_source_script(self):
        text = (
            "Officials in Kyiv received a letter. Kyiv's mayor responded. "
            "Cartagena police described a local incident. "
            "A Kyivan resident was not quoted."
        )
        prepared, review = pronunciation.prepare(text)
        self.assertIn("Keev received", prepared)
        self.assertIn("Keev's mayor", prepared)
        self.assertIn("Car-ta-HEN-ah police", prepared)
        self.assertIn("Kyivan resident", prepared)
        self.assertEqual(review["explicit_city_or_name_rules_applied"],
                         ["Cartagena", "Kyiv"])
        self.assertTrue(review["source_transcript_unchanged"])
        self.assertIn("Kyiv's mayor", text)

    def test_local_san_antonio_cst_alert_is_expanded(self):
        text = (
            "And now, a look at the weather in San Antonio. "
            "The National Weather Service lists an active alert: "
            "Freeze Warning issued November 25 at 11:15AM CST until "
            "November 26 at 9:00AM CST. The warning remains in force."
        )
        prepared, review = pronunciation.prepare(text)
        self.assertEqual(prepared.count("Central Standard Time"), 2)
        self.assertEqual(review["expanded_time_zone_codes"], ["CST", "CST"])
        self.assertEqual(review["unresolved_time_zone_codes"], [])

    def test_ambiguous_cst_in_world_news_is_not_guessed(self):
        text = (
            "China's officials listed a meeting for 9:00AM CST. "
            "The report is not about San Antonio."
        )
        prepared, review = pronunciation.prepare(text)
        self.assertIn("9:00AM CST", prepared)
        self.assertEqual(review["unresolved_time_zone_codes"], ["CST"])

    def test_unambiguous_clock_offsets_expand_without_making_up_local_time(self):
        text = (
            "The session starts at 6:30 PM UTC. "
            "The broadcast is at 8:15AM EDT. "
            "Another report lists 10 AM IST."
        )
        prepared, review = pronunciation.prepare(text)
        self.assertIn("6:30 PM Coordinated Universal Time", prepared)
        self.assertIn("8:15AM Eastern Daylight Time", prepared)
        self.assertIn("10 AM IST", prepared)
        self.assertIn("IST", review["unresolved_time_zone_codes"])
        self.assertNotIn("Central Standard Time", prepared)

    def test_new_proper_name_requires_explicit_reviewed_glossary(self):
        testname = "Dr. Example Fictional"
        original = "Analysts met Dr. Example Fictional in Nairobi."
        baseline, _ = pronunciation.prepare(original, rules=[])
        self.assertEqual(baseline, original)
        revised, _ = pronunciation.prepare(
            original, rules=[("Example Fictional", "Ek-zam-pul Fik-shun-ul")]
        )
        self.assertIn("Dr. Ek-zam-pul Fik-shun-ul", revised)

    def test_malicious_alias_file_cannot_insert_ssml(self):
        variants = [
            {"version": 1, "rules": [{"written": "City", "spoken": "<phoneme>"}]},
            {"version": 1, "rules": [{"written": "City", "spoken": "one\nBREAK"}]},
            {"version": 1, "rules": [
                {"written": "Kyiv", "spoken": "Keev"},
                {"written": "kyiv", "spoken": "Kiev"},
            ]},
        ]
        for item in variants:
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "pronunciations.json"
                path.write_text(json.dumps(item), encoding="utf-8")
                with self.assertRaises(ValueError):
                    pronunciation.load_glossary(path)

    def test_speech_preparation_preserves_original_publication_text(self):
        original = (
            "In Kyiv, a new development was announced. "
            "And now, a look at the weather in San Antonio. "
            "The National Weather Service issued an advisory at 7:00AM CST."
        )
        prepared = tts.delivery_text(original)
        self.assertIn("Keev", prepared)
        self.assertIn("Central Standard Time", prepared)
        self.assertIn('<break time="0.65s" />', prepared)
        self.assertNotEqual(prepared, original)
        self.assertIn("Kyiv", original)
        self.assertEqual(tts.VOICE_ORDER[0][0], "Brian")
        self.assertEqual(tts.VOICE_ORDER[1][0], "Daniel")


class LeadDetailTests(unittest.TestCase):
    def sample_dossiers(self):
        lead = {
            "headline": "Coastal authorities review flood barriers and new warning systems",
            "category": "world",
            "sources": [{
                "publisher": "BBC World",
                "url": "https://www.bbc.com/news/example-flood",
                "title": "Coastal authorities review flood barriers",
                "summary": (
                    "The regional emergency agency reviewed flood barriers "
                    "after a series of storms reached the coast this month. "
                    "Officials plan to publish the technical assessment next "
                    "week before deciding whether repairs are required. "
                    "The government's notice also said that a second "
                    "public consultation would begin in December."
                ),
                "primary": False,
            }],
            "claim_ledger": [
                {
                    "publisher": "BBC World",
                    "source_url": "https://www.bbc.com/news/example-flood",
                    "evidence": (
                        "The regional emergency agency reviewed flood barriers "
                        "after a series of storms reached the coast this month."
                    ),
                    "claim": (
                        "The regional emergency agency reviewed flood barriers "
                        "after a series of storms reached the coast this month."
                    ),
                    "evidence_field": "summary",
                    "independently_verified": False,
                },
            ],
            "uncertainties": [],
            "reporting_comparison": {
                "independent_reporting_established": False,
                "different_numbers_need_review": False,
            },
            "official_context": [],
            "official_page_fetches_attempted": 0,
        }
        return {"Top world headlines": [lead],
                "Business and markets": []}

    def test_extra_complete_source_sentences_add_actual_detail(self):
        dossiers = self.sample_dossiers()
        attached = research33.enrich_lead_feed_context(dossiers)
        lead = dossiers["Top world headlines"][0]
        self.assertGreaterEqual(attached, 1)
        self.assertLessEqual(attached, 4)
        self.assertTrue(all(item["exact_excerpt"] in lead["sources"][0]["summary"]
                            for item in lead["lead_feed_context"]))
        self.assertTrue(all(item["exact_excerpt"].endswith(".")
                            for item in lead["lead_feed_context"]))
        stats = research33.validate_research(dossiers)
        self.assertEqual(stats["lead_feed_context_sentences"], attached)
        self.assertEqual(stats["independent_fact_checks"], 0)
        material = {"Top world headlines": [{"headline": lead["headline"],
                                             "evidence": []}],
                    "Business and markets": []}
        ready = research33.enrich_writer_material(dossiers, material)
        extra = ready["Top world headlines"][0]["feed_detail_context"]
        self.assertTrue(extra)
        self.assertIn("not_independently_verified", extra[0]["status"])
        beats = broadcast32._editorial_beat_plan(ready)
        self.assertGreater(beats[0]["additional_complete_rss_sentences"], 0)

    def test_truncated_feed_fragment_cannot_become_new_fact(self):
        self.assertEqual(
            research33._complete_rss_sentences(
                "Officials issued a statement but investigators have not"
            ), []
        )
        self.assertEqual(
            research33._complete_rss_sentences(
                "An official sentence that provides enough detail to be "
                "useful to a listener. The second sentence is cut off"
            ),
            ["An official sentence that provides enough detail to be "
             "useful to a listener."],
        )

    def test_tampered_source_quote_fails_exact_validation(self):
        dossiers = self.sample_dossiers()
        research33.enrich_lead_feed_context(dossiers)
        lead = dossiers["Top world headlines"][0]
        self.assertTrue(lead["lead_feed_context"])
        lead["lead_feed_context"][0]["exact_excerpt"] = (
            "A fabrication about 87 people with no source."
        )
        with self.assertRaisesRegex(ValueError, "exactly traceable"):
            research33.validate_research(dossiers)

    def test_untrusted_source_domain_does_not_enter_lead_context(self):
        dossiers = self.sample_dossiers()
        lead = dossiers["Top world headlines"][0]
        lead["sources"][0]["url"] = (
            "https://www.bbc.com.malicious.example/story"
        )
        self.assertEqual(research33.enrich_lead_feed_context(dossiers), 0)

    def test_numeric_gate_accepts_only_exact_validated_extra_context(self):
        dossiers = self.sample_dossiers()
        lead = dossiers["Top world headlines"][0]
        lead["sources"][0]["summary"] += (
            " The agency scheduled 17 public hearings after the decision was announced by officials."
        )
        research33.enrich_lead_feed_context(dossiers)
        research33.validate_research(dossiers)
        from datetime import datetime
        from zoneinfo import ZoneInfo
        now = datetime(2026, 11, 25, tzinfo=ZoneInfo("America/Chicago"))
        # The number 17 must appear *exactly* in an attached verified
        # source sentence before the existing numeric gate accepts it.
        quote = [x for x in lead["lead_feed_context"]
                 if "17" in x["exact_excerpt"]]
        self.assertTrue(quote)
        checked = newsroom3.script_numeric_gate(
            "A publisher reports 17 public hearings.", dossiers, {}, now
        )
        self.assertTrue(checked["numeric_tokens_approved"])
        with self.assertRaisesRegex(ValueError, "Unsupported numeric"):
            newsroom3.script_numeric_gate(
                "A publisher reports 91 public hearings.", dossiers, {}, now
            )

    def test_no_external_story_expansion_call_added(self):
        # RSS detail is drawn solely from already fetched trusted feed
        # summaries; cannot accidentally invoke a paid LLM or new scraper.
        self.assertEqual(
            research33.enrich_lead_feed_context(self.sample_dossiers()),
            research33.enrich_lead_feed_context(self.sample_dossiers()),
        )


if __name__ == "__main__":
    unittest.main()

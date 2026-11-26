"""Offline acceptance tests for Research Desk 3.5.

No network, TTS credits, publishing, or audio generation.
"""
from datetime import datetime
from types import SimpleNamespace
import unittest
from zoneinfo import ZoneInfo

from src import editorial, newsroom3, research33, research35, broadcast32
from tests_support import editorial_groups
from tests.test_research33 import nasa_dossier, html_response, DOCUMENT


NOW = datetime(2026, 11, 25, 5, tzinfo=ZoneInfo("America/Chicago"))


class SameEventTests(unittest.TestCase):
    def test_same_event_paraphrases_get_linked(self):
        examples = (
            ("United States announces sanctions on Lebanon banks",
             "Washington details Lebanon banking sanctions"),
            ("Security Council discusses Ukraine energy infrastructure attacks",
             "Security Council discusses Ukraine energy infrastructure attacks amid winter"),
            ("France introduces tariffs on China electric vehicles",
             "France levies tariffs on Chinese electric vehicles"),
        )
        for headline, related in examples:
            self.assertGreater(
                research35.match_score(headline, related, ""), 0,
                (headline, related),
            )
            self.assertEqual(
                research33._topic_match_score(headline, related),
                research35.match_score(headline, related),
            )

    def test_country_agency_or_sector_is_not_event_identity(self):
        unrelated = (
            ("US announces tariffs on Chinese electric vehicles",
             "EU announces tariffs on China food imports"),
            ("Ukraine energy infrastructure attacks kill civilians",
             "Ukraine energy summit discusses new transportation"),
            ("Flood warnings in Japan after storm",
             "Election results announced in Japan"),
            ("Global security council reports South Sudan famine",
             "Global security council reports South Sudan elections"),
            ("France cuts interest rates after inflation report",
             "France holds interest rates after inflation report"),
            ("EU announces tariffs on China imports",
             "EU lifts tariffs on China imports"),
        )
        for headline, other in unrelated:
            self.assertEqual(
                research35.match_score(headline, other, ""), 0.0,
                (headline, other),
            )

    def test_summary_cannot_rescue_a_country_only_match(self):
        score = research35.match_score(
            "Canada elections and parliamentary coalition",
            "Canada drought emergency and farming policy",
            "Canada's parliamentary committee heard a report about elections",
        )
        self.assertEqual(score, 0)
        review = research35.review_match(
            "Ukraine energy infrastructure attacks",
            "Ukraine energy infrastructure attacks amid winter",
        )
        self.assertTrue(review["same_event_candidate"])
        self.assertFalse(review["independent_corroboration_established"])

    def test_event_link_tracking_is_non_verification(self):
        title = "Security Council discusses Ukraine energy infrastructure attacks"
        story = {
            "category": "world", "title": title, "publisher": "BBC World",
            "url": "https://www.bbc.co.uk/news/abc1",
            "short_summary": "Security Council discussed attacks.",
            "published": "2026-11-25T07:00:00+00:00",
            "related_reports": [], "provenance": "publisher_rss",
        }
        d = newsroom3.build_dossiers({
            "rundown": {"Top world headlines": [story]}
        }, [])
        source = {
            "category": "world",
            "title": "Security Council discusses Ukraine energy infrastructure attacks amid winter",
            "summary": "The Council heard concerns about strikes and energy supply.",
            "publisher": "United Nations Press Releases",
            "url": "https://press.un.org/en/2026/sc-1001.doc.htm",
            "provenance": "primary_release_feed",
            "published": "2026-11-25T08:00:00+00:00",
            "age": 1,
        }
        n = research33.link_selected_feed_context(d, {"world": [source]})
        self.assertEqual(n, 1)
        status = d["Top world headlines"][0]["event_link35_review"]
        self.assertEqual(status["added_source_reports"], 1)
        self.assertEqual(status["same_event_candidates"], 1)
        self.assertIn("no truth check", status["method"])
        newsroom3.validate_dossiers(d)


class OfficialSourceTests(unittest.TestCase):
    def test_complete_official_sentences_never_end_mid_sentence(self):
        link = nasa_dossier()["sources"][0]["url"]
        d = research33.get_official_excerpt(
            link, "NASA News Releases",
            headline="NASA announces an instrument test",
            get=lambda url, **kw: html_response(url, DOCUMENT),
        )
        self.assertIsNotNone(d)
        self.assertTrue(d["excerpts"])
        self.assertTrue(all(sent.endswith((".", "!", "?"))
                            and sent in d["source_text"] for sent in d["excerpts"]))
        self.assertTrue(all(len(sent) <= 255 for sent in d["excerpts"]))

    def test_clipped_agency_fragment_cannot_be_used_as_quote(self):
        units = research33._complete_official_sentences([
            "The agency reported an extensive development, but its text was cut",
            "Investigators are conducting a detailed inspection of the "
            "affected area and will release a written report next week.",
        ])
        self.assertEqual(len(units), 1)
        self.assertTrue(units[0].endswith("."))

    def test_retrieval_budget_is_bounded_and_per_story(self):
        def copy_dossier(index):
            base = nasa_dossier()
            base["headline"] = "NASA announces an instrument test"
            # Different article URL ensures each document is an independent
            # eligible official link, rather than a duplicate.
            base["sources"][0]["url"] = (
                "https://www.nasa.gov/news-release/example-%d/" % index
            )
            return base
        d = {"Top world headlines": [copy_dossier(1)],
             "Science": [copy_dossier(i) for i in range(2, 9)]}
        for i in range(9, 13):
            doc = dict(d["Top world headlines"][0]["sources"][0])
            doc["url"] = "https://www.nasa.gov/news-release/example-%d/" % i
            d["Top world headlines"][0]["sources"].append(doc)
        calls = []
        def get(url, **kwargs):
            calls.append(url)
            return html_response(url, DOCUMENT)
        research33.enrich_dossiers(d, get=get)
        self.assertEqual(len(calls), 4)
        lead = d["Top world headlines"][0]["official_retrieval35"]
        self.assertEqual(lead["eligible_issuer_links"], 5)
        self.assertEqual(lead["attempted"], 2)
        self.assertEqual(lead["skipped_due_to_global_or_story_cap"], 3)
        stats = research33.validate_research(d)
        self.assertGreaterEqual(stats["official_urls_skipped_by_cap"], 3)
        self.assertEqual(stats["official_document_fetches_attempted"], 4)

    def test_unavailable_issuer_is_counted_without_source_fabrication(self):
        card = nasa_dossier()
        d = {"Science": [card]}
        research33.enrich_dossiers(
            d, get=lambda url, **kw: html_response(url, DOCUMENT, 503)
        )
        stats = research33.validate_research(d)
        self.assertEqual(stats["official_documents_checked"], 0)
        self.assertEqual(stats["official_urls_rejected_or_unavailable"], 1)
        self.assertEqual(card["official_context"], [])


class ScopedNumberTests(unittest.TestCase):
    def _dossiers(self):
        def card(pub, url, excerpt):
            return {
                "claim_ledger": [{"evidence": excerpt}],
                "official_context": [], "lead_feed_context": [],
            }
        return {
            "Top world headlines": [
                card("BBC", "https://bbc.com/a",
                     "According to a publisher, 14 countries announced sanctions.")
            ],
            "Business and markets": [
                card("NPR", "https://npr.org/b",
                     "According to a publisher, 87 financial institutions responded.")
            ],
        }

    def test_no_cross_section_number_laundering(self):
        d = self._dossiers()
        self.assertTrue(newsroom3.script_numeric_gate(
            "A report said 87 institutions responded.", d, {}, NOW
        )["numeric_tokens_approved"])
        with self.assertRaisesRegex(ValueError, "87"):
            newsroom3.script_numeric_gate(
                "World reporting cites 87 institutions.", d, {}, NOW,
                scope_sections=("Top world headlines",),
            )
        self.assertTrue(newsroom3.script_numeric_gate(
            "A report cited fourteen countries.", d, {}, NOW,
            scope_sections=("Top world headlines",),
        )["numeric_tokens_approved"])

    def test_unsourced_spoken_figures_are_blocked(self):
        d = self._dossiers()
        for claim in (
            "The report mentioned nineteen countries.",
            "The report mentioned forty five countries.",
            "A statement listed twenty-one institutions.",
        ):
            with self.assertRaisesRegex(ValueError, "Unsupported numeric"):
                newsroom3.script_numeric_gate(
                    claim, d, {}, NOW, scope_sections=("Top world headlines",)
                )

    def test_existing_weather_rounding_and_dates_survive_global_gate(self):
        d = self._dossiers()
        weather = {"temperature_f": 48.6, "high_f": 58,
                   "nws_active_alerts": []}
        result = newsroom3.script_numeric_gate(
            "Good morning. It is November 25, 2026. "
            "The temperature is 49 degrees.", d, weather, NOW
        )
        self.assertTrue(result["numeric_tokens_approved"])

    def test_reject_unsupported_world_number_before_second_paid_call(self):
        edition = editorial.curate(editorial_groups(), [], NOW)
        d = newsroom3.build_dossiers(edition, [])
        for section in d.values():
            for card in section:
                card["reporting_comparison"] = {
                    "different_numbers_need_review": False,
                    "independent_reporting_established": False,
                }
                card["official_context"] = []
        calls = []
        def post(url, **kwargs):
            calls.append(url)
            payload = (
                "BBC World describes ongoing negotiations and official "
                "statements without a verified final outcome. " * 18
                + "The report also lists nineteen new countries."
            )
            return SimpleNamespace(
                status_code=200,
                json=lambda: {"candidates": [{"content": {
                    "parts": [{"text": payload}]
                }}]},
            )
        script, report = broadcast32.generated_script(
            NOW, edition, d, "Local weather unavailable.",
            "test-only", "gemini-3.5-flash-lite",
            post=post, cache_dir="",
        )
        self.assertIsNone(script)
        self.assertEqual(report["reason"], "world_numeric_evidence_gate")
        self.assertEqual(report["provider_calls"], 1)
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()

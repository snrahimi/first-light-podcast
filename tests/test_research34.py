"""Research Desk 3.4: offline source-depth and editor QA tests."""
import unittest
from unittest.mock import patch
from datetime import datetime
from zoneinfo import ZoneInfo

from src import research34, first_light, research33, newsroom3, editorial


def source_card():
    source = {
        "publisher": "BBC World",
        "url": "https://www.bbc.com/news/example-test",
        "title": "Regional water officials publish a new inspection report",
        "summary": (
            "Regional officials issued a report on water levels after "
            "a series of storms affected the coastline earlier this month. "
            "The agency said the review will continue until local "
            "engineers deliver their findings next week."
        ),
        "primary": False,
    }
    ledger = [{
        "publisher": source["publisher"], "source_url": source["url"],
        "evidence": source["title"], "claim": source["title"],
        "evidence_field": "title", "independently_verified": False,
    }, {
        "publisher": source["publisher"], "source_url": source["url"],
        "evidence": newsroom3.clean(source["summary"], 240),
        "claim": newsroom3.clean(source["summary"], 240),
        "evidence_field": "summary", "independently_verified": False,
    }]
    return {
        "headline": source["title"],
        "sources": [source], "claim_ledger": ledger,
        "lead_feed_context": [{
            "publisher": source["publisher"], "url": source["url"],
            "exact_excerpt": (
                "The agency said the review will continue until local "
                "engineers deliver their findings next week."
            ),
        }],
        "official_context": [],
        "previous_coverage": "Water levels were studied last week",
        "reporting_comparison": {"different_numbers_need_review": False},
        "editorial_review": {"sensitive_claims_present": False},
    }


class Desk34Tests(unittest.TestCase):
    def test_additional_world_feeds_are_allowlisted_and_https(self):
        publishers = {
            item[1]: item[2] for item in first_light.RSS_FEEDS
        }
        for name in ("Deutsche Welle", "France 24",
                     "ABC Australia", "PBS News"):
            self.assertIn(name, publishers)
            self.assertTrue(publishers[name].startswith("https://"))
        canonical = {
            "Deutsche Welle": "https://www.dw.com/en/article",
            "France 24": "https://www.france24.com/en/article",
            "ABC Australia": "https://www.abc.net.au/news/article",
            "PBS News": "https://www.pbs.org/newshour/article",
        }
        for name, link in canonical.items():
            self.assertTrue(first_light._trusted_feed_link(name, link))
            self.assertTrue(research33._trusted_feed_candidate({
                "publisher": name, "url": link,
                "provenance": "publisher_rss",
            }))
            self.assertFalse(first_light._trusted_feed_link(
                name, link.replace("https://www.", "https://fake.")
            ))

    def test_coverage_reports_source_diversity_not_truth(self):
        groups = {
            "world": [
                {"publisher": "BBC World"},
                {"publisher": "France 24"},
                {"publisher": "Deutsche Welle"},
            ],
            "business": [{"publisher": "BBC Business"}],
            "science": [], "tech": [],
        }
        report = research34.source_coverage(groups)
        self.assertEqual(report["categories"]["world"]["distinct_publishers"], 3)
        self.assertFalse(report["fact_verification_claimed"])
        self.assertIn("No fresh science", " ".join(report["review_flags"]))

    def test_lead_card_contains_exact_source_snippets_with_traceable_links(self):
        dossier = source_card()
        cards = research34.lead_research_cards({
            "Top world headlines": [dossier],
        })
        self.assertEqual(len(cards), 1)
        card = cards[0]
        self.assertEqual(card["lead_number"], 1)
        self.assertEqual(card["independently_verified_facts"], 0)
        self.assertGreaterEqual(card["source_verified_excerpt_count"], 2)
        self.assertEqual(card["source_count"], 1)
        self.assertTrue(card["attributed_possible_next_steps"])
        self.assertTrue(card["review_flags"])
        for snippet in card["claims"]:
            self.assertEqual(snippet["publisher"], "BBC World")
            self.assertIn(snippet["exact_excerpt"],
                          dossier["sources"][0]["title"] + " " +
                          dossier["sources"][0]["summary"])

    def test_no_fabricated_excerpt_allowed(self):
        card = source_card()
        card["claim_ledger"][0]["evidence"] = (
            "An invented event affected 70000 residents."
        )
        with self.assertRaisesRegex(ValueError, "verbatim"):
            research34.lead_research_cards({
                "Top world headlines": [card]
            })

    def test_no_insecure_source_url(self):
        card = source_card()
        link = "http://example.org/news"
        card["sources"][0]["url"] = link
        for claim in card["claim_ledger"]:
            claim["source_url"] = link
        card["lead_feed_context"][0]["url"] = link
        with self.assertRaisesRegex(ValueError, "valid HTTPS"):
            research34.lead_research_cards({
                "Top world headlines": [card]
            })

    def test_writer_card_match_and_reject_mismatched_lead(self):
        card = research34.lead_research_cards({
            "Top world headlines": [source_card()]
        })[0]
        material = {"Top world headlines": [
            {"headline": card["headline"], "evidence": []}
        ]}
        revised = research34.attach_writer_research(material, [card])
        self.assertEqual(revised["Top world headlines"][0]
                         ["research_desk34"]["lead_number"], 1)
        with self.assertRaisesRegex(ValueError, "order/headline"):
            research34.attach_writer_research({
                "Top world headlines": [{"headline": "Different story"}]
            }, [card])

    def test_editorial_detects_fabricated_interviews_not_source_truth(self):
        card = research34.lead_research_cards({
            "Top world headlines": [source_card()]
        })[0]
        coverage = research34.source_coverage({
            "world": [{"publisher": "BBC World"}], "business": [],
            "science": [], "tech": [],
        })
        safe = research34.editorial_review(
            "BBC World reports that officials issued a statement.", [card],
            coverage
        )
        self.assertIsNone(safe["hard_reject_reason"])
        self.assertFalse(safe["underlying_events_independently_fact_checked"])
        reject = research34.editorial_review(
            "I interviewed the minister in the field today.", [card],
            coverage
        )
        self.assertTrue(reject["fabricated_fieldwork_language_detected"])
        self.assertEqual(reject["hard_reject_reason"],
                         "fabricated_original_fieldwork_or_independent_verification")

    def test_desk_does_not_fetch_articles_or_call_llm(self):
        with patch("src.research34.research33.get_official_excerpt") as http:
            research34.lead_research_cards({
                "Top world headlines": [source_card()]
            })
            http.assert_not_called()


if __name__ == "__main__":
    unittest.main()

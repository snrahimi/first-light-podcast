"""Regression tests for First Light editorial selection and carryover memory."""
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from src import editorial


def headline(title, category="world", publisher="Outlet A", age=3, summary=""):
    import re
    return {
        "title": title, "category": category, "publisher": publisher,
        "age": age, "summary": summary or title,
        "url": "https://example.org/" +
               re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") +
               "?publisher=" + publisher.replace(" ", ""),
        "published": "2026-11-23T09:30:00+00:00",
    }


def standard_groups():
    return {
        "world": [
            headline("Ukraine peace talks continue as European leaders meet", publisher="Outlet A"),
            headline("European leaders meet to continue Ukraine peace talks", publisher="Outlet B"),
            headline("Japan election results bring parliamentary coalition discussions"),
            headline("Brazil leaders negotiate new regional trade agreement"),
            headline("Sudan relief agencies report humanitarian supplies delayed"),
            headline("Canada announces changes to national transport rules"),
        ],
        "business": [
            headline("Global inflation pressures prompt central bank discussion", "business"),
            headline("Technology companies report quarterly earnings results", "business")
        ],
        "science": [
            headline("Scientists publish new observations from Antarctic ice samples", "science")
        ],
        "tech": [
            headline("Cybersecurity researchers disclose major software vulnerability", "tech")
        ],
    }


class EditorialTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 23, 5, 0,
                            tzinfo=ZoneInfo("America/Chicago"))

    def test_related_headlines_require_multiple_significant_terms(self):
        self.assertTrue(editorial.same_topic(
            "Ukraine peace talks continue as European leaders meet",
            "European leaders meet to continue Ukraine peace talks"))
        self.assertFalse(editorial.same_topic(
            "Ukraine peace talks continue as European leaders meet",
            "Japan election results bring parliamentary coalition discussions"))

    def test_cluster_does_not_call_one_publisher_independent(self):
        groups = standard_groups()
        results = editorial.cluster_stories(groups)
        doubles = [c for c in results if c["multiple_publishers"]]
        self.assertGreaterEqual(len(doubles), 1)
        self.assertEqual(len(doubles[0]["publishers"]), 2)

    def test_prior_episode_metadata_round_trip(self):
        edition = editorial.curate(standard_groups(), [], self.now)
        note = editorial.memory_note(edition)
        prior = [{"tag_name": "first-light-2026-11-22", "body": note}]
        history = editorial.read_prior_releases(prior, self.now)
        self.assertGreaterEqual(len(history), 5)
        self.assertTrue(all(x["date"] == self.now.date().isoformat() for x in history))

    def test_repeat_headlines_dropped(self):
        groups = standard_groups()
        memory = [{
            "title": "Scientists publish new observations from Antarctic ice samples",
            "date": "2026-11-22",
            "category": "science",
        }]
        edition = editorial.curate(groups, memory, self.now)
        headlines = [
            s["title"] for stories in edition["rundown"].values()
            for s in stories
        ]
        self.assertNotIn(memory[0]["title"], headlines)
        self.assertGreaterEqual(edition["repeated_topics_avoided"], 1)

    def test_rundown_is_short_and_source_attributed(self):
        edition = editorial.curate(standard_groups(), [], self.now)
        self.assertGreaterEqual(edition["count"], 5)
        self.assertLessEqual(edition["count"], 8)
        all_stories = [
            s for chapter in edition["rundown"].values() for s in chapter
        ]
        self.assertEqual(len(all_stories), edition["count"])
        self.assertTrue(all(s["publisher"] and s["url"].startswith("https://")
                            for s in all_stories))

    def test_editorial_notes_do_not_claim_independent_verification(self):
        edition = editorial.curate(standard_groups(), [], self.now)
        self.assertIn("not independent verification",
                      editorial.source_notes(edition))
        self.assertGreater(len(editorial.edition_sources(edition)), 5)

    def test_pronunciation_expands_standard_abbreviations(self):
        self.assertEqual(
            editorial.speaking_text("The NWS checked the U.S. GDP and AI."),
            "The National Weather Service checked the United States "
            "gross domestic product and artificial intelligence."
        )

    def test_script_gate_requires_identity_and_date(self):
        edition = editorial.curate(standard_groups(), [], self.now)
        valid = ("Good morning, this is First Light in San Antonio, 2026. "
                 "Here are today's international world stories. " +
                 "Verified facts should be attributed to sources. " * 100)
        result = editorial.script_quality(valid, edition, self.now)
        self.assertGreater(result["script_words"], 640)
        with self.assertRaises(ValueError):
            editorial.script_quality("Hello", edition, self.now)

    def test_malformed_history_cannot_crash_editorial_planning(self):
        broken = [{"tag_name": "first-light-2026-11-22",
                   "body": "<!-- FIRST_LIGHT_MEMORY_V1:not-json -->"}]
        self.assertEqual(editorial.read_prior_releases(broken, self.now), [])


if __name__ == "__main__":
    unittest.main()

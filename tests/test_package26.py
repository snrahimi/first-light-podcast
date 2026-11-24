"""Package 2+.6: sourced depth, fixed-call writer QA, lead diversity."""
import unittest
from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from src import broadcast32, editorial, newsroom3, quality2plus, research33
from tests_support import editorial_groups

NOW = datetime(2026, 11, 24, 5, tzinfo=ZoneInfo("America/Chicago"))


def feed(title, category="world", publisher="Outlet A", age=1):
    import re
    return {
        "title": title, "summary": title,
        "category": category, "publisher": publisher,
        "published": "2026-11-24T10:00:00+00:00",
        "url": "https://example.org/" + re.sub(r"[^a-z0-9]+", "-", title.lower())
        + "?publisher=" + publisher.replace(" ", ""),
        "age": age,
    }


def official_response(url, body):
    return SimpleNamespace(
        status_code=200, url=url,
        headers={"Content-Type": "text/html"},
        content=body.encode("utf-8"),
    )


def _edition_with_dossiers():
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


def reply(text):
    return SimpleNamespace(
        status_code=200,
        json=lambda: {"candidates": [{"content": {"parts": [{"text": text}]}}]},
    )


class Package26Tests(unittest.TestCase):
    def test_deeper_official_excerpts_include_adjacent_subject_paragraph(self):
        url = "https://www.nasa.gov/news-release/orbital-test/"
        html = """<html><main>
        <h1>NASA announces spacecraft instrument test</h1>
        <p>NASA engineers finished the spacecraft instrument test and
        published a summary of the laboratory observations for review.</p>
        <p>The instrument review will assess the durability of components
        before a possible next set of checks is scheduled.</p>
        <p>A separate article about community sports leagues contains
        unrelated announcements and event details.</p>
        </main></html>"""
        doc = research33.get_official_excerpt(
            url, "NASA News Releases",
            headline="NASA announces spacecraft instrument test",
            get=lambda u, **kw: official_response(u, html),
        )
        self.assertIsNotNone(doc)
        self.assertIn("durability of components", doc["source_text"])
        self.assertNotIn("community sports leagues", doc["source_text"])
        self.assertGreaterEqual(len(doc["excerpts"]), 2)
        self.assertLessEqual(len(doc["excerpts"]), research33.MAX_OFFICIAL_EXCERPTS)
        self.assertTrue(all(e in doc["source_text"] for e in doc["excerpts"]))

    def test_research_does_not_allow_unrelated_headline_laundering(self):
        url = "https://press.un.org/en/2026/sc123.doc.htm"
        body = """<html><main>
        <h1>Security Council discusses energy attacks in Ukraine</h1>
        <p>Security Council delegates reviewed reports about energy
        infrastructure attacks in Ukraine and planned a further meeting.</p>
        <h2>Unrelated committee event</h2>
        <p>The committee discussed different regional agricultural trade issues.</p>
        </main></html>"""
        doc = research33.get_official_excerpt(
            url, "United Nations Press Releases",
            headline="Security Council discusses energy attacks in Ukraine",
            get=lambda u, **kw: official_response(u, body),
        )
        self.assertIsNotNone(doc)
        self.assertNotIn("agricultural trade issues", doc["source_text"])
        self.assertNotIn("Unrelated committee", doc["source_text"])

    def test_research_wider_excerpt_limit_and_no_publisher_article_fetch(self):
        self.assertEqual(research33.MAX_DOCUMENTS, 4)
        self.assertEqual(research33.MAX_RELATED_LEADS, 3)
        self.assertEqual(research33.MAX_RELATED_OTHER, 2)
        self.assertFalse(research33._issuer_matches(
            "https://www.npr.org/news", "NASA News Releases"
        ))

    def test_two_world_leads_prefer_different_publishers_near_impact(self):
        groups = editorial_groups()
        groups["world"] = [
            feed("Sudan peace talks follow conflict and humanitarian emergency",
                 publisher="United Nations Press Releases", age=1),
            feed("Ukraine peace talks prompt new ceasefire discussions",
                 publisher="United Nations Press Releases", age=2),
            feed("Brazil announces national transport improvements",
                 publisher="BBC World", age=12),
            feed("Japan court reviews regional labor law changes",
                 publisher="NPR World", age=29),
            feed("Canada authorities discuss local transport changes",
                 publisher="BBC World", age=31),
        ]
        edition = editorial.curate(groups, [], NOW)
        leads = edition["rundown"]["Top world headlines"]
        self.assertEqual(len(leads), 2)
        self.assertEqual(edition["distinct_lead_publishers"], 2)
        self.assertEqual(len({s["publisher"] for s in leads}), 2)

    def test_major_high_impact_can_still_override_publisher_nudge(self):
        groups = editorial_groups()
        groups["world"] = [
            feed("Sudan ceasefire agreed after emergency talks and crisis",
                 publisher="United Nations Press Releases", age=1),
            feed("Ukraine peace ceasefire agreement ends weeks of negotiations",
                 publisher="United Nations Press Releases", age=1),
            feed("Canada university opens regional arts gallery",
                 publisher="BBC World", age=30),
            feed("Brazil community group discusses city arts",
                 publisher="NPR World", age=31),
        ]
        edition = editorial.curate(groups, [], NOW)
        self.assertEqual(edition["distinct_lead_publishers"], 1)

    def test_international_business_economics_ranks_above_trivial(self):
        groups = editorial_groups()
        groups["business"] = [
            feed("Celebrity mansion luxury estate lists for sale",
                 "business", "Outlet A", age=1),
            feed("Global inflation and trade tariffs prompt central bank review",
                 "business", "Outlet B", age=7),
            feed("Retailer unveils limited seasonal product packaging",
                 "business", "Outlet C", age=2),
        ]
        edition = editorial.curate(groups, [], NOW)
        self.assertIn("inflation", edition["rundown"]["Business and markets"][0]["title"])

    def test_material_budget_scales_with_distinct_reporting(self):
        sparse = {"Top world headlines": [{
            "headline": "Sparse story", "evidence": [
                {"publisher": "BBC", "text": "One short report."}],
            "official_context": [],
        }]}
        rich = {"Top world headlines": [{
            "headline": "Rich story", "evidence": [
                {"publisher": "BBC",
                 "text": "A first substantial report describes a planned " +
                         "official consultation and the subjects of the meeting."},
                {"publisher": "NPR",
                 "text": "A second substantive feed report describes the " +
                         "participants and a later session with additional goals."},
            ],
            "official_context": [
                {"agency": "NASA", "quoted_excerpt":
                 "An official agency release presents follow-up information."},
            ],
        }]}
        a = broadcast32._editorial_beat_plan(sparse)[0]
        b = broadcast32._editorial_beat_plan(rich)[0]
        self.assertGreater(b["suggested_words_if_supported"],
                           a["suggested_words_if_supported"])
        self.assertEqual(b["official_agency_excerpt_count"], 1)
        self.assertEqual(b["substantive_source_excerpts"], 2)

    def test_short_gemini_sections_are_flagged_without_extra_model_calls(self):
        edition, dossiers = _edition_with_dossiers()
        world = "BBC reports international developments with no confirmed final outcome. " * 17
        others = "NPR reports economic and scientific developments with limited evidence. " * 16
        calls = []
        def post(url, **kwargs):
            calls.append(url)
            return reply(world if len(calls) == 1 else others)
        script, info = broadcast32.generated_script(
            NOW, edition, dossiers,
            "Local forecast unavailable.", "test-key", "gemini-3.5-flash-lite",
            post=post,
        )
        self.assertIsNotNone(script)
        self.assertEqual(len(calls), 2)
        self.assertEqual(info["provider_calls"], 2)
        self.assertTrue(info["under_delivered_sections"])
        self.assertTrue(all(x["ratio"] < 0.65
                            for x in info["under_delivered_sections"]))
        self.assertEqual(info["cache_hits"], 0)

        edition["script_quality"] = {"draft": info}
        score = quality2plus.scorecard(
            script, dossiers, edition,
            {"nws_alert_check": "checked", "nws_active_alerts": []},
            "Gemini segmented evidence-led 3.2",
        )
        self.assertTrue(score["under_delivered_writer_sections"])
        self.assertIn("Substantially under-delivered Gemini sections:",
                      quality2plus.public_notes(score))
        self.assertTrue(score["needs_editorial_attention"])


if __name__ == "__main__":
    unittest.main()

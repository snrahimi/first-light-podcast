"""Offline Newsroom 3.0 tests. No live API calls or paid models."""
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch, MagicMock
from zoneinfo import ZoneInfo
import unittest

from src import editorial, newsroom3
from tests_support import editorial_groups

NOW = datetime(2026, 11, 23, 5, tzinfo=ZoneInfo("America/Chicago"))


def response(content=b"", obj=None):
    return SimpleNamespace(
        content=content,
        json=lambda: obj or {},
        raise_for_status=lambda: None,
    )


class Newsroom3Tests(unittest.TestCase):
    def test_strict_link_validation_rejects_domain_lookalikes(self):
        self.assertTrue(newsroom3.host_ok(
            "https://www.nasa.gov/news-release/test", ("nasa.gov",)))
        self.assertFalse(newsroom3.host_ok(
            "https://nasa.gov.fake.example/report", ("nasa.gov",)))
        self.assertFalse(newsroom3.host_ok(
            "http://nasa.gov/report", ("nasa.gov",)))
        self.assertFalse(newsroom3.host_ok(
            "https://user:pass@nasa.gov/report", ("nasa.gov",)))

    def test_bounded_gdelt_is_discovery_only(self):
        payload = {"articles": [
            {"url": "https://www.dw.com/en/major-event/a-123",
             "title": "Global summit election results and regional reactions"},
            {"url": "https://bogus.example/events",
             "title": "Unverified unrelated claim"},
        ]}
        with patch.dict("os.environ", {"NEWSROOM_GDELT_ENABLED": "true"}):
            got = newsroom3.discover_gdelt(NOW, get=lambda *a, **kw:
                                           response(obj=payload))
        self.assertEqual(len(got), 1)
        self.assertTrue(got[0]["discovery_only"])
        self.assertNotIn("summary", got[0])

    def test_gdelt_outage_is_not_fatal(self):
        from requests.exceptions import ReadTimeout
        def failing_get(*args, **kwargs):
            raise ReadTimeout("simulated outage")
        self.assertEqual(newsroom3.discover_gdelt(NOW, get=failing_get), [])

    def test_primary_rss_release_parsed_with_real_publisher(self):
        rss = b"""<?xml version="1.0"?><rss version="2.0"><channel>
        <title>NASA</title><item><title>NASA tests a new spacecraft component</title>
        <link>https://www.nasa.gov/news-release/new-spacecraft/</link>
        <pubDate>Mon, 23 Nov 2026 09:00:00 GMT</pubDate>
        <description>New spacecraft component tested in lab.</description>
        </item></channel></rss>"""
        def mocked(url, **kw):
            if "nasa.gov" in url:
                return response(content=rss)
            return response(content=b"<rss><channel></channel></rss>")
        results = newsroom3.primary_rss_candidates(NOW, get=mocked)
        self.assertEqual(len(results["science"]), 1)
        self.assertEqual(results["science"][0]["provenance"], "primary_release_feed")
        self.assertEqual(results["science"][0]["publisher"], "NASA News Releases")

    def test_cisa_recent_dates_only(self):
        data = {"vulnerabilities": [
            {"dateAdded": "2026-11-23", "cveID": "CVE-2026-12345",
             "vulnerabilityName": "Example Exploited Software Vulnerability",
             "shortDescription": "CISA lists active exploitation."},
            {"dateAdded": "2026-06-23", "cveID": "CVE-2026-99999",
             "vulnerabilityName": "Old issue", "shortDescription": "Outdated"},
        ]}
        records = newsroom3.cisa_kev_candidates(
            NOW, get=lambda *a, **k: response(obj=data))
        self.assertEqual(len(records), 1)
        self.assertIn("CVE-2026-12345", records[0]["title"])

    def test_official_feeds_enrich_existing_candidates(self):
        groups = editorial_groups()
        primary = {x: [] for x in groups}
        primary["science"] = [{
            "publisher": "NASA", "url": "https://www.nasa.gov/news-release/x",
            "title": "NASA confirms scientific results from spacecraft instruments",
            "category": "science", "summary": "Official release",
            "published": "2026-11-23T09:00:00+00:00", "age": 1,
            "provenance": "primary_release_feed",
        }]
        merged = newsroom3.augment_groups(groups, primary)
        self.assertEqual(len(merged["science"]), len(groups["science"]) + 1)
        self.assertEqual(len(groups["science"]), 1)

    def test_evidence_ledger_uses_exact_excerpt_not_discovery(self):
        edition = editorial.curate(editorial_groups(), [], NOW)
        leads = [{
            "title": "Ukraine peace talks continue as European leaders meet",
            "url": "https://www.dw.com/en/ukraine-world/a-1",
            "discovery_only": True,
        }]
        dossiers = newsroom3.build_dossiers(edition, leads)
        stats = newsroom3.validate_dossiers(dossiers)
        self.assertGreater(stats["attributed_claims"], 4)
        self.assertEqual(stats["independently_verified_facts"], 0)
        self.assertTrue(any(
            d["discovery_leads"]
            for chapter in dossiers.values() for d in chapter
        ))
        material = newsroom3.writer_material(dossiers)
        self.assertNotIn("discovery_leads", str(material))
        self.assertNotIn("www.dw.com", str(material))

    def test_claim_tampering_is_rejected(self):
        edition = editorial.curate(editorial_groups(), [], NOW)
        dossiers = newsroom3.build_dossiers(edition, [])
        first = next(x for ch in dossiers.values() for x in ch)
        first["claim_ledger"][0]["claim"] = "Falsified news claim about global conflict"
        with self.assertRaises(ValueError):
            newsroom3.validate_dossiers(dossiers)

    def test_unverified_language_and_new_numbers_are_blocked(self):
        edition = editorial.curate(editorial_groups(), [], NOW)
        dossiers = newsroom3.build_dossiers(edition, [])
        weather = {"high_f": 76}
        with self.assertRaisesRegex(ValueError, "Unsupported numeric"):
            newsroom3.script_numeric_gate(
                "First Light reports 999999 new cases in 2026.", dossiers,
                weather, NOW)
        with self.assertRaisesRegex(ValueError, "overclaims"):
            newsroom3.script_numeric_gate(
                "First Light: we independently verified everything.", dossiers,
                weather, NOW)
        good = newsroom3.script_numeric_gate(
            "First Light World Report in 2026. San Antonio near 76 degrees.",
            dossiers, weather, NOW)
        self.assertTrue(good["numeric_tokens_approved"])

    def test_public_audit_is_explicit_about_method(self):
        edition = editorial.curate(editorial_groups(), [], NOW)
        dossiers = newsroom3.build_dossiers(edition, [])
        stats = newsroom3.validate_dossiers(dossiers)
        data = newsroom3.audit_export(dossiers, stats, [])
        self.assertEqual(data["independently_verified_facts"], 0)
        self.assertIn("NOT", data["corroboration"])
        self.assertIn("GDELT Project", data["discovery"]["source"])
        self.assertIn("not independent factual verification",
                      newsroom3.audit_notes(dossiers, stats))

    def test_punctuation_comma_not_counted_as_an_unsupported_number(self):
        edition = editorial.curate(editorial_groups(), [], NOW)
        dossiers = newsroom3.build_dossiers(edition, [])
        text = ("Good morning San Antonio, this is First Light World Report "
                "on November 23, 2026. Here is the world report.")
        self.assertTrue(newsroom3.script_numeric_gate(
            text, dossiers, {}, NOW)["numeric_tokens_approved"])

    def test_evidence_scoped_writer_rewrites_short_draft_at_most_once(self):
        from src.first_light import optional_gemini_script
        edition = editorial.curate(editorial_groups(), [], NOW)
        short = ("Good morning, San Antonio, this is First Light: World Report "
                 "on November 23, 2026. World headlines follow. "
                 + "Our sources offer limited published headline details. " * 78)
        revised = ("Good morning, San Antonio, this is First Light: World Report "
                   "on November 23, 2026. World headlines follow. "
                   + "Our sources offer limited published headline details. " * 115)
        def reply(script):
            return SimpleNamespace(
                status_code=200,
                json=lambda: {"candidates": [{"content": {
                    "parts": [{"text": script}]
                }}]},
                raise_for_status=lambda: None,
            )
        with patch.dict("os.environ", {
            "GEMINI_API_KEY": "test-only", "GEMINI_MODEL": "gemini-3.5-flash-lite"
        }), patch("src.first_light.requests.post", side_effect=[
            reply(short), reply(revised)
        ]) as post:
            result = optional_gemini_script(NOW, edition, {}, {})
        self.assertEqual(result, revised.replace("\n", " ").strip())
        self.assertEqual(post.call_count, 2)
        self.assertIn("gemini-3.5-flash-lite", post.call_args_list[0].args[0])


if __name__ == "__main__":
    unittest.main()

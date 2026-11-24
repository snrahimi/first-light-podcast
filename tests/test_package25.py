"""Package 2+.5 offline regressions: no paid failover or speculative filler."""
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo
import xml.etree.ElementTree as ET

from src import broadcast32, editorial, first_light, newsroom3
from tests.test_editorial import headline, standard_groups

NOW = datetime(2026, 11, 24, 6, tzinfo=ZoneInfo("America/Chicago"))


class Package25Tests(unittest.TestCase):
    def _edition(self, day=NOW):
        return editorial.curate(standard_groups(), [], day)

    def test_release_history_retries_temporary_503_then_recovers(self):
        previous = NOW - timedelta(days=1)
        note = editorial.memory_note(self._edition(previous))
        attempts, delays = [], []
        def fake_get(url, **kwargs):
            attempts.append(url)
            if len(attempts) == 1:
                return SimpleNamespace(status_code=503, headers={"Retry-After": "3"})
            return SimpleNamespace(
                status_code=200, headers={}, json=lambda: [{
                    "tag_name": "first-light-2026-11-23", "body": note
                }],
            )
        history = editorial.load_history(
            "snrahimi/first-light-podcast", "not-a-real-token", NOW,
            get=fake_get, sleep=delays.append)
        self.assertEqual(len(attempts), 2)
        self.assertEqual(len(delays), 1)
        self.assertGreater(len(history), 2)

    def test_pages_backup_when_api_forbidden(self):
        prev = NOW - timedelta(days=1)
        edition = self._edition(prev)
        doc = editorial.memory_snapshot(edition, [], prev)
        urls = []
        def fake_get(url, **kw):
            urls.append(url)
            if "/releases" in url:
                return SimpleNamespace(status_code=403, headers={})
            return SimpleNamespace(
                status_code=200, json=lambda: doc,
                raise_for_status=lambda: None,
            )
        history = editorial.load_history(
            "snrahimi/first-light-podcast", "test-token", NOW,
            get=fake_get, sleep=lambda _: None,
            fallback_url="https://snrahimi.github.io/first-light-podcast/memory.json")
        self.assertEqual(len(urls), 2)
        self.assertGreater(len(history), 0)
        self.assertTrue(all(x["date"] == prev.date().isoformat() for x in history))

    def test_pages_memory_rejects_future_or_stale_snapshot(self):
        edition = self._edition(NOW)
        doc = editorial.memory_snapshot(edition, [], NOW)
        self.assertEqual(editorial._read_memory_snapshot(doc, NOW), [])
        self.assertEqual(editorial._read_memory_snapshot(
            doc, NOW + timedelta(days=9)), [])
        self.assertEqual(editorial._read_memory_snapshot({
            "version": 1, "through_date": "bad", "topics": "invalid"
        }, NOW), [])

    def test_world_leads_prefer_distinct_regions_when_impact_is_close(self):
        groups = standard_groups()
        groups["world"] = [
            headline("Colombia peace agreement brings negotiations to parliament"),
            headline("Colombia conflict causes renewed regional humanitarian warnings"),
            headline("Ukraine peace talks begin between European diplomatic leaders"),
            headline("Sudan relief agencies report humanitarian supplies delayed"),
        ]
        edition = editorial.curate(groups, [], NOW)
        leads = edition["rundown"]["Top world headlines"]
        self.assertEqual(len(leads), 2)
        self.assertEqual(len({s["region"] for s in leads}), 2)

    def test_economic_business_news_outranks_private_luxury_listing(self):
        groups = standard_groups()
        groups["business"] = [
            headline("Billionaire mansion luxury estate price reduced in London",
                     "business"),
            headline("Global inflation and employment data prompt central bank action",
                     "business"),
        ]
        edition = editorial.curate(groups, [], NOW)
        self.assertIn("inflation", edition["rundown"]["Business and markets"][0][
            "title"].lower())

    def test_fallback_adds_only_distinct_attributed_evidence(self):
        edition = self._edition()
        dossiers = newsroom3.build_dossiers(edition, [])
        section = "Top world headlines"
        card = dossiers[section][0]
        card["claim_ledger"].append({
            "evidence_field": "summary",
            "publisher": "Second Publisher",
            "source_url": "https://example.org/sourced-report",
            "evidence": (
                "Diplomatic delegates said new meetings will take place "
                "after negotiators review the latest proposal."
            ),
        })
        weather = {"source": "unavailable", "nws_alert_check": "unavailable"}
        short = first_light.fallback_readout(NOW, edition, weather)
        enriched = first_light.fallback_readout(NOW, edition, weather, dossiers)
        self.assertIn("Second Publisher adds:", enriched)
        self.assertNotIn("Second Publisher adds:", short)
        self.assertGreater(len(enriched.split()), len(short.split()))
        self.assertIn("artificial intelligence assistance", enriched)
        self.assertNotIn("That headline comes from one publisher", enriched)
        self.assertNotIn("independently confirmed here", enriched)
        self.assertNotIn("https://", enriched)
        newsroom3.script_numeric_gate(enriched, dossiers, weather, NOW)

    def test_fallback_does_not_pad_if_evidence_absent(self):
        edition = self._edition()
        dossiers = newsroom3.build_dossiers(edition, [])
        weather = {"source": "unavailable"}
        readout = first_light.fallback_readout(NOW, edition, weather, dossiers)
        self.assertEqual(readout.count("reports:"), edition["count"])
        self.assertNotIn("Additional details have not", readout)
        self.assertLess(len(readout.split()), 815)

    def test_rss_enclosure_uses_current_audio_not_archived_revision(self):
        tag = "first-light-2026-11-24"
        episode = {
            "tag_name": tag, "published_at": "2026-11-24T18:00:00Z",
            "html_url": "https://github.com/example/release",
            "assets": [
                {"name": tag + "-revision1.mp3", "browser_download_url": "https://example.org/old.mp3", "size": 123},
                {"name": tag + ".mp3", "browser_download_url": "https://example.org/new.mp3", "size": 456},
            ],
        }
        tree = first_light.xml_feed([episode], "https://example.org/podcast")
        url = tree.getroot().find("./channel/item/enclosure").attrib["url"]
        self.assertEqual(url, "https://example.org/new.mp3")

    def test_writer_retry_after_is_bounded(self):
        self.assertEqual(broadcast32._retry_delay(
            SimpleNamespace(headers={"Retry-After": "7"}), 0), 7)
        self.assertEqual(broadcast32._retry_delay(
            SimpleNamespace(headers={"Retry-After": "99999"}), 0), 2)
        self.assertEqual(broadcast32._retry_delay(
            SimpleNamespace(headers={"Retry-After": "invalid"}), 1), 4)

    def test_503_does_not_auto_switch_text_models(self):
        seen = []
        def unavailable(url, **kw):
            seen.append(url)
            return SimpleNamespace(status_code=503)
        result = broadcast32._call_gemini(
            "test", "gemini-3.5-flash-lite", "test prompt",
            post=unavailable, sleep=lambda _: None)
        self.assertIsNone(result)
        self.assertEqual(len(seen), 3)
        self.assertEqual(len(set(seen)), 1)
        self.assertIn("gemini-3.5-flash-lite", seen[0])


if __name__ == "__main__":
    unittest.main()

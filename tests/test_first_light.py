"""Offline checks: no API use, no paid calls."""
import os
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch
from types import SimpleNamespace
from src.first_light import public_base, xml_feed, web_sources, web_page

class PodcastTests(unittest.TestCase):
    def test_public_url(self):
        with patch.dict(os.environ, {"GITHUB_REPOSITORY": "snrahimi/first-light-podcast", "FEED_BASE_URL": ""}):
            self.assertEqual(public_base(), "https://snrahimi.github.io/first-light-podcast")

    def test_xml_valid_and_enclosure_present(self):
        release = {
            "tag_name": "first-light-2026-11-23",
            "html_url": "https://github.com/snrahimi/first-light-podcast/releases/tag/example",
            "published_at": "2026-11-23T10:00:00Z",
            "assets": [{"name": "first-light-2026-11-23.mp3", "size": 1234567,
                        "browser_download_url": "https://example.org/episode.mp3"}]
        }
        doc = xml_feed([release], "https://example.org")
        root = ET.fromstring(ET.tostring(doc.getroot()))
        item = root.find("./channel/item")
        self.assertIsNotNone(item)
        self.assertEqual(item.find("enclosure").attrib["type"], "audio/mpeg")
        self.assertEqual(item.find("enclosure").attrib["length"], "1234567")
        self.assertEqual(root.find("./channel/title").text, "First Light: World Report")

    def test_source_dedup(self):
        fake = SimpleNamespace(model_dump=lambda: {"output": [
            {"content": [{"annotations": [{"type": "url_citation",
                "url": "https://example.com/a", "title": "A"}]}]},
            {"action": {"sources": [
                {"url": "https://example.com/a", "title": "Again"},
                {"url": "https://example.com/b", "title": "B"}]}}
        ]})
        self.assertEqual(len(web_sources(fake)), 2)

    def test_html_escaped(self):
        page = web_page("2026-11-23", [{"url": "https://example.com/?x=1&y=2", "title": "<hello>"}], "<transcript>")
        self.assertIn("&lt;hello&gt;", page)
        self.assertIn("&lt;transcript&gt;", page)
        self.assertIn("x=1&amp;y=2", page)

if __name__ == "__main__":
    unittest.main()

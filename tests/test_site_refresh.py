"""The manual site transcript layout update must never replace audio/news."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src import refresh_transcript_site as refresh


class SiteRefreshTests(unittest.TestCase):
    def _public_files(self):
        base = {
            "index.html": (
                '<!doctype html><html><head><style>body{color:white}</style>'
                '</head><body><audio src="latest.mp3?date=2026-11-25"></audio>'
                '<h2>Transcript</h2><p>'
                'Good morning, San Antonio. '
                'We begin with the leading world developments. '
                'A report has been attributed to a publisher. '
                'Now, business and markets. '
                'A second report concerns the economy. '
                'And now, a look at the weather in San Antonio. '
                'Conditions are sunny.'
                '</p><footer>Original footer.</footer></body></html>'
            ).encode("utf-8"),
            "latest.mp3": b"ID3" + (b"\0" * 150000),
            "feed.xml": b"<?xml version='1.0' encoding='utf-8'?><rss/>",
            "latest.json": json.dumps({"date": "2026-11-25"}).encode(),
            "cover.png": b"PNG-original",
            "evidence.json": b'{"sources": []}',
            "health.json": b'{"episodes_found":1}',
            "health.html": b"<p>Original health</p>",
            "memory.json": b'{"topics":[]}',
        }
        return base

    def test_only_index_html_changes_no_audio_or_feeds(self):
        original = self._public_files()
        calls = []
        def fake_fetch(name):
            calls.append(name)
            return original[name]
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "site"
            result = refresh.refresh(folder, fetch=fake_fetch)
            self.assertTrue(result["layout_updated"])
            self.assertEqual(result["episode_date"], "2026-11-25")
            self.assertEqual(result["voice_api_requests"], 0)
            self.assertEqual(len(calls), len(original))
            for name in refresh.PRESERVE:
                self.assertEqual(
                    (folder / name).read_bytes(), original[name]
                )
            self.assertIn(
                b'transcript-weather', (folder / "index.html").read_bytes()
            )
            self.assertEqual((folder / ".nojekyll").read_bytes(), b"")

    def test_mismatched_dates_fails_without_writing_site(self):
        original = self._public_files()
        original["latest.json"] = b'{"date": "2026-11-24"}'
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "site"
            with self.assertRaisesRegex(RuntimeError, "does not match"):
                refresh.refresh(folder, fetch=lambda name: original[name])
            self.assertFalse(folder.exists())

    def test_incomplete_audio_fails_closed(self):
        original = self._public_files()
        original["latest.mp3"] = b"ID3"
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "site"
            with self.assertRaisesRegex(RuntimeError, "suspiciously small"):
                refresh.refresh(folder, fetch=lambda name: original[name])
            self.assertFalse(folder.exists())

    def test_missing_asset_fails_closed_without_deployable_folder(self):
        original = self._public_files()
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "site"
            def fake_fetch(name):
                if name == "evidence.json":
                    raise RuntimeError("HTTP 404")
                return original[name]
            with self.assertRaisesRegex(RuntimeError, "HTTP 404"):
                refresh.refresh(folder, fetch=fake_fetch)
            self.assertFalse(folder.exists())

    def test_refuses_dirty_output_directory(self):
        original = self._public_files()
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "site"
            folder.mkdir()
            (folder / "oldfile").write_text("do not overwrite")
            with self.assertRaisesRegex(RuntimeError, "empty"):
                refresh.refresh(folder, fetch=lambda name: original[name])

    def test_only_repo_base_is_allowed(self):
        with patch.dict(os.environ, {
            "GITHUB_REPOSITORY": "snrahimi/first-light-podcast"
        }):
            self.assertEqual(
                refresh.published_base(),
                "https://snrahimi.github.io/first-light-podcast/",
            )
        with patch.dict(os.environ, {
            "GITHUB_REPOSITORY": "bad.example/../../somewhere"
        }):
            with self.assertRaises(ValueError):
                refresh.published_base()


if __name__ == "__main__":
    unittest.main()

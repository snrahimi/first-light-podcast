"""Offline production TTS tests: no real provider calls or charges."""
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from src import elevenlabs_production as tts
from src import first_light


def subscription(remaining=12000):
    return SimpleNamespace(
        status_code=200,
        json=lambda: {"tier": "free", "character_count": 100,
                      "character_limit": 100 + remaining},
    )


def mp3_response(status=200):
    return SimpleNamespace(
        status_code=status,
        headers={"Content-Type": "audio/mpeg"},
        content=b"ID3" + (b"\x00" * 90000),
    )


class ProductionTtsTests(unittest.TestCase):
    def setUp(self):
        self.script = "Good morning from First Light. " * 120

    def _mock_encode(self, args, **kwargs):
        # Copy only through a local fake ffmpeg, no network or audio process.
        Path(args[-1]).write_bytes(b"ID3" + b"\x00" * 100000)
        return SimpleNamespace(returncode=0)

    def test_published_order_and_approved_voice_ids(self):
        self.assertEqual(
            tts.VOICE_ORDER,
            (("Brian", "nPczCjzI2devNBz1zQrb"),
             ("Daniel", "onwK4e9ZLuTAKqWW03F9")),
        )
        self.assertEqual(tts.MODEL, "eleven_flash_v2_5")

    def test_primary_brian_one_post_and_no_daniel_request(self):
        post = Mock(return_value=mp3_response())
        get = Mock(return_value=subscription())
        with tempfile.TemporaryDirectory() as folder, \
             patch.dict(os.environ, {"ELEVENLABS_API_KEY": "fake-key"}), \
             patch.object(tts.subprocess, "run", side_effect=self._mock_encode):
            output = Path(folder) / "episode.mp3"
            name = tts.synthesize(self.script, output, get=get, post=post,
                                  verify=lambda path: 365.0)
            self.assertEqual(name, "ElevenLabs Brian")
            self.assertTrue(output.exists())
            self.assertFalse((Path(folder) / "episode.tts-raw.partial.mp3").exists())
            self.assertEqual(post.call_count, 1)
            url = post.call_args.args[0]
            self.assertTrue(url.endswith(tts.VOICE_ORDER[0][1]))
            self.assertEqual(
                post.call_args.kwargs["json"]["text"], self.script
            )
            self.assertEqual(
                post.call_args.kwargs["json"]["model_id"], tts.MODEL
            )
            self.assertEqual(get.call_count, 1)

    def test_temporary_brian_failure_uses_daniel_once(self):
        post = Mock(side_effect=[mp3_response(503), mp3_response()])
        get = Mock(return_value=subscription())
        with tempfile.TemporaryDirectory() as folder, \
             patch.dict(os.environ, {"ELEVENLABS_API_KEY": "fake-key"}), \
             patch.object(tts.subprocess, "run", side_effect=self._mock_encode):
            output = Path(folder) / "episode.mp3"
            name = tts.synthesize(self.script, output, get=get, post=post,
                                  verify=lambda path: 365.0)
            self.assertEqual(name, "ElevenLabs Daniel")
            self.assertEqual(post.call_count, 2)
            self.assertEqual(get.call_count, 2)
            self.assertTrue(post.call_args.args[0].endswith(tts.VOICE_ORDER[1][1]))
            self.assertTrue(output.exists())

    def test_quota_and_payment_errors_do_not_double_charge(self):
        for status in (401, 402, 403, 429):
            post = Mock(return_value=mp3_response(status))
            with tempfile.TemporaryDirectory() as folder, \
                 patch.dict(os.environ, {"ELEVENLABS_API_KEY": "fake-key"}):
                output = Path(folder) / "episode.mp3"
                with self.assertRaisesRegex(tts.NarratorFailure, f"HTTP {status}"):
                    tts.synthesize(self.script, output,
                                   get=lambda *a, **kw: subscription(),
                                   post=post, verify=lambda path: 365.0)
                post.assert_called_once()
                self.assertFalse(output.exists())

    def test_credit_shortfall_blocks_both_voices_before_post(self):
        post = Mock()
        with tempfile.TemporaryDirectory() as folder, \
             patch.dict(os.environ, {"ELEVENLABS_API_KEY": "fake-key"}):
            with self.assertRaisesRegex(
                    tts.NarratorFailure, "insufficient verified credits"):
                tts.synthesize(
                    self.script, Path(folder) / "out.mp3",
                    get=lambda *a, **kw: subscription(0), post=post,
                )
            post.assert_not_called()

    def test_missing_credit_metadata_fails_closed(self):
        post = Mock()
        with tempfile.TemporaryDirectory() as folder, \
             patch.dict(os.environ, {"ELEVENLABS_API_KEY": "fake-key"}):
            with self.assertRaisesRegex(
                    tts.NarratorFailure, "metadata unavailable"):
                tts.synthesize(
                    self.script, Path(folder) / "out.mp3",
                    get=lambda *a, **kw: SimpleNamespace(status_code=403),
                    post=post,
                )
            post.assert_not_called()

    def test_corrupt_primary_mp3_tries_backup_without_mixing(self):
        corrupt = mp3_response()
        corrupt.content = b"this is not mp3" * 7000
        post = Mock(side_effect=[corrupt, mp3_response()])
        with tempfile.TemporaryDirectory() as folder, \
             patch.dict(os.environ, {"ELEVENLABS_API_KEY": "fake-key"}), \
             patch.object(tts.subprocess, "run", side_effect=self._mock_encode):
            target = Path(folder) / "out.mp3"
            name = tts.synthesize(
                self.script, target,
                get=lambda *a, **kw: subscription(),
                post=post, verify=lambda path: 355.0,
            )
            self.assertEqual(name, "ElevenLabs Daniel")
            self.assertTrue(target.exists())
            self.assertEqual(post.call_count, 2)

    def test_failed_backup_never_leaves_partial_episode(self):
        post = Mock(side_effect=[mp3_response(503), mp3_response(503)])
        with tempfile.TemporaryDirectory() as folder, \
             patch.dict(os.environ, {"ELEVENLABS_API_KEY": "fake-key"}):
            target = Path(folder) / "out.mp3"
            with self.assertRaisesRegex(tts.NarratorFailure, "Daniel"):
                tts.synthesize(
                    self.script, target,
                    get=lambda *a, **kw: subscription(),
                    post=post, verify=lambda path: 350.0,
                )
            self.assertFalse(target.exists())
            self.assertEqual(list(Path(folder).glob("*.partial.mp3")), [])
            self.assertEqual(post.call_count, 2)

    def test_audio_length_cap_is_enforced_before_requests(self):
        post = Mock()
        with tempfile.TemporaryDirectory() as folder, \
             patch.dict(os.environ, {"ELEVENLABS_API_KEY": "fake-key"}):
            with self.assertRaisesRegex(tts.NarratorFailure, "8000-character"):
                tts.synthesize(
                    "a" * (tts.MAX_SCRIPT_CHARS + 1),
                    Path(folder) / "out.mp3", post=post,
                )
        post.assert_not_called()

    def test_narrator_selection_and_charon_opt_out(self):
        with patch.dict(os.environ, {"FIRST_LIGHT_NARRATOR": "elevenlabs"}), \
             patch.object(first_light.elevenlabs_production,
                          "synthesize", return_value="ElevenLabs Brian") as backend:
            name = first_light.synthesize("Good morning", Path("example.mp3"))
            self.assertEqual(name, "ElevenLabs Brian")
            backend.assert_called_once()
        with patch.dict(os.environ, {"FIRST_LIGHT_NARRATOR": "unsupported"}):
            with self.assertRaisesRegex(RuntimeError, "Unsupported"):
                first_light.synthesize("Good morning", Path("example.mp3"))

    def test_rss_attribution_only_for_elevenlabs_episode(self):
        a = {
            "tag_name": "first-light-2026-11-25",
            "published_at": "2026-11-25T10:30:00Z",
            "assets": [{
                "name": "first-light-2026-11-25.mp3",
                "size": 1111, "browser_download_url": "https://example.test/e.mp3"
            }],
            "body": "Narrator: ElevenLabs Brian\nGenerated with ElevenLabs (https://elevenlabs.io)."
        }
        tree = first_light.xml_feed([a], "https://example.test")
        desc = tree.getroot().find("./channel/item/description").text
        self.assertIn("Voice generated with ElevenLabs", desc)
        b = dict(a, body="Narrator: Gemini Charon")
        other = first_light.xml_feed([b], "https://example.test")
        self.assertNotIn(
            "Voice generated with ElevenLabs",
            other.getroot().find("./channel/item/description").text,
        )

    def test_site_attribution_and_daily_workflow_settings(self):
        html = first_light.web_page(
            "2026-11-25", [], "News script", narrator="ElevenLabs Brian"
        )
        self.assertIn('href="https://elevenlabs.io"', html)
        self.assertNotIn(
            'href="https://elevenlabs.io"',
            first_light.web_page("2026-11-25", [], "News script"),
        )
        wf = (
            Path(__file__).resolve().parents[1]
            / ".github/workflows/daily.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("FIRST_LIGHT_NARRATOR:", wf)
        self.assertIn("ELEVENLABS_API_KEY:", wf)
        self.assertIn("secrets.ELEVENLABS_API_KEY", wf)
        self.assertIn("'elevenlabs'", wf)
        self.assertNotIn("ELEVENLABS_VOICE_ID:", wf)
        self.assertNotIn("ELEVENLABS_AUDITION_VOICE_ID:", wf)


if __name__ == "__main__":
    unittest.main()

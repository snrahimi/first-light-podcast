"""Account-gated replacement voice tests, all offline and non-billable."""
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src import voice_retirement as vr
from src import elevenlabs_audition as audition
from src import elevenlabs_production as production


def response(status, content):
    return SimpleNamespace(status_code=status, json=lambda: content)


def fake_client(plan="free", visible=True, enough=True, library=True):
    calls = []
    def get(url, **kwargs):
        calls.append((url, kwargs))
        if url.endswith("/user/subscription"):
            return response(200, {
                "tier": plan, "character_count": 100,
                "character_limit": 20000 if enough else 101,
            })
        for item in vr.CANDIDATES.values():
            if url.endswith("/" + item["id"]):
                if not visible:
                    return response(404, {})
                return response(200, {
                    "voice_id": item["id"],
                    "category": "professional" if library else "premade",
                    "sharing": {"status": "shared"} if library else None,
                })
        raise AssertionError("Unexpected external request")
    return get, calls


class VoiceRetirementTests(unittest.TestCase):
    def test_official_voice_replacement_ids_and_existing_production_untouched(self):
        self.assertEqual(vr.CANDIDATES["sawyer"]["id"],
                         "8dEUmyPMdDdK91vboYih")
        self.assertEqual(vr.CANDIDATES["finley"]["id"],
                         "fnYMz3F5gMEDGMWcH1ex")
        self.assertEqual(production.VOICE_ORDER[0][0], "Brian")
        self.assertEqual(production.VOICE_ORDER[1][0], "Daniel")
        self.assertEqual(production.VOICE_ORDER[0][1],
                         vr.CANDIDATES["sawyer"]["prior_id"])
        self.assertEqual(production.VOICE_ORDER[1][1],
                         vr.CANDIDATES["finley"]["prior_id"])

    def test_free_account_library_voices_blocked_without_speech(self):
        get, calls = fake_client(plan="free")
        data = vr.audit("fake-key", get=get)
        self.assertEqual(data["plan"], "free")
        self.assertEqual(data["text_to_speech_calls"], 0)
        self.assertEqual(len(calls), 3)
        self.assertTrue(all(c["known_free_tier_api_block"]
                            for c in data["candidates"].values()))
        self.assertFalse(any(c["read_only_audition_eligible"]
                             for c in data["candidates"].values()))
        for _, opts in calls:
            self.assertEqual(opts["headers"]["xi-api-key"], "fake-key")
            self.assertFalse(opts["allow_redirects"])
        with self.assertRaisesRegex(RuntimeError, "before TTS"):
            vr.audition_one("sawyer", "fake-key", get=get,
                            post=Mock())

    def test_paid_metadata_allows_a_manual_one_call_audition_only(self):
        get, calls = fake_client(plan="creator", enough=True)
        audio = b"ID3" + b"0" * 95000
        post = Mock(return_value=SimpleNamespace(
            status_code=200,
            headers={"Content-Type": "audio/mpeg"},
            content=audio,
        ))
        with tempfile.TemporaryDirectory() as directory:
            record = vr.audition_one(
                "finley", "fake-key", get=get, post=post,
                output=Path(directory),
                probe=lambda path: 50.5,
            )
            self.assertTrue(
                (Path(directory) / "first-light-finley-audition.mp3").exists()
            )
            self.assertEqual(record["candidate"], "Finley - Articulate Anchor")
            self.assertEqual(record["tts_requests"], 1)
            self.assertFalse(record["production_changed"])
            self.assertFalse(record["human_listening_approval"])
            self.assertEqual(
                post.call_args.args[0].split("/")[-1],
                vr.CANDIDATES["finley"]["id"]
            )
            self.assertEqual(
                post.call_args.kwargs["json"]["text"],
                vr.RETIREMENT_SAMPLE
            )
            self.assertEqual(
                post.call_args.kwargs["json"]["model_id"],
                audition.MODEL
            )
            post.assert_called_once()

    def test_unknown_credits_and_unavailable_voices_fail_closed(self):
        for visible, enough in [(False, True), (True, False)]:
            get, _ = fake_client("creator", visible=visible, enough=enough)
            post = Mock()
            audit = vr.audit("fake-key", get=get)
            self.assertFalse(audit["candidates"]["sawyer"]
                             ["read_only_audition_eligible"])
            with self.assertRaisesRegex(RuntimeError, "before TTS"):
                vr.audition_one("sawyer", "fake-key", get=get, post=post)
            post.assert_not_called()

    def test_free_account_premade_metadata_is_not_automatic_approval(self):
        get, _ = fake_client("free", library=False)
        report = vr.audit("fake-key", get=get)
        self.assertFalse(report["candidates"]["finley"]["known_free_tier_api_block"])
        self.assertFalse(report["candidates"]["finley"]["read_only_audition_eligible"])


    def test_retirement_sample_covers_actual_pronunciation_risks(self):
        self.assertLessEqual(len(vr.RETIREMENT_SAMPLE), 820)
        self.assertGreaterEqual(len(vr.RETIREMENT_SAMPLE.split()), 90)
        audition.audition_payload(vr.RETIREMENT_SAMPLE)
        for phrase in ("San Antonio", "Kyiv", "Cartagena",
                       "Warsaw", "Tehran", "Eastern Time",
                       "Central Standard Time"):
            self.assertIn(phrase, vr.RETIREMENT_SAMPLE)
        self.assertEqual(vr.RETIREMENT_SAMPLE.count("San Antonio"), 2)

    def test_no_production_voice_change_or_publication_permissions(self):
        from pathlib import Path
        flow = Path(__file__).resolve().parents[1] / \
            ".github/workflows/voice-retirement-audit.yml"
        content = flow.read_text(encoding="utf-8")
        self.assertIn("mode == 'audition_one'", content)
        self.assertIn("mode == 'audit_only'", content)
        self.assertIn("contents: read", content)
        self.assertNotIn("contents: write", content)
        self.assertNotIn("actions/deploy-pages", content)
        self.assertNotIn("src.first_light", content)
        self.assertIn("voice-retirement-audit/", content)


if __name__ == "__main__":
    unittest.main()

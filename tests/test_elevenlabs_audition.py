"""Offline checks for the manual, one-call ElevenLabs free-tier audition."""
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from pathlib import Path
import tempfile

from src import elevenlabs_audition as voice


def fake_response(status=200, mime="audio/mpeg", data=None):
    if data is None:
        data = b"ID3" + b"\x00" * 75000
    return SimpleNamespace(
        status_code=status, headers={"Content-Type": mime}, content=data
    )


class ElevenLabsAuditionTests(unittest.TestCase):
    def test_sample_is_original_small_and_bounded(self):
        payload = voice.audition_payload()
        self.assertEqual(payload["model_id"], "eleven_flash_v2_5")
        self.assertLessEqual(len(payload["text"]), voice.MAX_CHARACTERS)
        self.assertGreaterEqual(len(payload["text"].split()), 90)
        self.assertNotIn("article_url", payload)

    def test_excess_length_fails_before_api_call(self):
        with self.assertRaisesRegex(ValueError, "820-character"):
            voice.audition_payload(("international " * 100).strip())
        with self.assertRaisesRegex(ValueError, "90-160-word"):
            voice.audition_payload("This is much too short.")

    def test_exactly_one_request_and_expected_voice_and_format(self):
        called = []
        def post(url, **kwargs):
            called.append((url, kwargs))
            return fake_response()
        data = voice.request_sample(
            "fake-private-key", "JBFqnCBsd6RMkjVDRZzb", post=post
        )
        self.assertTrue(data.startswith(b"ID3"))
        self.assertEqual(len(called), 1)
        url, args = called[0]
        self.assertTrue(url.endswith("/JBFqnCBsd6RMkjVDRZzb"))
        self.assertEqual(args["headers"]["xi-api-key"], "fake-private-key")
        self.assertEqual(args["params"]["output_format"], "mp3_44100_128")
        self.assertFalse(args["allow_redirects"])
        self.assertLessEqual(len(args["json"]["text"]), 820)

    def test_missing_credentials_does_not_send_request(self):
        calls = []
        def post(*a, **kw):
            calls.append(1)
            raise AssertionError("An API call must not occur")
        with self.assertRaisesRegex(RuntimeError, "required"):
            voice.request_sample("", "JBFqnCBsd6RMkjVDRZzb", post=post)
        with self.assertRaisesRegex(RuntimeError, "required"):
            voice.request_sample("fake-private-key", "", post=post)
        with self.assertRaisesRegex(ValueError, "invalid format"):
            voice.request_sample("fake-private-key", "bad/voice", post=post)
        self.assertFalse(calls)

    def test_no_retry_or_secret_leak_for_quota_and_auth_errors(self):
        for status in (400, 401, 402, 403, 429, 503):
            calls = []
            def post(*args, **kwargs):
                calls.append(1)
                return fake_response(status=status)
            with self.assertRaises(RuntimeError) as caught:
                voice.request_sample(
                    "PRIVATE_TEST_KEY_DO_NOT_PRINT",
                    "JBFqnCBsd6RMkjVDRZzb",
                    post=post,
                )
            self.assertEqual(len(calls), 1)
            self.assertIn(f"HTTP {status}", str(caught.exception))
            self.assertNotIn("PRIVATE_TEST_KEY_DO_NOT_PRINT",
                             str(caught.exception))

    def test_diagnostic_detects_free_plan_shared_voice_with_get_only(self):
        key, voice_id = "KEY_SECRET_DO_NOT_LOG", "JBFqnCBsd6RMkjVDRZzb"
        calls = []
        def get(url, **kwargs):
            calls.append((url, kwargs))
            if url.endswith("/user/subscription"):
                data = {"tier": "free", "character_count": 100,
                        "character_limit": 10000}
            else:
                data = {"voice_id": voice_id, "category": "professional",
                        "sharing": {"public_owner_id": "private"},
                        "available_for_tiers": ["starter", "creator"]}
            return SimpleNamespace(status_code=200, json=lambda: data)
        result = voice.diagnose_access(
            key, voice_id, get=get, announce=False,
        )
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(c[1]["headers"]["xi-api-key"] == key
                            for c in calls))
        self.assertTrue(all(c[1]["allow_redirects"] is False
                            for c in calls))
        self.assertTrue(result["known_free_voice_block"])
        self.assertEqual(result["plan"], "free")
        self.assertEqual(result["voice_type"], "shared_voice_library")
        self.assertEqual(result["credit_counter"], "not_exhausted")

    def test_diagnostic_does_not_block_premade_or_unknown_voice(self):
        voice_id = "JBFqnCBsd6RMkjVDRZzb"
        def get(url, **kwargs):
            if url.endswith("/user/subscription"):
                data = {"tier": "free"}
            else:
                data = {"voice_id": voice_id, "category": "premade",
                        "sharing": None, "available_for_tiers": ["free"]}
            return SimpleNamespace(status_code=200, json=lambda: data)
        result = voice.diagnose_access("test-key", voice_id,
                                       get=get, announce=False)
        self.assertFalse(result["known_free_voice_block"])
        self.assertEqual(result["voice_type"], "other")
        unavailable = voice.diagnose_access(
            "test-key", voice_id,
            get=lambda *a, **kw: SimpleNamespace(status_code=403),
            announce=False,
        )
        self.assertEqual(unavailable["plan"], "unknown")
        self.assertFalse(unavailable["known_free_voice_block"])

    def test_402_reports_whitelisted_code_without_leaking_response_body(self):
        for code, safe_term in (
            ("paid_plan_required", "requires a paid plan"),
            ("insufficient_credits", "insufficient available credits"),
            ("unknown_secret_123", "cause unknown"),
        ):
            response = fake_response(status=402)
            response.json = lambda c=code: {
                "detail": {
                    "code": c,
                    "message": "SECRET-RESPONSE-DETAILS-MUST-NOT-LEAK",
                }
            }
            with self.assertRaises(RuntimeError) as ctx:
                voice.request_sample(
                    "SECRET-API-KEY", "JBFqnCBsd6RMkjVDRZzb",
                    post=lambda *a, **kw: response,
                )
            message = str(ctx.exception)
            self.assertIn("HTTP 402", message)
            self.assertIn(safe_term, message)
            self.assertNotIn("SECRET", message)
            self.assertNotIn("unknown_secret_123", message)

    def test_cli_skips_billable_request_for_known_free_library_block(self):
        with patch.dict("os.environ", {
            "ELEVENLABS_API_KEY": "test-key",
            "ELEVENLABS_VOICE_ID": "JBFqnCBsd6RMkjVDRZzb",
        }):
            with patch.object(voice, "diagnose_access", return_value={
                "known_free_voice_block": True
            }):
                with patch.object(voice, "request_sample") as post:
                    with patch("pathlib.Path.mkdir") as mkdir:
                        with self.assertRaisesRegex(
                                RuntimeError, "free-tier API cannot synthesize"):
                            voice.main()
                        post.assert_not_called()
                        mkdir.assert_not_called()

    def test_diagnose_only_mode_requires_explicit_generate_input(self):
        workflow = (
            Path(__file__).resolve().parents[1]
            / ".github/workflows/elevenlabs-voice-audition.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("default: diagnose_only", workflow)
        self.assertIn("run: python -m src.elevenlabs_audition --diagnose",
                      workflow)
        self.assertIn("if: " + "$" + "{{ inputs.mode == 'generate_sample' }}",
                      workflow)
        self.assertIn(
            "if: " + "$" + "{{ inputs.mode == 'generate_sample' && success() }}",
            workflow,
        )

    def test_reject_fake_or_massive_audio(self):
        cases = [
            fake_response(mime="text/html"),
            fake_response(data=b"not mp3" * 15000),
            fake_response(data=b"ID3" + b"x" * 3000001),
            fake_response(data=b"ID3" + b"x" * 10),
        ]
        for response in cases:
            with self.assertRaises(RuntimeError):
                voice.request_sample(
                    "fake-key", "JBFqnCBsd6RMkjVDRZzb",
                    post=lambda *a, **kw: response,
                )

    def test_audition_installs_ffprobe_before_audio_inspection(self):
        workflow = (
            Path(__file__).resolve().parents[1]
            / ".github/workflows/elevenlabs-voice-audition.yml"
        ).read_text(encoding="utf-8")
        installer = "sudo apt-get install -y --no-install-recommends ffmpeg"
        verifier = "ffprobe -version"
        self.assertIn(installer, workflow)
        self.assertIn(verifier, workflow)
        self.assertLess(workflow.index(installer), workflow.index(verifier))
        self.assertIn("run: python -m src.elevenlabs_audition", workflow)
        self.assertLess(workflow.index(verifier),
                        workflow.index("run: python -m src.elevenlabs_audition"))

    def test_cli_fail_closed_if_secrets_absent(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.dict("os.environ", {
                "ELEVENLABS_API_KEY": "",
                "ELEVENLABS_VOICE_ID": "",
            }):
                with patch("pathlib.Path.mkdir") as mkdir:
                    with self.assertRaisesRegex(RuntimeError, "Configure both"):
                        voice.main()
                    mkdir.assert_not_called()


if __name__ == "__main__":
    unittest.main()

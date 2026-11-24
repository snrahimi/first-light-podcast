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
            voice.audition_payload("This is a sample sentence. " * 50)
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

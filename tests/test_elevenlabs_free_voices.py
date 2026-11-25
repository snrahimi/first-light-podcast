"""No-credit offline tests of the ElevenLabs free voice shortlist."""
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from src import elevenlabs_free_voices as free


def answer(body, code=200):
    return SimpleNamespace(status_code=code, json=lambda: body)


class FreeVoiceComparisonTests(unittest.TestCase):
    def test_published_legacy_default_ids_and_only_expected_voices(self):
        self.assertEqual(
            [k for k in free.SHORTLIST],
            ["daniel", "brian", "chris", "alice"],
        )
        self.assertEqual(
            free.SHORTLIST["daniel"]["id"], "onwK4e9ZLuTAKqWW03F9"
        )
        self.assertEqual(
            free.SHORTLIST["brian"]["id"], "nPczCjzI2devNBz1zQrb"
        )
        self.assertEqual(
            free.SHORTLIST["chris"]["id"], "iP95p4xoKVk53GoZ742B"
        )
        self.assertEqual(
            free.SHORTLIST["alice"]["id"], "Xb7hH8MSUJpSbSDYk0k2"
        )

    def test_discover_gets_only_metadata_and_filters_community_and_paid(self):
        names = free.SHORTLIST
        calls = []
        def get(url, **kwargs):
            calls.append((url, kwargs))
            if url.endswith("/user/subscription"):
                return answer({"tier": "free"})
            return answer({"voices": [
                {"voice_id": names["daniel"]["id"],
                 "category": "premade", "sharing": None},
                {"voice_id": names["brian"]["id"],
                 "category": "premade", "sharing": None,
                 "available_for_tiers": ["free", "starter"]},
                {"voice_id": names["chris"]["id"],
                 "category": "premade",
                 "sharing": {"public_owner_id": "hidden"}},
                {"voice_id": names["alice"]["id"],
                 "category": "premade", "sharing": None,
                 "available_for_tiers": ["creator"]},
                {"voice_id": "PRIVATE_CUSTOM_USER_VOICE",
                 "category": "generated"},
            ]})
        result = free.discover("TEST_CREDENTIAL", get=get, announce=False)
        self.assertEqual(result["plan"], "free")
        self.assertEqual(result["metadata_status"], "available")
        self.assertEqual(list(result["choices"]), ["daniel", "brian"])
        self.assertEqual(len(calls), 3)
        self.assertTrue(all(
            call[1]["headers"]["xi-api-key"] == "TEST_CREDENTIAL" and
            call[1]["allow_redirects"] is False
            for call in calls
        ))

    def test_no_defaults_or_metadata_means_no_candidates(self):
        for returned in (answer({"voices": []}),
                         answer({}, code=403)):
            def get(url, **kwargs):
                return (answer({"tier": "free"})
                        if url.endswith("/user/subscription") else returned)
            found = free.discover("TEST", get=get, announce=False)
            self.assertEqual(found["choices"], {})

    def test_restricted_or_unknown_candidate_cannot_generate_audio(self):
        for option in ("daniel", "brian", "chris", "alice"):
            mock_run = Mock()
            def get(url, **kwargs):
                return (answer({"tier": "free"})
                        if url.endswith("/user/subscription") else
                        answer({"voices": []}))
            with self.assertRaisesRegex(RuntimeError, "no TTS API request"):
                free.audition_one(
                    option, "TEST_CREDENTIAL", get=get, run=mock_run,
                )
            mock_run.assert_not_called()

    def test_selected_listed_default_calls_one_candidate_only(self):
        candidate = free.SHORTLIST["brian"]
        def get(url, **kwargs):
            if url.endswith("/user/subscription"):
                return answer({"tier": "free"})
            return answer({"voices": [{
                "voice_id": candidate["id"],
                "category": "premade",
                "sharing": None,
            }]})
        mock_run = Mock()
        with patch.object(Path, "write_text") as write_text:
            free.audition_one(
                "brian", "TEST_CREDENTIAL", get=get, run=mock_run,
            )
        mock_run.assert_called_once_with(
            voice_id_override=candidate["id"],
        )
        self.assertEqual(write_text.call_count, 1)
        self.assertIn("Brian", write_text.call_args.args[0])

    def test_invalid_alias_or_missing_api_key_never_calls_tts(self):
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            free.audition_one("library-voice", "TEST_CREDENTIAL")
        with self.assertRaisesRegex(RuntimeError, "required"):
            free.discover("")

    def test_owned_voice_design_discovery_counts_without_identifying(self):
        def get(url, **kwargs):
            if url.endswith("/user/subscription"):
                return answer({"tier": "free"})
            if "voice_type=personal" in url:
                return answer({"voices": [
                    {"category": "generated", "voice_id": "PRIVATE_PERSONAL_ID",
                     "sharing": None},
                    {"category": "professional", "voice_id": "COMMUNITY_ID",
                     "sharing": {"public_owner_id": "owner"}},
                ]})
            return answer({"voices": []})
        result = free.discover("KEY", get=get, announce=False)
        self.assertEqual(result["owned_voice_design_count"], 1)
        self.assertEqual(result["choices"], {})

    def test_custom_voice_must_be_personally_owned_and_generated(self):
        selected = "A12B34C56D78E90F1234"
        fake_run = Mock()
        def get(url, **kwargs):
            if url.endswith("/user/subscription"):
                return answer({"tier": "free"})
            if url.endswith("/voices/" + selected):
                return answer({
                    "voice_id": selected, "category": "professional",
                    "sharing": {"public_owner_id": "other"},
                })
            return answer({"voices": []})
        with patch.dict(os.environ, {
            "ELEVENLABS_AUDITION_VOICE_ID": selected
        }):
            with self.assertRaisesRegex(RuntimeError, "no TTS request"):
                free.audition_one(
                    "custom", "KEY", get=get, run=fake_run,
                )
        fake_run.assert_not_called()

    def test_owned_voice_design_may_be_auditioned_with_secret_override(self):
        selected = "A12B34C56D78E90F1234"
        fake_run = Mock()
        def get(url, **kwargs):
            if url.endswith("/user/subscription"):
                return answer({"tier": "free"})
            if url.endswith("/voices/" + selected):
                return answer({
                    "voice_id": selected, "category": "generated",
                    "sharing": None,
                })
            if "voice_type=personal" in url:
                return answer({"voices": [{
                    "voice_id": selected, "category": "generated",
                    "sharing": None,
                }]})
            return answer({"voices": []})
        with patch.dict(os.environ, {
            "ELEVENLABS_AUDITION_VOICE_ID": selected
        }):
            with patch.object(Path, "write_text") as write_text:
                free.audition_one(
                    "custom", "KEY", get=get, run=fake_run,
                )
        fake_run.assert_called_once_with(
            voice_id_override=selected,
        )
        self.assertIn("Personal Voice Design", write_text.call_args.args[0])

    def test_custom_secret_missing_does_not_generate(self):
        with patch.dict(os.environ, {
            "ELEVENLABS_AUDITION_VOICE_ID": ""
        }):
            fake_run = Mock()
            with self.assertRaisesRegex(RuntimeError, "secret"):
                free.audition_one("custom", "KEY",
                                  get=lambda url, **kw: answer({"voices": []}),
                                  run=fake_run)
            fake_run.assert_not_called()

    def test_workflow_default_is_nonbillable_and_production_untouched(self):
        root = Path(__file__).resolve().parents[1]
        wf = (root / ".github/workflows/elevenlabs-free-voice-compare.yml"
              ).read_text(encoding="utf-8")
        self.assertIn("default: discover_only", wf)
        self.assertIn("python -m src.elevenlabs_free_voices discover", wf)
        self.assertIn("if: " + "$" + "{{ inputs.mode == 'audition_one' }}", wf)
        self.assertIn("python -m src.elevenlabs_free_voices audition", wf)
        self.assertNotIn("GEMINI_API_KEY", wf)
        self.assertNotIn("pages:", wf)
        self.assertNotIn("contents: write", wf)
        self.assertNotIn("          ELEVENLABS_VOICE_ID:", wf)
        self.assertIn("ELEVENLABS_AUDITION_VOICE_ID", wf)


if __name__ == "__main__":
    unittest.main()

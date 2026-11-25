"""First Light editorial and Brian delivery upgrades: offline/no API requests."""
import os
from pathlib import Path
import re
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from datetime import datetime
from zoneinfo import ZoneInfo

from src import editorial, broadcast32, elevenlabs_production as tts


class NewsroomQualityUpgradeTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 25, 5, 0,
                            tzinfo=ZoneInfo("America/Chicago"))

    def _cluster(self, summary):
        title = "A regional court reviews a new water resources ruling"
        item = {
            "title": title,
            "publisher": "Fictional Local Wire",
            "summary": summary,
            "age": 2,
        }
        return {
            "category": "world",
            "lead": item,
            "reports": [item],
            "publishers": ["Fictional Local Wire"],
            "region": "other",
        }

    def test_complete_reporting_has_bounded_narration_bonus(self):
        clipped = self._cluster(
            "A regional court issued a preliminary statement about the case "
            "after testimony from several officials but the record"
        )
        supported = self._cluster(
            "A regional court issued a preliminary statement after testimony "
            "from several officials. No final timetable was included in the "
            "court filing, the report said."
        )
        no_context = editorial._story_explainer_support(clipped)
        meaningful = editorial._story_explainer_support(supported)
        self.assertEqual(no_context["complete_distinct_summaries"], 0)
        self.assertEqual(no_context["bonus"], 0)
        self.assertEqual(meaningful["complete_distinct_summaries"], 1)
        self.assertEqual(meaningful["bonus"], 2)
        self.assertFalse(meaningful["independently_verified"])
        a, _, _ = editorial._rank(clipped, [])
        b, _, _ = editorial._rank(supported, [])
        self.assertGreater(b, a)
        self.assertLessEqual(b - a, 8)

    def test_repeated_same_summary_cannot_inflate_evidence(self):
        title = "A regional court reviews a new water resources ruling"
        full = ("In a published report the officials said their next review "
                "will be on Friday and public comments remain open.")
        duplicate = self._cluster(full)
        duplicate["reports"].append({
            "title": title, "publisher": "Second Source", "summary": full
        })
        score = editorial._story_explainer_support(duplicate)
        self.assertEqual(score["complete_distinct_summaries"], 1)
        self.assertEqual(score["publisher_feeds"], 2)
        self.assertFalse(score["independently_verified"])

    def test_sparse_world_lead_stays_short(self):
        sparse = {"Top world headlines": [{
            "headline": "A court issued a notice",
            "evidence": [
                {"publisher": "Example Wire",
                 "text": "A court issued a notice but the rest of the"}
            ],
            "official_context": [],
        }]}
        beat = broadcast32._editorial_beat_plan(sparse)[0]
        self.assertEqual(beat["narrative_depth"], "brief_only")
        self.assertEqual(beat["story_role"], "world_lead")
        self.assertLessEqual(beat["suggested_words_if_supported"], 120)
        self.assertEqual(beat["complete_source_excerpts"], 0)

    def test_supported_world_lead_can_receive_depth(self):
        material = {"Top world headlines": [{
            "headline": "A court issued a notice",
            "evidence": [
                {"publisher": "Wire One",
                 "text": "The court released its written notice after a "
                         "public hearing with local officials on Tuesday."},
                {"publisher": "Wire Two",
                 "text": "The published document contained two separate "
                         "proposed dates for later proceedings this month."},
            ],
            "official_context": [],
        }]}
        beat = broadcast32._editorial_beat_plan(material)[0]
        self.assertEqual(beat["narrative_depth"], "supported_explainer")
        self.assertEqual(beat["complete_source_excerpts"], 2)
        self.assertGreater(beat["suggested_words_if_supported"], 120)

    def test_presentation_review_is_advisory_only_not_fact_check(self):
        script = (
            "Outlet A reports: An event happened. "
            "In its summary Outlet A adds: Another statement. "
            "Outlet B reports: A second development happened. "
            "Outlet C reports: A third development happened. "
            "Business markets and science technology weather are discussed."
        )
        edition = {"rundown": {"Top world headlines": [
            {"title": "One", "explainer_support": {
                "complete_distinct_summaries": 0
            }},
            {"title": "Two", "explainer_support": {
                "complete_distinct_summaries": 1
            }},
        ]}}
        result = broadcast32.presentation_review(script, edition)
        self.assertEqual(result["status"], "advisory_only_not_independent_verification")
        self.assertEqual(result["lead_stories_with_scarce_feed_context"], 1)
        self.assertGreaterEqual(result["attribution_formula_count"], 4)
        self.assertTrue(result["editorial_notes"])

    def test_brian_planning_rate_is_mapped_without_changing_audio(self):
        preflight = broadcast32.duration_preflight(765)
        self.assertEqual(preflight["planning_voice"], "ElevenLabs Brian")
        self.assertEqual(preflight["planning_wpm"], 153)
        self.assertEqual(preflight["observed_charon_wpm"], 163)
        self.assertEqual(preflight["estimated_seconds"], 300)


class NarratorDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.script = (
            "Good morning, San Antonio. "
            "We begin with the leading world developments. "
            "An attributed publisher describes an event. "
            "Now let's turn to business, science and technology. "
            "A source describes a business report. "
            "And now, a look at the weather in San Antonio. "
            "It's partly cloudy today. "
            "That's First Light: World Report. Thanks for listening."
        )

    def test_delivery_inserts_only_short_known_ssml_pauses(self):
        result = tts.delivery_text(self.script)
        breaks = re.findall(r'<break time="([0-9.]+)s" />', result)
        self.assertEqual(breaks, ["0.4", "0.5", "0.65", "0.45"])
        spoken = re.sub(r'<break time="[0-9.]+s" />', "", result)
        self.assertEqual(" ".join(spoken.split()), " ".join(self.script.split()))
        self.assertLessEqual(len(result), tts.MAX_SCRIPT_CHARS)

    def test_no_fake_break_from_source_quoted_phrase(self):
        script = (
            "The report quotes a sentence: "
            "And now, a look at the weather in San Antonio. "
            "The agency did not issue a forecast."
        )
        spoken = tts.delivery_text(script)
        # Quoted/source phrase wasn't introduced after a full stop; do
        # not attempt to interpret it as a producer-authored transition.
        self.assertEqual(spoken, script)

    def test_untrusted_ssml_is_rejected_before_tts(self):
        with self.assertRaisesRegex(tts.NarratorFailure, "untrusted"):
            tts.delivery_text("Source <break time=\"3s\" /> says news.")

    def test_brian_preset_is_natural_and_backup_stays_separate(self):
        self.assertEqual(tts.VOICE_SETTINGS["Brian"]["speed"], 1.0)
        self.assertLess(tts.VOICE_SETTINGS["Brian"]["stability"],
                        tts.VOICE_SETTINGS["Daniel"]["stability"])
        self.assertLess(tts.VOICE_SETTINGS["Brian"]["stability"], 0.63)
        for name in ("Brian", "Daniel"):
            cfg = tts.VOICE_SETTINGS[name]
            self.assertTrue(cfg["use_speaker_boost"])
            self.assertEqual(cfg["style"], 0.0)
            self.assertTrue(0.7 <= cfg["speed"] <= 1.2)

    def test_credit_preflight_counts_all_added_break_markup(self):
        script = self.script
        prepared = tts.delivery_text(script)
        self.assertGreater(len(prepared), len(script))
        responder = Mock(return_value=SimpleNamespace(
            status_code=200, json=lambda: {
                "character_count": 999, "character_limit": 999 + len(script)
            },
        ))
        post = Mock()
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {
            "ELEVENLABS_API_KEY": "fake-testing-key"
        }):
            with self.assertRaisesRegex(
                    tts.NarratorFailure, "insufficient verified credits"):
                tts.synthesize(
                    script, Path(tmp) / "episode.mp3", get=responder, post=post
                )
        post.assert_not_called()

    def test_brian_post_contains_pause_cues_only_not_changed_spoken_words(self):
        from unittest.mock import Mock
        def fake_ffmpeg(cmd, **kwargs):
            Path(cmd[-1]).write_bytes(b"ID3" + b"0" * 150000)
            return SimpleNamespace(returncode=0)
        def audio_reply(*args, **kwargs):
            return SimpleNamespace(
                status_code=200,
                headers={"Content-Type": "audio/mpeg"},
                content=b"ID3" + b"0" * 150000,
            )
        post = Mock(side_effect=audio_reply)
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {
            "ELEVENLABS_API_KEY": "fake-testing-key"
        }), patch.object(tts.subprocess, "run", side_effect=fake_ffmpeg):
            target = Path(tmp) / "episode.mp3"
            narrator = tts.synthesize(
                self.script, target,
                get=lambda *args, **kwargs: SimpleNamespace(
                    status_code=200,
                    json=lambda: {"character_count": 0,
                                  "character_limit": 20000},
                ),
                post=post, verify=lambda path: 350.0,
            )
            self.assertEqual(narrator, "ElevenLabs Brian")
            self.assertEqual(post.call_count, 1)
            payload = post.call_args.kwargs["json"]
            self.assertIn('<break time="0.65s" />', payload["text"])
            self.assertEqual(payload["voice_settings"],
                             tts.VOICE_SETTINGS["Brian"])
            restored = re.sub(
                r'<break time="[0-9.]+s" />', "", payload["text"]
            )
            self.assertEqual(" ".join(restored.split()),
                             " ".join(self.script.split()))
            self.assertTrue(target.is_file())


if __name__ == "__main__":
    unittest.main()

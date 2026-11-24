"""Offline package 2+ operational monitoring and release revision tests."""
import unittest
import tempfile
from pathlib import Path
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from src import monitor2plus, first_light


def release(day, with_assets=True, health=None):
    tag = f"first-light-{day}"
    body = monitor2plus.encode_health(health) if health else "Earlier release."
    return {
        "tag_name": tag, "body": body,
        "html_url": "https://github.com/example/first-light/releases/tag/" + tag,
        "assets": (
            [{"name": tag + ".mp3", "size": 5500000},
             {"name": tag + ".txt", "size": 4200},
             {"name": tag + "-evidence.json", "size": 20000}]
            if with_assets else []
        ),
    }


class Monitor2PlusTests(unittest.TestCase):
    def test_marker_round_trip_for_current_release(self):
        record = {
            "day": "2026-11-24", "narrator": "Gemini Charon",
            "duration_seconds": 315.4, "in_duration_target": True,
            "script_mode": "Gemini segmented evidence-led 3.2",
        }
        self.assertEqual(
            monitor2plus.decode_health(release("2026-11-24", health=record)),
            record,
        )
        self.assertIsNone(monitor2plus.decode_health(release("2026-11-23")))
        tampered = release("2026-11-23", health=record)
        self.assertIsNone(monitor2plus.decode_health(tampered))

    def test_30_day_metrics_report_only_known_values(self):
        today = date(2026, 11, 24)
        good = release("2026-11-24", health={
            "day": "2026-11-24", "duration_seconds": 321,
            "in_duration_target": True, "narrator": "Gemini Charon",
            "gemini_text_requests": 2,
            "script_mode": "Gemini segmented evidence-led 3.2",
            "official_documents": 1,
        })
        old = release("2026-10-01", health={
            "day": "2026-10-01", "duration_seconds": 9999,
            "in_duration_target": False
        })
        unknown = release("2026-11-23")
        history = monitor2plus.rolling_report([good, old, unknown], today)
        self.assertEqual(history["episodes_found"], 2)
        self.assertEqual(history["episodes_with_quality_metadata"], 1)
        self.assertEqual(history["older_episodes_without_quality_metadata"], 1)
        self.assertEqual(history["five_to_seven_minute_episodes"], 1)
        self.assertEqual(history["official_source_pages_total"], 1)
        self.assertEqual(history["text_writer_request_total"], 2)
        self.assertEqual(history["mean_duration_seconds"], 321)

    def test_daily_release_checks_assets_not_just_tag(self):
        today = date(2026, 11, 24)
        self.assertFalse(monitor2plus.assess_daily_delivery([], today)["ok"])
        self.assertFalse(monitor2plus.assess_daily_delivery(
            [release("2026-11-24", with_assets=False)], today)["ok"])
        self.assertTrue(monitor2plus.assess_daily_delivery(
            [release("2026-11-24")], today)["ok"])

    def test_repository_validation_and_bounded_github_request(self):
        with self.assertRaises(ValueError):
            monitor2plus.load_releases("../bad", "test",
                                       get=lambda *a, **kw: None)
        observed = []
        def get(url, **kw):
            observed.append((url, kw))
            return SimpleNamespace(
                raise_for_status=lambda: None,
                json=lambda: [release("2026-11-24")])
        out = monitor2plus.load_releases("org/repo", "example-token", get=get)
        self.assertEqual(len(out), 1)
        self.assertIn("/org/repo/releases", observed[0][0])
        self.assertEqual(observed[0][1]["timeout"], (5, 15))

    def test_health_marker_contains_no_secret_and_explicit_no_verification(self):
        edition = {
            "narrator": "Gemini Charon",
            "script_mode": "source-attributed RSS fallback",
            "quality_scorecard": {
                "distinct_source_links": 7,
                "sensitive_claims_for_review": ["review"],
                "official_pages_inspected": 1,
            },
            "script_quality": {"script_words": 640, "draft": {
                "provider_calls": 3, "retries": 1,
            }},
        }
        record = monitor2plus.health_record(
            "2026-11-24", edition, {"duration_seconds": 245,
                                  "duration_in_target": False})
        self.assertEqual(record["independently_verified_claims"], 0)
        self.assertEqual(record["gemini_text_requests"], 3)
        self.assertEqual(record["narrator"], "Gemini Charon")
        self.assertNotIn("token", str(record).lower())

    def test_archive_prior_release_assets_before_same_date_overwrite(self):
        tag = "first-light-2026-11-24"
        names = (tag + ".mp3", tag + ".txt", tag + "-evidence.json")
        observed_uploads = []
        with tempfile.TemporaryDirectory() as temp:
            def fake_gh(*args, **kwargs):
                if args[:3] == ("release", "view", tag):
                    return SimpleNamespace(returncode=0,
                                           stdout="\n".join(names) + "\n")
                if args[:3] == ("release", "download", tag):
                    original = args[args.index("--pattern") + 1]
                    dest = Path(args[args.index("--dir") + 1]) / original
                    dest.write_bytes(b"Earlier, already published episode")
                    return SimpleNamespace(returncode=0, stdout="")
                if args[:3] == ("release", "upload", tag):
                    observed_uploads.append(Path(args[3]))
                    return SimpleNamespace(returncode=0, stdout="")
                raise AssertionError(f"Unexpected gh command: {args}")
            with patch("src.first_light.WORK", Path(temp)), patch(
                "src.first_light.run_gh", side_effect=fake_gh
            ):
                first_light.archive_prior_release_assets(tag, "Initial release body")
            self.assertEqual(len(observed_uploads), 4)
            self.assertTrue(all(x.exists() for x in observed_uploads))
            self.assertTrue(any(x.name.endswith("-revision1.mp3")
                                for x in observed_uploads))
            self.assertTrue(any(x.name.endswith("-revision1-notes.md")
                                for x in observed_uploads))

    def test_archive_refuses_incomplete_previous_release(self):
        with tempfile.TemporaryDirectory() as temp, patch(
            "src.first_light.WORK", Path(temp)
        ), patch("src.first_light.run_gh", return_value=SimpleNamespace(
            returncode=0, stdout="first-light-2026-11-24.mp3\n"
        )) as gh:
            with self.assertRaisesRegex(RuntimeError, "incomplete"):
                first_light.archive_prior_release_assets(
                    "first-light-2026-11-24", "Old notes")
            self.assertEqual(gh.call_count, 1)

    def test_same_date_release_revisions_are_explicit_and_monotonic(self):
        first = first_light.release_revision_notes(
            "Previously published audio.",
            now=datetime(2026, 11, 24, 18, tzinfo=timezone.utc),
        )
        self.assertIn("FIRST_LIGHT_REVISION_V1:2", first)
        self.assertIn("no human-reviewed correction is implied", first)
        second = first_light.release_revision_notes(
            first, now=datetime(2026, 11, 24, 19, tzinfo=timezone.utc),
        )
        self.assertIn("FIRST_LIGHT_REVISION_V1:3", second)
        self.assertIn("Revision 2:", second)
        self.assertIn("Revision 3:", second)


if __name__ == "__main__":
    unittest.main()

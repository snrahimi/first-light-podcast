"""Offline tests: honest editorial scorecards and weather alert placement."""
import unittest
from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from src import quality2plus, broadcast32, first_light, newsroom3, editorial
from tests_support import editorial_groups

NOW = datetime(2026, 11, 23, 5, 0, tzinfo=ZoneInfo("America/Chicago"))


class Package2PlusQualityTests(unittest.TestCase):
    def test_sensitivity_and_repetition_are_flags_not_fact_check_claims(self):
        edition = editorial.curate(editorial_groups(), [], NOW)
        dossiers = newsroom3.build_dossiers(edition, [])
        first_card = next(iter(dossiers.values()))[0]
        first_card["editorial_review"]["sensitive_claims_present"] = True
        script = (
            "Good morning San Antonio, First Light: World Report in 2026. "
            + "The available report is attributed to the news publisher. " * 4
            + "Different developments are being reported by the press. " * 85
        )
        report = quality2plus.scorecard(
            script, dossiers, edition, {"nws_alert_check": "not verified"},
            "Gemini segmented evidence-led 3.2")
        self.assertFalse(report["human_review_completed"])
        self.assertFalse(not report["automation_is_not_fact_verification"])
        self.assertEqual(report["independently_verified_claims"], 0)
        self.assertGreaterEqual(len(report["sensitive_claims_for_review"]), 1)
        self.assertTrue(report["possible_repeated_sentences"])
        self.assertEqual(report["weather_alerts_reported"], None)
        self.assertIn("not fact-checks", quality2plus.public_notes(report))

    def test_priority_weather_requires_checked_nws_severity(self):
        self.assertEqual(first_light.early_weather_alert_intro({
            "nws_alert_check": "not verified",
            "nws_active_alerts": ["Tornado Warning for San Antonio"]
        }), "")
        self.assertEqual(first_light.early_weather_alert_intro({
            "nws_alert_check": "checked",
            "nws_active_alerts": ["Special Weather Statement"]
        }), "")
        intro = first_light.early_weather_alert_intro({
            "nws_alert_check": "checked",
            "nws_active_alerts": ["Tornado Warning for San Antonio"]
        })
        self.assertIn("Before the world news", intro)
        self.assertIn("Tornado Warning for San Antonio", intro)

    def test_early_alert_appears_before_world_section(self):
        edition = editorial.curate(editorial_groups(), [], NOW)
        dossiers = newsroom3.build_dossiers(edition, [])
        for chapter in dossiers.values():
            for d in chapter:
                d["official_context"] = []
                d["reporting_comparison"] = {
                    "independent_reporting_established": False,
                    "different_numbers_need_review": False,
                }
        calls = []
        section_a = "BBC reports an international diplomatic discussion. " * 30
        section_b = "NASA reports a scientific analysis and new research. " * 30
        def fake_post(*a, **k):
            calls.append(1)
            text = section_a if len(calls) == 1 else section_b
            return SimpleNamespace(status_code=200, json=lambda: {
                "candidates": [{"content": {"parts": [{"text": text}]}}
                ]})
        script, _ = broadcast32.generated_script(
            NOW, edition, dossiers, "San Antonio weather data unavailable.",
            "test", "gemini-3.5-flash-lite", post=fake_post,
            early_alert_text="National Weather Service: Tornado Warning."
        )
        self.assertIsNotNone(script)
        self.assertLess(script.index("Tornado Warning"), script.index("BBC reports"))

    def test_missing_nws_alert_check_keeps_uncertainty(self):
        weather = {"source": "unavailable", "nws_alert_check": "not verified"}
        narration = first_light.weather_narration(weather)
        self.assertIn("could not be verified", narration)
        self.assertNotIn("No active National Weather Service alerts", narration)


if __name__ == "__main__":
    unittest.main()

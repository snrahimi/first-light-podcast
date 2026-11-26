"""No-network proof that the live audition preview does not publish."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src import first_light_preview as preview
from src import elevenlabs_production


def fake_edition():
    return {
        "script_mode": "Gemini segmented evidence-led 3.2",
        "script_quality": {
            "estimated_duration_seconds": 348,
            "duration_preflight": {
                "status": "estimated_in_target",
            },
            "presentation_review": {
                "status": "advisory_only_not_independent_verification",
                "attribution_formula_count": 0,
            },
        },
        "lead_explainer_ready": 2,
        "lead_story_count": 2,
        "quality_scorecard": {
            "distinct_source_links": 4,
        },
    }


def fake_reading():
    # Real narration may have other content; these details are synthetic.
    return (
        "Good morning, San Antonio. This is First Light: World Report. "
        "We begin with the leading world developments. "
        "A public agency published new data today. "
        "According to the issuing agency, further details remain under review. "
        "Now let's turn to business, science and technology. "
        "A regional publication reported an economic update. "
        "And now, a look at the weather in San Antonio. "
        "Conditions will vary across the region. "
        "That's First Light: World Report. Thanks for listening."
    )


class PreviewSafetyTests(unittest.TestCase):
    def test_preview_runs_real_pipeline_calls_but_never_publishes(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "preview"
            def fake_synthesize(script, path):
                self.assertEqual(script, fake_reading())
                Path(path).write_bytes(b"ID3" + b"0" * 110000)
                return "ElevenLabs Brian"
            with (
                patch.object(preview.first_light, "fetch_weather",
                             return_value={"source": "NWS"}),
                patch.object(preview.first_light, "news_and_script",
                             return_value=(
                                 "Synthetic source notes",
                                 [{"title": "Example", "url": "https://example.org"}],
                                 fake_reading(),
                                 fake_edition(),
                             )),
                patch.object(preview.first_light, "synthesize",
                             side_effect=fake_synthesize) as synthesis,
                patch.object(preview.first_light, "inspect_audio",
                             return_value={
                                 "duration_seconds": 345.2,
                                 "duration_in_target": True,
                             }),
                patch.object(preview.first_light, "publish_release") as release,
                patch.object(preview.first_light, "list_releases") as releases,
                patch.object(preview.first_light, "web_page") as web_page,
            ):
                result = preview.run_preview(output=output)
            self.assertEqual(result["status"], "complete")
            self.assertTrue(result["unpublished"])
            self.assertEqual(result["narrator"], "ElevenLabs Brian")
            self.assertFalse(result["publication_performed"])
            release.assert_not_called()
            releases.assert_not_called()
            web_page.assert_not_called()
            synthesis.assert_called_once()
            self.assertIn("World Headlines",
                          (output / "transcript-preview.html").read_text())
            self.assertTrue((output / "first-light-preview.mp3").exists())
            self.assertEqual(
                (output / "first-light-preview.txt").read_text(),
                fake_reading(),
            )
            self.assertEqual(
                json.loads(
                    (output / "editorial-review.json").read_text()
                )["presentation_review"]["attribution_formula_count"], 0
            )

    def test_credit_failure_keeps_safe_text_artifact_without_publishing(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "preview"
            with (
                patch.object(preview.first_light, "fetch_weather",
                             return_value={"source": "NWS"}),
                patch.object(preview.first_light, "news_and_script",
                             return_value=("Notes", [], fake_reading(),
                                           fake_edition())),
                patch.object(preview.first_light, "synthesize",
                             side_effect=elevenlabs_production.NarratorFailure(
                                 "insufficient verified credits for complete narration"
                             )),
                patch.object(preview.first_light, "publish_release") as publish,
            ):
                with self.assertRaisesRegex(
                        RuntimeError, "audio unavailable"):
                    preview.run_preview(output=output)
            publish.assert_not_called()
            result = json.loads(
                (output / "editorial-review.json").read_text()
            )
            self.assertEqual(result["status"], "audio_not_created")
            self.assertIn("insufficient verified credits",
                          result["audio_failure_category"])
            self.assertFalse((output / "first-light-preview.mp3").exists())
            self.assertTrue((output / "first-light-preview.txt").exists())
            self.assertIn("UNPUBLISHED", (output / "transcript-preview.html").read_text())

    def test_html_escapes_source_content_and_links_only_local_preview(self):
        page = preview.build_html(
            'Good morning <script>alert(1)</script> to San Antonio.',
            "ElevenLabs Brian",
        )
        self.assertNotIn("<script>alert(1)</script>", page)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", page)
        self.assertIn('src="first-light-preview.mp3"', page)
        self.assertNotIn("feed.xml", page)
        self.assertNotIn('src="latest.mp3"', page)
        self.assertIn("noncommercial evaluation only", page)

    def test_workflow_is_one_shot_and_cannot_write_pages(self):
        workflow = (
            Path(__file__).resolve().parents[1]
            / ".github/workflows/first-light-preview.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("START FIRST LIGHT EDITORIAL PREVIEW (ONE SHOT)", workflow)
        self.assertIn("  workflow_dispatch:", workflow)
        self.assertIn("    branches: [main]", workflow)
        self.assertIn("path: preview-review/", workflow)
        self.assertIn("retention-days: 1", workflow)
        self.assertIn("  contents: read", workflow)
        self.assertNotIn("pages: write", workflow)
        self.assertNotIn("contents: write", workflow)
        self.assertNotIn("actions/deploy-pages", workflow)
        self.assertNotIn("python -m src.first_light\n", workflow)


if __name__ == "__main__":
    unittest.main()

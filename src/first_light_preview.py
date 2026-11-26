"""Produce one source-grounded, unpublished First Light editorial preview.

The preview uses the exact production news/weather/writer and Brian->Daniel
speech pipeline. It never calls publish_release, writes to SITE, changes RSS,
publishes GitHub Pages, or modifies the existing daily podcast.

This script is intended for an explicitly requested one-time Actions test.
Production TTS uses credits only if the verified account has enough for the
complete script. The generated audio and manuscript are temporary review
artifacts, not a production episode.
"""
from __future__ import annotations

from datetime import datetime
import html
import json
import logging
import os
from pathlib import Path
import sys

from . import first_light, elevenlabs_production, transcript_display

LOG = logging.getLogger("firstlight.preview")
PREVIEW_DIR = Path("preview-review")


def build_html(script, narrator=None):
    """A self-contained readable transcript with local audio, not live RSS."""
    voice = html.escape(narrator or "Audio unavailable")
    return (
        '<!doctype html><html lang="en"><head>'
        '<meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>First Light | Unpublished Editorial Preview</title>'
        '<style>body{background:#101b2b;color:#e7edf5;max-width:850px;'
        'margin:30px auto;padding:0 22px;font:17px/1.7 system-ui,'
        'Arial,sans-serif}h1,h2{line-height:1.25}a{color:#ffd1a5}'
        'audio{width:100%;margin:18px 0 24px}'
        + transcript_display.TRANSCRIPT_CSS
        + '</style></head><body>'
        '<header><h1>First Light: World Report</h1>'
        '<p><strong>UNPUBLISHED AUDIO TEST</strong> '
        'Not a released or independently verified news episode.</p>'
        '<p>Narrator: ' + voice + '</p>'
        '<p>Generated with <a href="https://elevenlabs.io">ElevenLabs</a>; '
        'noncommercial evaluation only.</p></header>'
        '<audio controls preload="metadata" src="first-light-preview.mp3">'
        'Audio preview is supplied separately.</audio>'
        '<h2>Preview Transcript</h2>'
        + transcript_display.render_transcript(script)
        + '</body></html>'
    )


def review_payload(edition, script, narrator=None, audio=None):
    """Public safe QA metadata; does NOT call presentation score verification."""
    metrics = edition["script_quality"]
    return {
        "status": "complete" if narrator and audio else "script_only",
        "unpublished": True,
        "narrator": narrator,
        "audio_quality": audio,
        "script_mode": edition["script_mode"],
        "script_words": len(script.split()),
        "tts_prepared_characters": len(
            elevenlabs_production.delivery_text(script)
        ),
        "presentation_review": metrics["presentation_review"],
        "lead_story_count": edition.get("lead_story_count"),
        "lead_explainer_ready": edition.get("lead_explainer_ready"),
        "estimated_duration_seconds": metrics["estimated_duration_seconds"],
        "estimated_duration_status": metrics["duration_preflight"]["status"],
        "quality_scorecard": edition["quality_scorecard"],
        "independent_fact_check_performed": False,
        "publication_performed": False,
    }


def run_preview(now=None, *, output=PREVIEW_DIR):
    """Compile actual source-grounded script then test production narration.

    Return an on-disk artifact set for review. If synthesis is unavailable,
    keep the non-billable transcript and fail rather than publishing.
    """
    now = now or datetime.now(first_light.TZ)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    # Source and script pipeline is read-only apart from its bounded
    # section-cache. No daily producer or publication function is called.
    weather = first_light.fetch_weather(now)
    notes, sources, script, edition = first_light.news_and_script(
        None, now, weather
    )
    (output / "first-light-preview.txt").write_text(
        script, encoding="utf-8"
    )
    (output / "source-notes.md").write_text(
        "# UNPUBLISHED FIRST LIGHT PREVIEW\n\n"
        "Automated source attribution is not independent fact verification.\n\n"
        + notes + "\n\n"
        + "\n".join(
            f"- [{source['title']}]({source['url']})"
            for source in sources
        ),
        encoding="utf-8",
    )
    summary = review_payload(edition, script)
    (output / "editorial-review.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # The caller explicitly requested a test. The production speech path
    # checks remaining credits and is permitted exactly one Brian attempt,
    # plus one Daniel backup if the failure is voice-specific/transient.
    audio_file = output / "first-light-preview.mp3"
    try:
        narrator = first_light.synthesize(script, audio_file)
        audio = first_light.inspect_audio(audio_file)
    except Exception as exc:
        # The production TTS backend logs no keys or provider response.
        # Avoid leaking arbitrary errors / request payloads in GH Actions.
        summary["status"] = "audio_not_created"
        summary["audio_failure_type"] = type(exc).__name__
        if isinstance(exc, elevenlabs_production.NarratorFailure):
            summary["audio_failure_category"] = exc.category
        (output / "editorial-review.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        (output / "transcript-preview.html").write_text(
            build_html(script), encoding="utf-8"
        )
        LOG.error("Unpublished audio preview failed safely: %s",
                  summary.get("audio_failure_category",
                              summary["audio_failure_type"]))
        raise RuntimeError("Unpublished preview audio unavailable") from None
    summary = review_payload(edition, script, narrator, audio)
    (output / "editorial-review.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (output / "transcript-preview.html").write_text(
        build_html(script, narrator), encoding="utf-8"
    )
    LOG.info(
        "Unpublished preview completed: narrator=%s, duration=%.1fs, "
        "words=%d, target_achieved=%s; no release, RSS or Pages writes",
        narrator, audio["duration_seconds"], len(script.split()),
        audio["duration_in_target"]
    )
    return summary


def main():
    for env in ("GITHUB_REPOSITORY", "GH_TOKEN", "ELEVENLABS_API_KEY"):
        first_light.required(env)
    result = run_preview()
    print(
        "First Light preview result: "
        f"narrator={result['narrator']}, "
        f"duration={result['audio_quality']['duration_seconds']}s, "
        f"words={result['script_words']}, "
        "publication=no."
    )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    try:
        main()
    except Exception:
        LOG.error("Preview exited without publishing")
        sys.exit(1)

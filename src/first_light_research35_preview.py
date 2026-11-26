"""Unpublished read-only Newsroom 3.5 Research Desk acceptance preview.

Uses the real source, weather and two-part editorial script paths but
does NOT synthesize any audio, change narrator preferences, or publish
GitHub Releases, RSS, Pages or the website. A separate optional audio
preview still requires a deliberate manual workflow dispatch.
"""
from __future__ import annotations

from datetime import datetime
import json
import logging
from pathlib import Path
import sys

from . import first_light, transcript_display, official_context36

LOG = logging.getLogger("firstlight.research35.preview")
OUT = Path("research-preview")


def run(*, now=None, output=OUT):
    now = now or datetime.now(first_light.TZ)
    target = Path(output)
    target.mkdir(parents=True, exist_ok=True)
    weather = first_light.fetch_weather(now)
    notes, sources, script, edition = first_light.news_and_script(None, now, weather)
    metrics = edition["script_quality"]
    research = metrics["research_desk35"]
    official_value = official_context36.review_official_context(
        edition.get("newsroom3_audit", {}).get("research_desk34", {}).get("lead_cards", [])
    )
    result = {
        "status": "research_preview_complete",
        "unpublished": True,
        "audio_generated": False,
        "elevenlabs_calls": 0,
        "production_voice_changed": False,
        "publication_performed": False,
        "script_mode": edition["script_mode"],
        "script_words": len(script.split()),
        "selected_stories": edition["count"],
        "original_source_links": len(sources),
        "world_leads": len(edition["rundown"].get("Top world headlines", [])),
        "research_desk35": research,
        "official_context36_unpublished_editorial_value_audit": official_value,
        "source_attributed_claims": edition["newsroom3_audit"]["attributed_claims"],
        "independent_fact_checks": 0,
        "gemini_writing_requests": metrics["draft"].get("provider_calls", 0),
        "fallback_reason": metrics["draft"].get("reason"),
        "cold_open": metrics["newsroom33"]["cold_open"],
        "duration_estimated_seconds": metrics["estimated_duration_seconds"],
        "duration_target_achieved": metrics["duration_preflight"]["estimated_in_target"],
        "explanation": (
            "Source matching and exact excerpts are evidence of published "
            "statements, not independent verification of the underlying facts."
        ),
    }
    (target / "research-review.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (target / "research-transcript.txt").write_text(
        script + "\n", encoding="utf-8",
    )
    (target / "research-transcript.html").write_text(
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<title>First Light | Unpublished Research Desk Test</title>"
        "<style>body{font:17px/1.6 system-ui;max-width:850px;"
        "margin:2rem auto;padding:0 1rem}"
        + transcript_display.TRANSCRIPT_CSS
        + "</style></head><body><h1>First Light Research Desk 3.5</h1>"
        "<p><strong>Unpublished script-only test. No audio generated.</strong>"
        " Automated attribution is not independent fact checking.</p>"
        + transcript_display.render_transcript(script) + "</body></html>",
        encoding="utf-8",
    )
    (target / "source-notes.md").write_text(
        "# Unpublished First Light Research Desk 3.5\n\n"
        "Machine-attributed source claims, not independently verified events.\n\n"
        + notes + "\n\n" + "\n".join(
            "- [" + str(x.get("title", "Original reporting")).replace(
                "[", "").replace("]", "") + "](" + x["url"] + ")"
            for x in sources if x.get("url", "").startswith("https://")
        ) + "\n",
        encoding="utf-8",
    )
    LOG.info(
        "Unpublished Research Desk 3.5: %s; %d words; %d same-event "
        "reports linked, %d official pages read; TTS=0, publish=no.",
        edition["script_mode"], len(script.split()),
        research["event_links"]["added_source_reports"],
        research["official_source_retrieval"]["accepted_documents"],
    )
    return result


def main():
    for required in ("GITHUB_REPOSITORY", "GH_TOKEN"):
        first_light.required(required)
    result = run()
    print(
        "Research Desk 3.5 test complete: "
        + str(result["script_words"]) + " words; mode="
        + result["script_mode"] + "; narration=no; publication=no."
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        main()
    except Exception:
        LOG.error("Research-only preview failed safely; nothing was published")
        sys.exit(1)

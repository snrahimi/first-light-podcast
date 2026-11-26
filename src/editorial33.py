"""Newsroom 3.3 presentation helpers. No network, model, or TTS calls.

Source metadata and previous-episode headlines are only editorial cues,
not verification. Cold-open text is produced by the existing source-gated
world-section writer; this code merely separates it for ordering.
"""
from __future__ import annotations

import re

PREVIEW_PATTERN = re.compile(
    r"^PREVIEW:\s*(?P<preview>.+?)\s+STORY:\s*(?P<story>.+)$",
    re.I | re.S,
)
MAX_PACKAGE_HEADLINE = 68


def _brief_label(value, *, max_length=MAX_PACKAGE_HEADLINE):
    """Clean a source headline for metadata, without inventing new words."""
    label = " ".join(str(value or "").split()).strip(". ")
    if len(label) > max_length:
        label = label[:max_length].rsplit(" ", 1)[0].rstrip(".,;: ")
    return label


def topic_packaging(edition):
    """Grounded episode labels for editorial review and public metadata.

    Titles do not replace RSS identifiers, source attributions, or original
    headlines. An episode teaser is not proof that a story is verified.
    """
    rundown = edition.get("rundown", {})
    leads = rundown.get("Top world headlines", [])[:2]
    titles = [_brief_label(x.get("title")) for x in leads]
    titles = [t for t in titles if t]
    section_counts = {
        name: len(stories) for name, stories in rundown.items()
    }
    return {
        "display_title": (
            "First Light | " + " / ".join(titles)
            if titles else "First Light: World Report"
        ),
        "lead_headlines": [
            {"headline": x.get("title", ""),
             "publisher": x.get("publisher", ""),
             "url": x.get("url", "")}
            for x in leads
        ],
        "section_counts": section_counts,
        "attribution_required": True,
        "headlines_not_independently_verified": True,
    }


def continuity_card(story):
    """Advisory follow-up metadata, not a claim that something changed."""
    freshness = story.get("freshness") or {}
    previous = story.get("previous")
    if not isinstance(previous, dict) or not previous.get("headline"):
        return {
            "type": "new_to_show_or_no_prior_record",
            "previous_headline": None,
            "verified_new_detail": False,
            "rule": "Do not call it a follow-up without an actual prior record.",
        }
    return {
        "type": "possibly_continuing_story",
        "previous_headline": str(previous.get("headline")),
        "previous_edition_date": previous.get("date"),
        "prior_status": freshness.get("prior_edition_coverage"),
        "verified_new_detail": False,
        "rule": (
            "Previous episode history is a headline memory only. "
            "Compare with today's sourced excerpts and only describe "
            "what changed if today's excerpts explicitly support it. "
            "Never infer progress or repeat an old claim as new."
        ),
    }


def split_preview(world_section):
    """Separate an optional structured 20-second hook from the world report.

    Exactly two markers are required; malformed generation falls back
    to the complete report, never fabricating a teaser or stripping news.
    """
    raw = " ".join(str(world_section or "").split())
    hit = PREVIEW_PATTERN.fullmatch(raw)
    if not hit:
        # Guard against narrating a model-produced label on partial output.
        safe = re.sub(r"^PREVIEW:\s*", "", raw, flags=re.I)
        safe = re.sub(r"\bSTORY:\s*", "", safe, count=1, flags=re.I)
        return "", safe, {"mode": "unstructured_world_section", "preview_words": 0}
    preview, report = hit.group("preview").strip(), hit.group("story").strip()
    count = len(preview.split())
    if not (16 <= count <= 48 and len(report.split()) >= 95):
        return "", report, {
            "mode": "rejected_preview_limits",
            "preview_words": 0,
        }
    if re.search(r"(?i)\b(?:https?://|www\.)", preview):
        return "", report, {
            "mode": "rejected_preview_link",
            "preview_words": 0,
        }
    return preview, report, {
        "mode": "structured_two_story_preview",
        "preview_words": count,
    }


def continuing_story_review(material):
    """Count source-linked stories with earlier coverage, never assert change."""
    cards = [card for chapter in material.values() for card in chapter]
    needs_check = [
        card.get("headline", "") for card in cards
        if isinstance(card.get("continuity"), dict)
        and card["continuity"].get("type") == "possibly_continuing_story"
    ]
    return {
        "possible_followups": len(needs_check),
        "possible_followup_headlines": needs_check[:8],
        "source_grounded_change_verified": False,
        "basis": "headline history used as editorial cue; current reporting required",
    }

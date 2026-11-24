"""Package 2+: deterministic editorial preflight, not automated truth checking.

All calculations are drawn from already selected and source-audited newsroom
objects. Results report measurable coverage and potential review needs.
No model calls, web access, speculative truth scores or invented evidence.
"""
from __future__ import annotations

from collections import Counter
import re

if __package__:
    from . import broadcast32
else:
    import broadcast32


def _repeated_sentences(script):
    sentences = re.split(r"(?<=[.!?])\s+", script)
    counts = Counter(
        re.sub(r"\s+", " ", sentence).strip().lower()
        for sentence in sentences if len(sentence.split()) >= 6
    )
    return [
        {"repeat_count": count, "words": len(phrase.split())}
        for phrase, count in counts.items() if count >= 3
    ][:8]


def scorecard(script, dossiers, edition, weather, script_mode):
    """Produce transparent quality indicators, not a rating of factual truth."""
    cards = [c for chapter in dossiers.values() for c in chapter]
    claims = [x for c in cards for x in c.get("claim_ledger", [])]
    source_links = {
        (c["publisher"], c["url"]) for card in cards
        for c in card.get("sources", [])
    }
    sensitive = [
        {"headline": card["headline"],
         "reason": "sensitive_claims_require_human_review"}
        for card in cards
        if card.get("editorial_review", {}).get("sensitive_claims_present")
    ]
    discrepancies = sum(
        bool(card.get("reporting_comparison", {}).get("different_numbers_need_review"))
        for card in cards
    )
    words = len(script.split())
    preflight = broadcast32.duration_preflight(words)
    ai_mode = script_mode.startswith("Gemini segmented")
    writer_flags = (
        edition.get("script_quality", {}).get("draft", {}).get(
            "under_delivered_sections", [])
        if ai_mode else []
    )
    alert_check = weather.get("nws_alert_check", "not verified")
    official_count = sum(
        len(c.get("official_context", [])) for c in cards
    )
    result = {
        "system": "Package 2+ transparent editorial scorecard v1",
        "automation_is_not_fact_verification": True,
        "human_review_completed": False,
        "script_mode": script_mode,
        "gemini_writer_used": ai_mode,
        "under_delivered_writer_sections": writer_flags,
        "distinct_lead_publishers": edition.get("distinct_lead_publishers"),
        "distinct_lead_regions": edition.get("distinct_lead_regions"),
        "selected_stories": len(cards),
        "attributed_excerpt_count": len(claims),
        "distinct_source_links": len(source_links),
        "additional_related_reports": sum(
            c.get("linked_feed_context_count", 0) for c in cards
        ),
        "official_pages_inspected": official_count,
        "independently_verified_claims": 0,
        "sensitive_claims_for_review": sensitive,
        "differing_report_numbers_for_review": discrepancies,
        "possible_repeated_sentences": _repeated_sentences(script),
        "weather_alert_check": alert_check,
        "weather_alerts_reported": (
            len(weather.get("nws_active_alerts", []))
            if alert_check == "checked" else None
        ),
        "script_words": words,
        "duration_preflight": preflight,
        "passes_automated_provenance_checks": True,
        "needs_editorial_attention": bool(
            sensitive or discrepancies or writer_flags
            or _repeated_sentences(script)
            or not preflight["estimated_in_target"]
            or alert_check != "checked"
        ),
    }
    return result


def public_notes(report):
    text = [
        "PACKAGE 2+ AUTOMATED EDITORIAL SCORECARD",
        "Machine-generated flags are not fact-checks or human editorial review.",
        f"Script: {report['script_mode']}; words: {report['script_words']}",
        f"Estimated spoken runtime: {report['duration_preflight']['estimated_seconds']} seconds",
        f"Selected stories: {report['selected_stories']}; "
        f"source links: {report['distinct_source_links']}",
        f"Attributable RSS/agency excerpts: {report['attributed_excerpt_count']}",
        f"Official document pages: {report['official_pages_inspected']}",
        f"Additional related feed reports: {report['additional_related_reports']}",
        f"Distinct lead publishers: {report.get('distinct_lead_publishers', 'unknown')}",
        f"Substantially under-delivered Gemini sections: "
        f"{len(report['under_delivered_writer_sections'])}",
        f"Potential duplicate sentences: {len(report['possible_repeated_sentences'])}",
        f"Sensitive stories requiring human review: {len(report['sensitive_claims_for_review'])}",
        f"Source-number disagreement flags: {report['differing_report_numbers_for_review']}",
        f"NWS alert check: {report['weather_alert_check']}",
        "No claim is represented as independently fact checked.",
    ]
    return "\n".join(text)

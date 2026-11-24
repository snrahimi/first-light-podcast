"""Package 2+ GitHub-native delivery watchdog and rolling production metrics.

No separate hosted monitoring, email account or paid API. Release markers
describe published audio and writing mode, NOT independent fact verification.
"""
from __future__ import annotations

import base64
from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
from zoneinfo import ZoneInfo

import requests

CENTRAL = ZoneInfo("America/Chicago")
HEALTH_MARKER = "FIRST_LIGHT_HEALTH_V1:"
MAX_RELEASES = 60
RELEASE_TAG = re.compile(r"^first-light-(\d{4}-\d{2}-\d{2})$")


def health_record(day, edition, audio):
    """Compact, public operational metadata recorded with the release."""
    report = edition.get("quality_scorecard", {})
    draft = edition.get("script_quality", {}).get("draft", {})
    return {
        "day": day,
        "narrator": edition.get("narrator", ""),
        "script_mode": edition.get("script_mode", ""),
        "duration_seconds": round(audio["duration_seconds"], 1),
        "in_duration_target": bool(audio.get("duration_in_target", False)),
        "script_words": edition.get("script_quality", {}).get("script_words", 0),
        "sources": report.get("distinct_source_links", 0),
        "official_documents": report.get("official_pages_inspected", 0),
        "related_feed_reports": report.get("additional_related_reports", 0),
        "sensitive_review_flags": len(report.get("sensitive_claims_for_review", [])),
        "independently_verified_claims": 0,
        "gemini_text_requests": draft.get("provider_calls", 0),
        "writer_cache_hits": draft.get("cache_hits", 0),
        "writer_retries": draft.get("retries", 0),
    }


def encode_health(record):
    payload = json.dumps(record, ensure_ascii=True, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    return "<!-- " + HEALTH_MARKER + base64.urlsafe_b64encode(
        payload).decode().rstrip("=") + " -->"


def decode_health(release):
    match = re.search(
        r"<!--\s*" + HEALTH_MARKER + r"([A-Za-z0-9_-]{1,3000})\s*-->",
        str(release.get("body", "")),
    )
    if not match:
        return None
    try:
        raw = match.group(1)
        data = json.loads(base64.urlsafe_b64decode(
            raw + "=" * (-len(raw) % 4)))
        if isinstance(data, dict) and data.get("day") == (
            str(release["tag_name"]).removeprefix("first-light-")
        ):
            return data
    except (ValueError, TypeError, KeyError):
        return None
    return None


def rolling_report(releases, today):
    """Operational statistics over recent calendar dates, not all-time."""
    valid = {}
    for release in releases:
        match = RELEASE_TAG.fullmatch(str(release.get("tag_name", "")))
        if not match:
            continue
        try:
            day = date.fromisoformat(match.group(1))
        except ValueError:
            continue
        if day > today or day < today - timedelta(days=29):
            continue
        valid[day.isoformat()] = release
    metadata = [decode_health(item) for item in valid.values()]
    measured = [row for row in metadata if row]
    good_durations = [
        row["duration_seconds"] for row in measured
        if isinstance(row.get("duration_seconds"), (int, float))
    ]
    return {
        "window_days": 30,
        "through_date": today.isoformat(),
        "episodes_found": len(valid),
        "days_without_release": 30 - len(valid),
        "episodes_with_quality_metadata": len(measured),
        "older_episodes_without_quality_metadata": len(valid) - len(measured),
        "charon_episodes_measured": sum(
            row.get("narrator") == "Gemini Charon" for row in measured
        ),
        "five_to_seven_minute_episodes": sum(
            bool(row.get("in_duration_target")) for row in measured
        ),
        "rss_script_fallbacks": sum(
            row.get("script_mode") == "source-attributed RSS fallback"
            for row in measured
        ),
        "text_writer_request_total": sum(
            row.get("gemini_text_requests", 0) for row in measured
        ),
        "official_source_pages_total": sum(
            row.get("official_documents", 0) for row in measured
        ),
        "mean_duration_seconds": (
            round(sum(good_durations) / len(good_durations), 1)
            if good_durations else None
        ),
        "metric_limitations": (
            "Coverage of duration and script metrics begins only when "
            "public FIRST_LIGHT_HEALTH_V1 release metadata is present. "
            "Publication is best effort and no claim is independently fact checked."
        ),
    }


def assess_daily_delivery(releases, today):
    tag = "first-light-" + today.isoformat()
    release = next((r for r in releases if r.get("tag_name") == tag), None)
    if release is None:
        return {"ok": False, "reason": "release_not_found", "tag": tag}
    assets = {str(asset.get("name")): int(asset.get("size", 0))
              for asset in release.get("assets", [])}
    required = {
        tag + ".mp3": 100_000,
        tag + ".txt": 500,
        tag + "-evidence.json": 200,
    }
    missing = [name for name, minimum in required.items()
               if assets.get(name, 0) < minimum]
    return {
        "ok": not missing, "tag": tag,
        "reason": "published_assets_present" if not missing else "missing_or_small_assets",
        "problem_assets": missing,
        "release_url": release.get("html_url", ""),
    }


def load_releases(repository, token, *, get=requests.get):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("Invalid GitHub repository identifier")
    if not token:
        raise RuntimeError("Missing GitHub token for monitoring")
    response = get(
        f"https://api.github.com/repos/{repository}/releases",
        params={"per_page": MAX_RELEASES},
        timeout=(5, 15),
        headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, list):
        raise ValueError("Unexpected GitHub release response")
    return data


def main():
    today = datetime.now(CENTRAL).date()
    releases = load_releases(
        os.getenv("GITHUB_REPOSITORY", ""),
        os.getenv("GH_TOKEN", ""),
    )
    delivery = assess_daily_delivery(releases, today)
    history = rolling_report(releases, today)
    lines = [
        "# First Light daily delivery watchdog",
        f"Local date: {today.isoformat()}",
        f"Release: {delivery['tag']}",
        f"Delivery: {'PASS' if delivery['ok'] else 'CHECK REQUIRED'}",
        f"Reason: {delivery['reason']}",
        f"Published episodes in 30-day calendar window: {history['episodes_found']}",
        f"Episodes with operational metadata: {history['episodes_with_quality_metadata']}",
        f"5-7 minute episodes among measured: {history['five_to_seven_minute_episodes']}",
        f"Fallback scripts among measured: {history['rss_script_fallbacks']}",
        "Missing episodes and source claims require human assessment.",
    ]
    output = "\n".join(lines) + "\n"
    print(output)
    summary = os.getenv("GITHUB_STEP_SUMMARY", "")
    if summary:
        with Path(summary).open("a", encoding="utf-8") as handle:
            handle.write(output)
    if not delivery["ok"]:
        raise RuntimeError(
            f"Daily delivery requires investigation: {delivery['reason']}"
        )


if __name__ == "__main__":
    main()

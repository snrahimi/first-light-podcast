"""Read-only audit and manual-only audition of official default-voice successors.

Brian -> Sawyer, Daniel -> Finley per ElevenLabs' 2026 Default
retirement documentation. Listing a shared/library voice does NOT grant
Free-tier API access. A TTS request requires a positive paid-plan,
voice metadata, and credit preflight, then a separate user-triggered
manual GitHub Actions workflow. No daily production configuration edits.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

import requests

if __package__:
    from . import elevenlabs_audition as audition
else:
    import elevenlabs_audition as audition


CANDIDATES = {
    "sawyer": {
        "name": "Sawyer - Midnight Storyteller",
        "id": "8dEUmyPMdDdK91vboYih",
        "replaces": "Brian",
        "prior_id": "nPczCjzI2devNBz1zQrb",
    },
    "finley": {
        "name": "Finley - Articulate Anchor",
        "id": "fnYMz3F5gMEDGMWcH1ex",
        "replaces": "Daniel",
        "prior_id": "onwK4e9ZLuTAKqWW03F9",
    },
}
SUBSCRIPTION = "https://api.elevenlabs.io/v1/user/subscription"
VOICE = "https://api.elevenlabs.io/v1/voices/"
PAID = {"starter", "creator", "pro", "scale", "business", "enterprise"}
LIBRARY_TYPES = {"professional", "community", "famous", "shared"}
OUTPUT = Path("voice-retirement-audit")


def _get_meta(url, key, *, get=requests.get):
    """Return only validated status and metadata, never raw exceptions."""
    try:
        response = get(
            url,
            headers={"xi-api-key": key, "Accept": "application/json"},
            timeout=(6, 15), allow_redirects=False,
        )
        if response.status_code != 200:
            return response.status_code, {}
        value = response.json()
        return 200, value if isinstance(value, dict) else {}
    except (requests.RequestException, ValueError, TypeError, AttributeError):
        return None, {}


def audit(key, *, get=requests.get):
    """Exactly three authenticated GETs, zero speech generations."""
    if not key:
        raise RuntimeError("ELEVENLABS_API_KEY required for metadata-only audit")
    status, account = _get_meta(SUBSCRIPTION, key, get=get)
    tier = str(account.get("tier") or "").lower()
    plan = "free" if tier in ("free", "free_disabled") else (
        "paid" if tier in PAID else "unknown"
    )
    count, limit = account.get("character_count"), account.get("character_limit")
    headroom = (
        max(0, limit - count)
        if type(count) is int and type(limit) is int
        and 0 <= count <= limit else None
    )
    voices = {}
    for alias, candidate in CANDIDATES.items():
        voice_status, info = _get_meta(VOICE + candidate["id"], key, get=get)
        exists = voice_status == 200 and info.get("voice_id") == candidate["id"]
        category = info.get("category") if exists else None
        shared = isinstance(info.get("sharing"), dict) if exists else False
        tiers = info.get("available_for_tiers") if exists else None
        library = shared or category in LIBRARY_TYPES
        explicit_free_denial = (
            isinstance(tiers, list) and bool(tiers) and "free" not in tiers
        )
        blocked_free = plan == "free" and (library or explicit_free_denial)
        # A checked, paid key removes the known Free Voice Library block,
        # but it NEVER proves synthesis rights without the TTS audition.
        possible = bool(
            exists and plan == "paid" and headroom is not None
            and headroom >= len(audition.SAMPLE)
        )
        voices[alias] = {
            "name": candidate["name"],
            "replaces": candidate["replaces"],
            "listed_in_account_voice_metadata": exists,
            "category": (str(category)[:30] if category else "unknown"),
            "library_voice": library if exists else None,
            "known_free_tier_api_block": blocked_free,
            "read_only_audition_eligible": possible,
            "real_tts_audition_passed": False,
            "human_listening_review_passed": False,
            "reason": (
                "voice not visible to this API key" if not exists else
                "Voice Library API restricted on Free" if blocked_free else
                "account tier or verified credits unknown" if not possible else
                "candidate for one manually approved TTS sample"
            ),
        }
    return {
        "audit_version": 1,
        "plan": plan,
        "account_metadata_status": "available" if status == 200 else "unavailable",
        "credit_headroom": (
            "enough_for_one_conservative_sample"
            if headroom is not None and headroom >= len(audition.SAMPLE)
            else "insufficient_or_unverifiable"
        ),
        "text_to_speech_calls": 0,
        "production_voice_unchanged": True,
        "monthly_credit_amounts_not_logged": True,
        "candidates": voices,
        "official_retirement_date": "2026-12-31",
        "licensing_note": (
            "Free ElevenLabs outputs require noncommercial use and attribution. "
            "Paid API access does not independently establish commercial "
            "publication rights until the selected paid plan is confirmed."
        ),
    }


def audition_one(alias, key, *, get=requests.get, post=requests.post,
                 output=OUTPUT, probe=audition.inspect_mp3):
    """Only explicit manual invocation may make one chargeable TTS call."""
    if alias not in CANDIDATES:
        raise ValueError("Select Sawyer or Finley from the fixed candidate list")
    result = audit(key, get=get)
    state = result["candidates"][alias]
    if not state["read_only_audition_eligible"]:
        raise RuntimeError(
            "Selected replacement lacks verified paid API/credit eligibility; "
            "audition stopped before TTS. Production unchanged."
        )
    # Strict spend cap from existing original audition: <=820 chars,
    # <=160 spoken words, one provider call, no retries.
    audition.audition_payload()
    audio = audition.request_sample(key, CANDIDATES[alias]["id"], post=post)
    target_dir = Path(output)
    target_dir.mkdir(parents=True, exist_ok=True)
    temp = target_dir / "voice.partial.mp3"
    dest = target_dir / ("first-light-" + alias + "-audition.mp3")
    try:
        temp.write_bytes(audio)
        duration = probe(temp)
        temp.replace(dest)
    finally:
        temp.unlink(missing_ok=True)
    # Successful audio does NOT qualify a voice for production; human
    # review for clarity, licensing and pronunciation is still required.
    data = {
        "candidate": CANDIDATES[alias]["name"],
        "replaces": CANDIDATES[alias]["replaces"],
        "duration_seconds": duration,
        "tts_requests": 1,
        "script_characters": len(audition.SAMPLE),
        "audio_validated": True,
        "human_listening_approval": False,
        "production_changed": False,
    }
    (target_dir / "audition-script.txt").write_text(
        audition.SAMPLE, encoding="utf-8"
    )
    (target_dir / "audition-result.json").write_text(
        json.dumps(data, indent=2), encoding="utf-8"
    )
    return data


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    if not key:
        raise RuntimeError("Missing ElevenLabs API secret")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    if argv == ["audit"]:
        result = audit(key)
        (OUTPUT / "account-access-audit.json").write_text(
            json.dumps(result, indent=2), encoding="utf-8"
        )
        print(
            "Replacement voice read-only audit: plan=" + result["plan"]
            + "; Sawyer=" + result["candidates"]["sawyer"]["reason"]
            + "; Finley=" + result["candidates"]["finley"]["reason"]
            + "; TTS requests=0, production unchanged."
        )
    elif len(argv) == 2 and argv[0] == "audition":
        data = audition_one(argv[1], key)
        print(
            "Replacement audition validated: " + data["candidate"]
            + f", duration={data['duration_seconds']}s; "
            "no publication and no automatic switch to production."
        )
    else:
        raise SystemExit("Usage: voice_retirement audit | audition sawyer|finley")


if __name__ == "__main__":
    main()

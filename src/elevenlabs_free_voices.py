"""Read-only shortlist and opt-in noncommercial auditions for classic Default voices.

The API's community Voice Library is unavailable to free-plan API users.
The four historic Default voices below are being sunset on 2026-12-31.
Access is limited to older accounts; never assume a voice ID is entitled.
No voice synthesis occurs during discovery. This module does not affect
the daily Charon podcast.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys

import requests

from . import elevenlabs_audition as audition

# These published, historical Default IDs belong to ElevenLabs, not to
# individual community sharers. Do not mistake Infinity/library replacements
# for free API voices. Availability is checked at run time.
SHORTLIST = {
    "daniel": {
        "name": "Daniel",
        "style": "British male, formal world-news anchor",
        "id": "onwK4e9ZLuTAKqWW03F9",
    },
    "brian": {
        "name": "Brian",
        "style": "Warm male storyteller, reflective podcast host",
        "id": "nPczCjzI2devNBz1zQrb",
    },
    "chris": {
        "name": "Chris",
        "style": "Approachable male, conversational morning briefing",
        "id": "iP95p4xoKVk53GoZ742B",
    },
    "alice": {
        "name": "Alice",
        "style": "Polished female presenter, international tone",
        "id": "Xb7hH8MSUJpSbSDYk0k2",
    },
}

DEFAULT_VOICE_URL = (
    "https://api.elevenlabs.io/v2/voices?"
    "voice_type=default&page_size=100"
)
SUBSCRIPTION_URL = "https://api.elevenlabs.io/v1/user/subscription"


def discover(api_key, *, get=requests.get, announce=True):
    """Use only authenticated GETs; return names of *listed* defaults.

    Do not log account metadata, unexpected voice names, raw response bodies
    or IDs. False negatives are safer than paid HTTP 402 requests.
    """
    if not api_key:
        raise RuntimeError("ELEVENLABS_API_KEY secret required")
    account = audition._read_only_metadata(
        SUBSCRIPTION_URL, api_key, get=get,
    )
    tier = str(account.get("tier", "")).lower()
    plan = "free" if tier == "free" else (
        "paid" if tier in ("starter", "creator", "pro", "scale",
                           "business", "enterprise") else "unknown"
    )
    catalog = audition._read_only_metadata(
        DEFAULT_VOICE_URL, api_key, get=get,
    )
    rows = catalog.get("voices")
    metadata_status = "available" if isinstance(rows, list) else "unavailable"
    usable = {}
    if isinstance(rows, list):
        for alias, info in SHORTLIST.items():
            record = next((
                voice for voice in rows
                if isinstance(voice, dict)
                and voice.get("voice_id") == info["id"]
            ), None)
            if record is None or record.get("category") != "premade":
                continue
            # These must be Default, premade and not community shared.
            if isinstance(record.get("sharing"), dict):
                continue
            tiers = record.get("available_for_tiers")
            if (isinstance(tiers, list) and tiers and
                    plan == "free" and "free" not in tiers):
                continue
            usable[alias] = info

    result = {
        "plan": plan,
        "metadata_status": metadata_status,
        "choices": usable,
    }
    if announce:
        print(
            "First Light free-voice discovery: "
            f"plan={plan}, default_catalog={metadata_status}, "
            f"shortlisted_voices_listed={len(usable)}, TTS_requests=0."
        )
        for alias, info in usable.items():
            print(
                "Candidate: " + alias + " (" + info["name"]
                + "): " + info["style"]
            )
        if metadata_status == "unavailable":
            print(
                "Default voice listing unavailable with this API key. "
                "Voice metadata read permission may be required; "
                "no free API candidates are confirmed."
            )
        elif not usable:
            print(
                "No shortlisted classic Default voices available. "
                "These voices are limited to pre-March-2026 accounts "
                "and end 2026-12-31. Consider designing a personal "
                "voice with ElevenLabs Voice Design on your free plan."
            )
        else:
            print(
                "Listed is not a promise of TTS entitlement; use "
                "audition_one only to spend credits on one voice."
            )
    return result


def audition_one(alias, api_key, *, get=requests.get, run=None):
    """Synthesize a single selected candidate only after default listing.

    Tests inject 'run' to assert no paid request occurs if absent.
    """
    if alias not in SHORTLIST:
        raise ValueError("Unsupported free-voice shortlist choice")
    found = discover(api_key, get=get, announce=True)
    if alias not in found["choices"]:
        raise RuntimeError(
            "Selected classic Default voice is not confirmed for this "
            "account; no TTS API request made. Run discover_only, "
            "or try a personal Voice Design voice instead."
        )
    candidate = found["choices"][alias]
    synthesizer = run or audition.main
    synthesizer(voice_id_override=candidate["id"])
    output = Path("voice-audition")
    output.joinpath("candidate.txt").write_text(
        "Audition candidate: " + candidate["name"] + "\n"
        "Noncommercial voice comparison; Gemini Charon unchanged.\n",
        encoding="utf-8",
    )
    print(
        "Finished " + candidate["name"] +
        " audition; no changes to public podcast or live voice."
    )


def main(argv=None):
    arguments = sys.argv[1:] if argv is None else argv
    if arguments == ["discover"]:
        discover(os.environ.get("ELEVENLABS_API_KEY", "").strip())
    elif len(arguments) == 2 and arguments[0] == "audition":
        audition_one(
            arguments[1],
            os.environ.get("ELEVENLABS_API_KEY", "").strip(),
        )
    else:
        raise SystemExit(
            "Usage: python -m src.elevenlabs_free_voices discover "
            "| audition [daniel|brian|chris|alice]"
        )


if __name__ == "__main__":
    main()

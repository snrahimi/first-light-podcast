"""Single-call, manual-only ElevenLabs sample for noncommercial voice comparison.

This is NOT wired into the daily producer or public podcast feeds.
Only invoke with two repository secrets from the manual audition workflow.
Do not log, print, or persist the credentials.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys

import requests

MODEL = "eleven_flash_v2_5"
OUTPUT_FORMAT = "mp3_44100_128"
MAX_CHARACTERS = 820
MAX_AUDIO_BYTES = 3_000_000

# Original demonstration text; no actual news events are asserted.
SAMPLE = (
    "Good morning, San Antonio. This is First Light: World Report, "
    "a calm, clear look at the stories shaping our world. "
    "Ahead, we will explore international diplomacy, global markets, "
    "advances in science, and the latest developments in cybersecurity. "
    "Our reporting separates official statements from claims attributed "
    "to publishers, and we note when important details are still uncertain. "
    "From Washington to London, from Tokyo to Nairobi, each story "
    "deserves context, care, and an easy-to-follow explanation. "
    "We will also keep an eye on local weather before your day gets underway. "
    "Whether you're making coffee, heading into work, or starting "
    "the morning on the road, thank you for joining us. "
    "This is First Light. The world, before your day."
)


def audition_payload(text=SAMPLE):
    """Reject long or empty text *before* any billable request."""
    if not isinstance(text, str) or not 90 <= len(text.split()) <= 160:
        raise ValueError("Audition must be a 90-160-word original script")
    if len(text) > MAX_CHARACTERS:
        raise ValueError("Audition exceeds strict 820-character budget")
    return {
        "text": text,
        "model_id": MODEL,
        "voice_settings": {
            "stability": 0.62,
            "similarity_boost": 0.78,
        },
    }



# Only interpret documented, known error codes. Never print arbitrary
# response bodies, error messages, headers, voice IDs, or account details:
# GitHub Actions logs on a public repository may be publicly accessible.
SAFE_ERROR_REASONS = {
    "paid_plan_required": "selected voice or feature requires a paid plan",
    "subscription_required": "selected feature requires a paid plan",
    "insufficient_credits": "insufficient available credits",
    "quota_exceeded": "available account/API-key quota exceeded",
    "payment_required": "payment, credits or subscription access required",
    "free_users_not_allowed": "selected voice is restricted on the free tier",
    "feature_not_available": "feature not available on this plan",
    "invalid_api_key": "API key invalid",
}


def _safe_error_reason(response):
    """Read only a known status code, discarding potentially sensitive text."""
    try:
        payload = response.json()
        detail = payload.get("detail", {}) if isinstance(payload, dict) else {}
        if not isinstance(detail, dict):
            return "cause unknown; check plan, credits and voice access"
        code = detail.get("code") or detail.get("status")
        if isinstance(code, str):
            return SAFE_ERROR_REASONS.get(
                code, "cause unknown; check plan, credits and voice access"
            )
    except (ValueError, TypeError, AttributeError):
        pass
    return "cause unknown; check plan, credits and voice access"


def _read_only_metadata(url, key, *, get=requests.get):
    """Read API metadata using GET, with no speech generation or retries."""
    try:
        response = get(
            url,
            headers={"xi-api-key": key, "Accept": "application/json"},
            timeout=(6, 14),
            allow_redirects=False,
        )
        if response.status_code != 200:
            return {}
        value = response.json()
        return value if isinstance(value, dict) else {}
    except (requests.RequestException, ValueError, TypeError, AttributeError):
        return {}


def diagnose_access(api_key, voice_id, *, get=requests.get, announce=True):
    """Check free-plan library voice eligibility with *zero* TTS requests.

    These GET APIs can be forbidden on API keys scoped to text-to-speech.
    If either metadata lookup fails, report unknown rather than guessing.
    Return metadata-free categories and a conservative known-block flag.
    """
    if not api_key or not voice_id:
        raise RuntimeError("Both ElevenLabs repository secrets are required")
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,100}", voice_id):
        raise ValueError("ELEVENLABS_VOICE_ID has an invalid format")
    subscription = _read_only_metadata(
        "https://api.elevenlabs.io/v1/user/subscription",
        api_key, get=get,
    )
    voice = _read_only_metadata(
        f"https://api.elevenlabs.io/v1/voices/{voice_id}",
        api_key, get=get,
    )
    tier = str(subscription.get("tier", "")).lower()
    plan = "free" if tier in ("free", "free_disabled") else (
        "paid" if tier in ("starter", "creator", "pro", "scale",
                           "business", "enterprise") else "unknown"
    )
    shared = isinstance(voice.get("sharing"), dict)
    voice_type = "shared_voice_library" if shared else (
        "other" if voice.get("voice_id") == voice_id else "unknown"
    )
    eligible_tiers = voice.get("available_for_tiers")
    explicitly_paid_only = (
        isinstance(eligible_tiers, list) and bool(eligible_tiers)
        and "free" not in eligible_tiers
    )
    blocked = plan == "free" and (shared or explicitly_paid_only)
    credits = "unknown"
    used = subscription.get("character_count")
    allowed = subscription.get("character_limit")
    if (type(used) is int and type(allowed) is int
            and 0 <= used and allowed >= 0):
        credits = "exhausted" if allowed - used <= 0 else "not_exhausted"
    result = {
        "plan": plan,
        "voice_type": voice_type,
        "credit_counter": credits,
        "known_free_voice_block": blocked,
    }
    if announce:
        print(
            "ElevenLabs read-only diagnostic: "
            f"plan={plan}, selected_voice={voice_type}, "
            f"quota_counter={credits}; TTS requests=0."
        )
        if blocked:
            print(
                "Voice access blocked: the selected shared/restricted voice "
                "cannot be synthesized using this free-tier API key. "
                "Select an eligible premade voice or a paid plan."
            )
        elif plan == "unknown" or voice_type == "unknown":
            print(
                "API metadata unavailable or restricted: no conclusion about "
                "this voice. See the ElevenLabs dashboard for plan and voice."
            )
        else:
            print(
                "No known voice-plan block detected by metadata. "
                "This does not guarantee sufficient credits or TTS access."
            )
    return result


def request_sample(api_key, voice_id, *, post=requests.post, text=SAMPLE):
    """Exactly one API request. Fail closed on errors, quotas and audio issues.

    The request is limited by script length, contains no sensitive content,
    does not follow redirects, and will not retry a rejected paid request.
    """
    if not api_key or not voice_id:
        raise RuntimeError("Both ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID are required")
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,100}", voice_id):
        raise ValueError("ELEVENLABS_VOICE_ID has an invalid format")
    payload = audition_payload(text)
    response = post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        headers={
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
        params={"output_format": OUTPUT_FORMAT},
        json=payload,
        timeout=(10, 85),
        allow_redirects=False,
    )
    if response.status_code != 200:
        # Only a whitelisted error category is printed, not the raw
        # response text, key, voice name/ID or account details.
        raise RuntimeError(
            f"ElevenLabs audition returned HTTP {response.status_code} "
            f"({_safe_error_reason(response)}); "
            "no retry and no production change"
        )
    content_type = str(response.headers.get("Content-Type", "")).lower()
    audio = response.content
    if not content_type.startswith("audio/"):
        raise RuntimeError("ElevenLabs returned a non-audio response")
    if not 50_000 <= len(audio) <= MAX_AUDIO_BYTES:
        raise RuntimeError("ElevenLabs response has unexpected audio size")
    if not (audio.startswith(b"ID3") or (
        len(audio) > 2 and audio[0] == 0xff and audio[1] & 0xe0 == 0xe0
    )):
        raise RuntimeError("ElevenLabs response is not recognized MP3")
    return audio


def inspect_mp3(path):
    """Use ffprobe to check output duration and codec before retaining it."""
    done = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration:stream=codec_name", "-of", "json", str(path)],
        check=True, capture_output=True, text=True, timeout=15,
    )
    data = json.loads(done.stdout)
    if not any(stream.get("codec_name") == "mp3"
               for stream in data.get("streams", [])):
        raise RuntimeError("Audition output is not an MP3")
    duration = float(data["format"]["duration"])
    if not 20 <= duration <= 90:
        raise RuntimeError("Audition audio duration outside 20-90 seconds")
    return round(duration, 1)


def main(voice_id_override=None):
    """Use selected voice without changing the GitHub voice secret."""
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    voice = voice_id_override or os.environ.get("ELEVENLABS_VOICE_ID", "").strip()
    # Validate preconditions before making any billable request.
    audition_payload()
    if not key or not voice:
        raise RuntimeError("Configure both ElevenLabs repository secrets first")
    status = diagnose_access(key, voice, announce=False)
    if status["known_free_voice_block"]:
        raise RuntimeError(
            "ElevenLabs free-tier API cannot synthesize this Voice Library "
            "voice. No voice-generation request made; choose a premade "
            "API-eligible voice or an appropriate paid plan."
        )
    output = Path("voice-audition")
    output.mkdir(exist_ok=True)
    audio = request_sample(key, voice)
    target = output / "first-light-elevenlabs-free-test.mp3"
    temp = output / "audition.partial"
    try:
        temp.write_bytes(audio)
        duration = inspect_mp3(temp)
        temp.replace(target)
    finally:
        temp.unlink(missing_ok=True)
    (output / "script.txt").write_text(SAMPLE + "\n", encoding="utf-8")
    (output / "attribution.txt").write_text(
        "Generated with ElevenLabs. Noncommercial voice evaluation only.\n",
        encoding="utf-8",
    )
    (output / "metadata.json").write_text(
        json.dumps({
            "purpose": "Noncommercial, manual-only voice comparison",
            "production_changed": False,
            "model": MODEL,
            "audio_format": OUTPUT_FORMAT,
            "sample_characters": len(SAMPLE),
            "sample_words": len(SAMPLE.split()),
            "audio_seconds": duration,
            "api_calls": 1,
            "note": "Free-tier use requires attribution; no public release.",
        }, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Voice sample verified: {duration:.1f}s; "
        "one ElevenLabs request; audition artifact only; Charon unchanged."
    )


if __name__ == "__main__":
    if sys.argv[1:] == ["--diagnose"]:
        diagnose_access(
            os.environ.get("ELEVENLABS_API_KEY", "").strip(),
            os.environ.get("ELEVENLABS_VOICE_ID", "").strip(),
        )
    elif len(sys.argv) == 1:
        main()
    else:
        raise SystemExit("Use --diagnose for the read-only credit-free preflight")
